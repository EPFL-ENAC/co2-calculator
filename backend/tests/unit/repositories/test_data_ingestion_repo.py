"""Unit tests for DataIngestionRepository.

Covers:
- ``get_recalculation_status_by_year`` (Plan 310B)
- ``set_started_at`` and ``update_ingestion_job(finished_at=True)``
  (Plan 310C observability columns)
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.repositories.data_ingestion import DataIngestionRepository


def _make_job(
    module_type_id: int,
    data_entry_type_id: int | None,
    year: int,
    target_type: TargetType,
    ingestion_method: IngestionMethod,
    state: IngestionState,
    result: IngestionResult | None,
    is_current: bool = True,
) -> DataIngestionJob:
    """Helper to build a DataIngestionJob for test fixtures."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=target_type,
        ingestion_method=ingestion_method,
        provider=UserProvider.DEFAULT,
        state=state,
        result=result,
        is_current=is_current,
        meta={},
    )


# ======================================================================
# get_recalculation_status_by_year Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_recalculation_status_factors_only_needs_recalculation(
    db_session: AsyncSession,
):
    """FACTORS job present but no recalculation job → needs_recalculation=True."""
    repo = DataIngestionRepository(db_session)

    factor_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(factor_job)
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert len(rows) == 1
    assert rows[0]["module_type_id"] == 1
    assert rows[0]["data_entry_type_id"] == 20
    assert rows[0]["year"] == 2025
    assert rows[0]["needs_recalculation"] is True
    assert rows[0]["last_factor_job_id"] == factor_job.id
    assert rows[0]["last_recalculation_job_id"] is None
    assert rows[0]["last_recalculation_job_result"] is None


@pytest.mark.asyncio
async def test_get_recalculation_status_recalc_newer_than_factor(
    db_session: AsyncSession,
):
    """Recalculation job has higher id than factor job → needs_recalculation=False."""
    repo = DataIngestionRepository(db_session)

    factor_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(factor_job)
    await db_session.flush()

    recalc_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(recalc_job)
    await db_session.flush()

    # recalc_job.id > factor_job.id because it was inserted after
    assert recalc_job.id is not None
    assert factor_job.id is not None
    assert recalc_job.id > factor_job.id

    rows = await repo.get_recalculation_status_by_year(2025)

    assert len(rows) == 1
    assert rows[0]["needs_recalculation"] is False
    assert rows[0]["last_factor_job_id"] == factor_job.id
    assert rows[0]["last_recalculation_job_id"] == recalc_job.id
    assert rows[0]["last_recalculation_job_result"] == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_get_recalculation_status_factor_newer_than_recalc(
    db_session: AsyncSession,
):
    """Factor job has higher id than recalculation job → needs_recalculation=True.

    Simulated by inserting recalculation job first, then factor job.
    """
    repo = DataIngestionRepository(db_session)

    # Insert recalculation job FIRST so it gets a lower id
    recalc_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(recalc_job)
    await db_session.flush()

    # Insert factor job AFTER so it gets a higher id
    factor_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(factor_job)
    await db_session.flush()

    assert factor_job.id is not None
    assert recalc_job.id is not None
    assert factor_job.id > recalc_job.id

    rows = await repo.get_recalculation_status_by_year(2025)

    assert len(rows) == 1
    assert rows[0]["needs_recalculation"] is True
    assert rows[0]["last_factor_job_id"] == factor_job.id
    assert rows[0]["last_recalculation_job_id"] == recalc_job.id


@pytest.mark.asyncio
async def test_get_recalculation_status_recalc_job_error_needs_recalculation(
    db_session: AsyncSession,
):
    """Recalculation job has higher id than factor job but
    result=ERROR → needs_recalculation=True.

    Even though the recalc job is newer (higher id), the failed result must not
    hide the recalculation-needed badge.
    """
    repo = DataIngestionRepository(db_session)

    factor_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    db_session.add(factor_job)
    await db_session.flush()

    # Insert recalc job AFTER so it gets a higher id
    # (simulates "ran after the factor sync")
    recalc_job = _make_job(
        module_type_id=1,
        data_entry_type_id=20,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        state=IngestionState.FINISHED,
        result=IngestionResult.ERROR,
        is_current=True,
    )
    db_session.add(recalc_job)
    await db_session.flush()

    assert recalc_job.id is not None
    assert factor_job.id is not None
    assert recalc_job.id > factor_job.id

    rows = await repo.get_recalculation_status_by_year(2025)

    assert len(rows) == 1
    assert rows[0]["needs_recalculation"] is True
    assert rows[0]["last_factor_job_id"] == factor_job.id
    assert rows[0]["last_recalculation_job_id"] == recalc_job.id
    assert rows[0]["last_recalculation_job_result"] == IngestionResult.ERROR


@pytest.mark.asyncio
async def test_get_recalculation_status_error_factor_job_excluded(
    db_session: AsyncSession,
):
    """FACTORS job with result=ERROR is excluded → no status row returned."""
    repo = DataIngestionRepository(db_session)

    db_session.add(
        _make_job(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            state=IngestionState.FINISHED,
            result=IngestionResult.ERROR,
            is_current=True,
        )
    )
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert rows == []


@pytest.mark.asyncio
async def test_get_recalculation_status_no_factors_jobs(
    db_session: AsyncSession,
):
    """No FACTORS jobs for the year → empty list returned."""
    repo = DataIngestionRepository(db_session)

    # Only a recalculation job exists, no factor job
    db_session.add(
        _make_job(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            target_type=TargetType.DATA_ENTRIES,
            ingestion_method=IngestionMethod.computed,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
    )
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert rows == []


@pytest.mark.asyncio
async def test_get_recalculation_status_not_current_factor_job_excluded(
    db_session: AsyncSession,
):
    """FACTORS job with is_current=False is excluded from the query."""
    repo = DataIngestionRepository(db_session)

    db_session.add(
        _make_job(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=False,
        )
    )
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert rows == []


@pytest.mark.asyncio
async def test_get_recalculation_status_multiple_modules(
    db_session: AsyncSession,
):
    """Status rows are returned per (module_type_id, data_entry_type_id)."""
    repo = DataIngestionRepository(db_session)

    # Module 1, type 20
    db_session.add(
        _make_job(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
    )
    # Module 2, type 30
    db_session.add(
        _make_job(
            module_type_id=2,
            data_entry_type_id=30,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
    )
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert len(rows) == 2
    module_ids = {r["module_type_id"] for r in rows}
    assert module_ids == {1, 2}
    for row in rows:
        assert row["needs_recalculation"] is True


@pytest.mark.asyncio
async def test_get_recalculation_status_wrong_year_excluded(
    db_session: AsyncSession,
):
    """FACTORS jobs for a different year are not included."""
    repo = DataIngestionRepository(db_session)

    db_session.add(
        _make_job(
            module_type_id=1,
            data_entry_type_id=20,
            year=2024,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
    )
    await db_session.flush()

    rows = await repo.get_recalculation_status_by_year(2025)

    assert rows == []


# ======================================================================
# Plan 310C observability columns: set_started_at + finished_at flag
# ======================================================================


def _make_pending_job() -> DataIngestionJob:
    """Minimal NOT_STARTED job — observability columns default to NULL.

    Distinct from ``_make_job`` above: that helper's required arguments
    (``state``, ``result``, ``target_type``, ...) are tuned for the
    recalculation-status query, where every test row is FINISHED.  Here we
    need NOT_STARTED rows with sensible defaults for everything else, so a
    parameter-free constructor is clearer than defaulting six args of
    ``_make_job``.
    """
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=10,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=False,
        meta={},
    )


async def _reload_job(db_session: AsyncSession, job_id: int) -> DataIngestionJob:
    """Re-SELECT the job after expiring the identity map.

    ``set_started_at`` and the ``finished_at=True`` branch issue raw
    UPDATEs that bypass the ORM, so any session-attached instance keeps
    stale attribute values until we expire and re-fetch.
    """
    db_session.expire_all()
    return (
        await db_session.execute(
            select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_set_started_at_first_call_populates_column(
    db_session: AsyncSession,
):
    """First ``set_started_at`` flips the column from NULL to a timestamp."""
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None
    assert job.started_at is None

    await repo.set_started_at(job.id)
    await db_session.commit()

    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.started_at is not None


@pytest.mark.asyncio
async def test_set_started_at_second_call_is_noop(
    db_session: AsyncSession,
):
    """Second ``set_started_at`` leaves the original timestamp byte-equal.

    Verifies the ``started_at IS NULL`` guard — the property we rely on
    when retries call this method again, since ``finished_at - started_at``
    is supposed to span ALL attempts, not just the most recent one.
    """
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    await repo.set_started_at(job.id)
    await db_session.commit()
    first_value = (await _reload_job(db_session, job.id)).started_at
    assert first_value is not None

    await repo.set_started_at(job.id)
    await db_session.commit()
    second_value = (await _reload_job(db_session, job.id)).started_at

    # Byte-equal, not "earlier-or-equal": SQLite's second-precision clock
    # can make back-to-back UPDATEs produce identical timestamps, which
    # would silently pass an inequality assertion for the wrong reason.
    assert second_value == first_value


@pytest.mark.asyncio
async def test_update_ingestion_job_finished_at_flag_sets_column(
    db_session: AsyncSession,
):
    """``finished_at=True`` stamps the top-level column on the FINISHED transition."""
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None
    assert job.finished_at is None

    await repo.update_ingestion_job(
        job.id,
        status_message="ok",
        metadata={},
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        finished_at=True,
    )
    await db_session.commit()

    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.finished_at is not None
    assert refreshed.state == IngestionState.FINISHED
    assert refreshed.result == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_update_ingestion_job_without_flag_leaves_finished_at_null(
    db_session: AsyncSession,
):
    """Without the flag, ``finished_at`` stays NULL even on FINISHED transitions.

    Backward-compat guarantee for existing callers that drive only the
    legacy ``meta["completed_at"]`` JSON field — they continue to work
    unchanged and the new column stays opt-in.
    """
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    await repo.update_ingestion_job(
        job.id,
        status_message="ok",
        metadata={},
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
    )
    await db_session.commit()

    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.finished_at is None
    assert refreshed.state == IngestionState.FINISHED
