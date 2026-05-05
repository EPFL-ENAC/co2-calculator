"""Plan 310B Part 4 — auto-recalc fan-out at end of FACTORS sync."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.tasks.ingestion_tasks import _enqueue_stale_recalculations


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_creates_one_job_per_target():
    """Fans out one emission_recalc job per (module, det) flagged
    needs_recalculation, scoped to the parent's module/det filter."""
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    repo.get_recalculation_status_by_year = AsyncMock(
        return_value=[
            {
                "module_type_id": 1,
                "data_entry_type_id": 10,
                "year": 2025,
                "needs_recalculation": True,
            },
            {
                "module_type_id": 1,
                "data_entry_type_id": 11,
                "year": 2025,
                "needs_recalculation": True,
            },
            {
                "module_type_id": 2,
                "data_entry_type_id": 20,
                "year": 2025,
                "needs_recalculation": False,
            },
        ]
    )
    created_jobs = [MagicMock(id=100), MagicMock(id=101)]
    repo.create_ingestion_job = AsyncMock(side_effect=created_jobs)

    pipeline = uuid4()

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget") as mock_create_task,
        patch(
            "app.tasks.emission_recalculation_tasks.run_recalculation_task"
        ) as mock_runner,
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=None,  # no module filter — both stale combos hit
            data_entry_type_id=None,
            year=2025,
            pipeline_id=pipeline,
        )

    # Two stale combos → two jobs created and two tasks scheduled.
    assert repo.create_ingestion_job.await_count == 2
    assert mock_create_task.call_count == 2
    # Each created job inherited the parent pipeline_id.
    for call in repo.create_ingestion_job.await_args_list:
        new_job = call.args[0]
        assert new_job.pipeline_id == pipeline
        assert new_job.year == 2025
        assert new_job.meta["config"]["parent_job_id"] == 42
    # Sanity: the runner reference is what fire_and_forget wraps.
    assert mock_runner is not None


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_multitype_fans_out_per_module_det():
    """Multi-type factor upload (parent has module set, det=NULL) fans out
    one recalc per data_entry_type in MODULE_TYPE_TO_DATA_ENTRY_TYPES for
    that module — bypassing get_recalculation_status_by_year, which filters
    out factor jobs with data_entry_type_id IS NULL and would silently
    drop the recalc.
    """
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    # Should not be consulted in the multi-type branch — fail loudly if it is.
    repo.get_recalculation_status_by_year = AsyncMock(
        side_effect=AssertionError(
            "multi-type fan-out must not consult get_recalculation_status_by_year"
        )
    )
    repo.create_ingestion_job = AsyncMock(return_value=MagicMock(id=100))

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget"),
        patch("app.tasks.emission_recalculation_tasks.run_recalculation_task"),
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=1,  # headcount → [member, student]
            data_entry_type_id=None,
            year=2025,
            pipeline_id=uuid4(),
        )

    # MODULE_TYPE_TO_DATA_ENTRY_TYPES[ModuleTypeEnum.headcount] is
    # [member=1, student=2] — both should land.
    assert repo.create_ingestion_job.await_count == 2
    landed_dets = {
        call.args[0].data_entry_type_id
        for call in repo.create_ingestion_job.await_args_list
    }
    assert landed_dets == {1, 2}
    for call in repo.create_ingestion_job.await_args_list:
        assert call.args[0].module_type_id == 1
        assert call.args[0].meta["config"]["parent_job_id"] == 42


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_noop_when_no_stale():
    """No targets flagged → no jobs created, no tasks fired, no errors."""
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    repo.get_recalculation_status_by_year = AsyncMock(return_value=[])
    repo.create_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget") as mock_create_task,
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=None,
            data_entry_type_id=None,
            year=2025,
            pipeline_id=uuid4(),
        )

    repo.create_ingestion_job.assert_not_awaited()
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_returns_when_year_is_none():
    """If the parent factor job has no year, fan-out can't choose a recalc
    scope — log a warning and return without consulting the repo."""
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    repo.get_recalculation_status_by_year = AsyncMock()
    repo.create_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget") as mock_create_task,
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=1,
            data_entry_type_id=None,
            year=None,
            pipeline_id=uuid4(),
        )

    # Early-return path: nothing should be queried, nothing should be fired.
    repo.get_recalculation_status_by_year.assert_not_awaited()
    repo.create_ingestion_job.assert_not_awaited()
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_skips_unknown_module_type():
    """Multi-type fan-out with an unknown ``module_type_id`` (e.g. an enum
    value that no longer exists after a deletion) must skip rather than
    raise — the parent factor job already finished; we don't want to take
    the calling code down with a ValueError from MdoduleTypeEnum()."""
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    repo.get_recalculation_status_by_year = AsyncMock(
        side_effect=AssertionError(
            "Unknown-module branch must short-circuit before consulting the repo"
        )
    )
    repo.create_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget") as mock_create_task,
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=99999,  # not a valid ModuleTypeEnum value
            data_entry_type_id=None,
            year=2025,
            pipeline_id=uuid4(),
        )

    repo.create_ingestion_job.assert_not_awaited()
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_stale_recalculations_single_type_uses_parent_scope():
    """Plan 310B fix (Copilot follow-up): single-type factor uploads
    (parent has both module_type_id and data_entry_type_id set) MUST
    NOT consult ``get_recalculation_status_by_year`` — that helper
    filters on ``state=FINISHED`` but the parent factor job is still
    RUNNING when the fan-out fires, so the query returns no row and
    the recalc would silently skip.

    Instead, the helper builds a single target directly from the
    parent's (module, det) scope.  Pin that contract here.
    """
    session = MagicMock()
    session.commit = AsyncMock()

    repo = MagicMock()
    # If the helper consults this, the test fails — proves the
    # short-circuit is in place.
    repo.get_recalculation_status_by_year = AsyncMock(
        side_effect=AssertionError(
            "single-type fan-out must not consult get_recalculation_status_by_year"
        )
    )
    repo.create_ingestion_job = AsyncMock(return_value=MagicMock(id=200))

    pipeline = uuid4()

    with (
        patch("app.tasks.ingestion_tasks.DataIngestionRepository", return_value=repo),
        patch("app.tasks._background.fire_and_forget") as mock_create_task,
        patch("app.tasks.emission_recalculation_tasks.run_recalculation_task"),
    ):
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=42,
            module_type_id=5,  # single-type: both fields set
            data_entry_type_id=11,
            year=2025,
            pipeline_id=pipeline,
        )

    # Exactly one child job — for the parent's (module, det) — fired.
    assert repo.create_ingestion_job.await_count == 1
    new_job = repo.create_ingestion_job.await_args.args[0]
    assert new_job.module_type_id == 5
    assert new_job.data_entry_type_id == 11
    assert new_job.year == 2025
    assert new_job.pipeline_id == pipeline
    assert new_job.meta["config"]["parent_job_id"] == 42
    assert mock_create_task.call_count == 1
