"""Unit tests for the ops-console ``is_stale`` derivation.

``_job_is_stale`` gates the console's stale badge + manual Recover button;
it must mirror ``sweep_stuck_running_jobs``'s predicate (RUNNING with a
lock heartbeat older than the stale window) so the UI and the auto-recovery
sweep agree on what "stuck" means.
"""

from datetime import datetime, timedelta, timezone

from app.api.v1.data_sync import _job_is_stale
from app.models.data_ingestion import DataIngestionJob, EntityType, IngestionState

CUTOFF = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _job(state: IngestionState, locked_at: datetime | None) -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR, state=state, locked_at=locked_at
    )


def test_running_with_stale_heartbeat_is_stale():
    job = _job(IngestionState.RUNNING, CUTOFF - timedelta(minutes=1))
    assert _job_is_stale(job, CUTOFF) is True


def test_running_with_fresh_heartbeat_is_not_stale():
    job = _job(IngestionState.RUNNING, CUTOFF + timedelta(minutes=1))
    assert _job_is_stale(job, CUTOFF) is False


def test_running_without_lock_is_stale():
    assert _job_is_stale(_job(IngestionState.RUNNING, None), CUTOFF) is True


def test_finished_is_never_stale():
    job = _job(IngestionState.FINISHED, CUTOFF - timedelta(hours=2))
    assert _job_is_stale(job, CUTOFF) is False


def test_naive_locked_at_is_treated_as_utc():
    # SQLite test DBs return tz-naive datetimes for tz-aware columns.
    naive = (CUTOFF - timedelta(minutes=1)).replace(tzinfo=None)
    assert _job_is_stale(_job(IngestionState.RUNNING, naive), CUTOFF) is True
