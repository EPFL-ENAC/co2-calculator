"""Unit tests for DataIngestionRepository.

Covers:
- ``get_recalculation_status_by_year`` (Plan 310B)
- ``set_started_at`` plus state-driven ``finished_at`` auto-stamping in
  ``update_ingestion_job``, ``cancel_job`` (Plan 310C observability columns)
- ``get_current_pipeline_id_for_module`` (Plan 310D stale-stats UX)
"""

from uuid import uuid4

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
async def test_update_ingestion_job_auto_stamps_finished_at_on_finished_state(
    db_session: AsyncSession,
):
    """Transitioning to FINISHED auto-stamps ``finished_at``.

    No opt-in flag: the timestamp is derived from the lifecycle state
    transition itself, not a parameter the caller may forget.  This is
    the contract the dashboard's duration query depends on.
    """
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
    )
    await db_session.commit()

    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.finished_at is not None
    assert refreshed.state == IngestionState.FINISHED
    assert refreshed.result == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_update_ingestion_job_to_running_does_not_stamp_finished_at(
    db_session: AsyncSession,
):
    """Non-terminal transitions never stamp ``finished_at``.

    Closes the original ``finished_at: bool`` flag's loophole — callers
    can no longer accidentally persist a terminal timestamp on a
    RUNNING/QUEUED job.  Only the transition to FINISHED triggers the
    stamp.
    """
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    await repo.update_ingestion_job(
        job.id,
        status_message="working",
        metadata={},
        state=IngestionState.RUNNING,
    )
    await db_session.commit()

    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.finished_at is None
    assert refreshed.state == IngestionState.RUNNING


@pytest.mark.asyncio
async def test_update_ingestion_job_finished_at_idempotent_on_repeat_calls(
    db_session: AsyncSession,
):
    """Re-running update on an already-FINISHED row preserves the original timestamp.

    The IS NULL guard (``result_job.finished_at is None``) makes the
    auto-stamp idempotent so retry-update paths can't drift the recorded
    completion time.
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
    first_value = (await _reload_job(db_session, job.id)).finished_at
    assert first_value is not None

    await repo.update_ingestion_job(
        job.id,
        status_message="updated note",
        metadata={"extra": "info"},
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
    )
    await db_session.commit()
    second_value = (await _reload_job(db_session, job.id)).finished_at

    assert second_value == first_value


@pytest.mark.asyncio
async def test_cancel_job_stamps_finished_at(db_session: AsyncSession):
    """``cancel_job`` is a terminal transition — must populate ``finished_at``.

    Without this, observability queries that filter on ``finished_at IS
    NOT NULL`` silently miss cancelled jobs even though they are
    lifecycle-FINISHED.
    """
    repo = DataIngestionRepository(db_session)
    job = _make_pending_job()
    job.state = IngestionState.RUNNING
    job.is_current = True
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None
    assert job.finished_at is None

    cancelled = await repo.cancel_job(job.id)
    await db_session.commit()

    assert cancelled is not None
    refreshed = await _reload_job(db_session, job.id)
    assert refreshed.state == IngestionState.FINISHED
    assert refreshed.result == IngestionResult.ERROR
    assert refreshed.finished_at is not None


# ======================================================================
# get_current_pipeline_id_for_module Tests (Plan 310-D)
# ======================================================================
#
# Resolved during dev-rebase of PR #1053 (PR5) on top of #1052: PR5's
# tests pass ``year=`` to match the superset signature in
# ``DataIngestionRepository.get_current_pipeline_id_for_module``.  HEAD
# (#1052) did NOT have the year filter and its tests omit the kwarg.
# Kept PR5's six tests (they pass year=2025 throughout) and folded in
# HEAD's unique ``skips_jobs_without_pipeline_id`` case so the
# ``pipeline_id IS NOT NULL`` guard coverage isn't lost.


@pytest.mark.asyncio
async def test_get_current_pipeline_id_returns_none_when_no_active_pipeline(
    db_session: AsyncSession,
):
    """No matching jobs → ``None``."""
    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_pipeline_id_returns_active_pipeline(
    db_session: AsyncSession,
):
    """A NOT_STARTED job with a pipeline_id → its pipeline_id."""
    pipeline_id = uuid4()
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.NOT_STARTED,
        result=None,
        is_current=False,
    )
    job.pipeline_id = pipeline_id
    db_session.add(job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result == pipeline_id


@pytest.mark.asyncio
async def test_get_current_pipeline_id_skips_finished_jobs(
    db_session: AsyncSession,
):
    """A FINISHED job with a pipeline_id → does NOT match (terminal state).
    Without this filter, the badge would never clear after a chain
    completes."""
    pipeline_id = uuid4()
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    job.pipeline_id = pipeline_id
    db_session.add(job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_pipeline_id_filters_by_module_type(
    db_session: AsyncSession,
):
    """A pipeline for a different module_type_id → no match for ours."""
    other_pipeline_id = uuid4()
    other_job = _make_job(
        module_type_id=99,  # different module
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    other_job.pipeline_id = other_pipeline_id
    db_session.add(other_job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_pipeline_id_picks_most_recent_when_multiple_active(
    db_session: AsyncSession,
):
    """When multiple active pipelines match, pick the most recent by id.
    Frontend subscribes to a single pipeline so we must pick deterministically;
    most-recent-first matches what the operator just triggered."""
    older_pipeline = uuid4()
    newer_pipeline = uuid4()

    # Two different dets so the (module, det, target, method, year)
    # unique index allows both rows; both still match the
    # module-level pipeline lookup.
    older = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.NOT_STARTED,
        result=None,
        is_current=False,
    )
    older.pipeline_id = older_pipeline
    db_session.add(older)
    await db_session.flush()

    newer = _make_job(
        module_type_id=5,
        data_entry_type_id=12,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    newer.pipeline_id = newer_pipeline
    db_session.add(newer)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result == newer_pipeline


@pytest.mark.asyncio
async def test_get_current_pipeline_id_filters_by_year(
    db_session: AsyncSession,
):
    """An active pipeline for the same module but a different year → no match."""
    other_year_pipeline = uuid4()
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2024,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    job.pipeline_id = other_year_pipeline
    db_session.add(job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_pipeline_id_skips_jobs_without_pipeline_id(
    db_session: AsyncSession,
):
    """Active job without a ``pipeline_id`` (NULL) → returns None.

    Single-step jobs (e.g. unit_sync, manual recalcs) are not part of a
    multi-step chain; they shouldn't trigger the stale-stats badge.
    Carried forward from #1052's test suite — guards the
    ``pipeline_id IS NOT NULL`` clause that PR5 inherited unchanged.
    """
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    job.pipeline_id = None
    db_session.add(job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_id_for_module(module_type_id=5, year=2025)
    assert result is None


# ======================================================================
# get_current_pipeline_ids_for_modules Tests (Plan 310-D bulk N+1 fix)
# ======================================================================


@pytest.mark.asyncio
async def test_get_current_pipeline_ids_for_modules_returns_empty_for_empty_input(
    db_session: AsyncSession,
):
    """Empty ``module_type_ids`` short-circuits without firing a query.

    The carbon-report endpoint can hit this when a report has no
    modules (rare but possible during onboarding); the helper should
    return an empty dict cheaply rather than executing a useless
    ``WHERE module_type_id IN ()`` query."""
    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_ids_for_modules([], year=2025)
    assert result == {}


@pytest.mark.asyncio
async def test_get_current_pipeline_ids_for_modules_one_per_module(
    db_session: AsyncSession,
):
    """Two modules, each with one active pipeline → returns both
    keyed by module_type_id."""
    pipeline_a = uuid4()
    pipeline_b = uuid4()

    job_a = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    job_a.pipeline_id = pipeline_a
    job_b = _make_job(
        module_type_id=6,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.NOT_STARTED,
        result=None,
        is_current=True,
    )
    job_b.pipeline_id = pipeline_b
    db_session.add_all([job_a, job_b])
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_ids_for_modules([5, 6], year=2025)
    assert result == {5: pipeline_a, 6: pipeline_b}


@pytest.mark.asyncio
async def test_get_current_pipeline_ids_for_modules_picks_most_recent_per_module(
    db_session: AsyncSession,
):
    """Single module with two active pipelines → returns the most
    recent (highest id) only.  Mirrors the per-module helper's
    ``ORDER BY id DESC`` semantics folded into a single
    ``DISTINCT ON (module_type_id) ... ORDER BY module_type_id, id DESC``
    scan."""
    older_pipeline = uuid4()
    newer_pipeline = uuid4()

    older = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.NOT_STARTED,
        result=None,
        is_current=False,
    )
    older.pipeline_id = older_pipeline
    db_session.add(older)
    await db_session.flush()

    newer = _make_job(
        module_type_id=5,
        data_entry_type_id=12,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    newer.pipeline_id = newer_pipeline
    db_session.add(newer)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_ids_for_modules([5], year=2025)
    assert result == {5: newer_pipeline}


@pytest.mark.asyncio
async def test_get_current_pipeline_ids_for_modules_omits_modules_with_no_active(
    db_session: AsyncSession,
):
    """Module without an active pipeline is absent from the dict —
    callers use ``.get(...)`` and treat missing as "no badge"."""
    pipeline_a = uuid4()
    finished_pipeline = uuid4()

    job_a = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    job_a.pipeline_id = pipeline_a
    job_b_finished = _make_job(
        module_type_id=6,
        data_entry_type_id=11,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )
    job_b_finished.pipeline_id = finished_pipeline
    db_session.add_all([job_a, job_b_finished])
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_ids_for_modules([5, 6, 7], year=2025)
    # Only module 5 has an active pipeline; 6 is FINISHED, 7 has nothing.
    assert result == {5: pipeline_a}


@pytest.mark.asyncio
async def test_get_current_pipeline_ids_for_modules_filters_by_year(
    db_session: AsyncSession,
):
    """Active pipeline for a different year must not appear — the
    bulk query is keyed by ``(module_type_id, year)`` and a 2024
    pipeline must not bleed into the 2025 dashboard."""
    pipeline_2024 = uuid4()
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2024,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        state=IngestionState.RUNNING,
        result=None,
        is_current=True,
    )
    job.pipeline_id = pipeline_2024
    db_session.add(job)
    await db_session.commit()

    repo = DataIngestionRepository(db_session)
    result = await repo.get_current_pipeline_ids_for_modules([5], year=2025)
    assert result == {}
