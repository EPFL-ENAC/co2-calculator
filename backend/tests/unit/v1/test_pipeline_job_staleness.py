"""Unit tests for the shared job-staleness predicate.

``is_job_stale`` gates the console's stale badge + manual Recover button;
``stale_running_clause`` is the SQL side used by the auto-recovery sweep
and the ``recover_job`` gate. Both derive from one module so the UI and
recovery machinery can never disagree on what "stuck" means — the parity
test at the bottom locks the two implementations together.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionState,
)
from app.repositories.data_ingestion import is_job_stale, stale_running_clause

CUTOFF = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _job(state: IngestionState, locked_at: datetime | None) -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR, state=state, locked_at=locked_at
    )


def test_running_with_stale_heartbeat_is_stale():
    job = _job(IngestionState.RUNNING, CUTOFF - timedelta(minutes=1))
    assert is_job_stale(job, CUTOFF) is True


def test_running_with_fresh_heartbeat_is_not_stale():
    job = _job(IngestionState.RUNNING, CUTOFF + timedelta(minutes=1))
    assert is_job_stale(job, CUTOFF) is False


def test_running_without_lock_is_stale():
    assert is_job_stale(_job(IngestionState.RUNNING, None), CUTOFF) is True


def test_finished_is_never_stale():
    job = _job(IngestionState.FINISHED, CUTOFF - timedelta(hours=2))
    assert is_job_stale(job, CUTOFF) is False


def test_naive_locked_at_is_treated_as_utc():
    # SQLite test DBs return tz-naive datetimes for tz-aware columns.
    naive = (CUTOFF - timedelta(minutes=1)).replace(tzinfo=None)
    assert is_job_stale(_job(IngestionState.RUNNING, naive), CUTOFF) is True


@pytest.mark.asyncio
async def test_stale_predicate_parity(db_session):
    """The SQL clause and the Python twin classify the same rows the same
    way — a change to one without the other fails here."""
    jobs = [
        _job(IngestionState.RUNNING, CUTOFF - timedelta(minutes=1)),  # stale
        _job(IngestionState.RUNNING, CUTOFF + timedelta(minutes=1)),  # fresh
        _job(IngestionState.RUNNING, None),  # stale (no lock)
        _job(IngestionState.FINISHED, CUTOFF - timedelta(hours=2)),  # terminal
        _job(IngestionState.NOT_STARTED, None),  # never stale
    ]
    for job in jobs:
        db_session.add(job)
    await db_session.flush()

    sql_ids = set(
        (
            await db_session.execute(
                select(DataIngestionJob.id).where(stale_running_clause(CUTOFF))
            )
        )
        .scalars()
        .all()
    )
    python_ids = {j.id for j in jobs if is_job_stale(j, CUTOFF)}

    assert sql_ids == python_ids
    assert len(python_ids) == 2
