"""Unit tests for emission_recalculation_tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionResult, IngestionState
from app.tasks.emission_recalculation_tasks import (
    run_module_recalculation_task,
    run_recalculation_task,
)


def _make_mock_sessions():
    """Return (mock_job_session, mock_data_session) with async commit/rollback."""
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    job_session.rollback = AsyncMock()

    data_session = MagicMock()
    data_session.commit = AsyncMock()
    data_session.rollback = AsyncMock()

    return job_session, data_session


def _patch_session_local(mock_session_local, job_session, data_session):
    """Configure mock SessionLocal to yield job_session then data_session."""
    mock_session_local.return_value.__aenter__ = AsyncMock(
        side_effect=[job_session, data_session]
    )
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)


# ======================================================================
# run_recalculation_task — success path
# ======================================================================


@pytest.mark.asyncio
async def test_run_recalculation_task_success():
    """Job is updated RUNNING → FINISHED/SUCCESS; data_session committed once."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 42

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(
        return_value={
            "recalculated": 5,
            "modules_refreshed": 2,
            "errors": 0,
            "error_details": [],
        }
    )

    fake_entry_repo = MagicMock()
    fake_entry_repo.list_by_data_entry_type_and_year = AsyncMock(
        return_value=[MagicMock(), MagicMock()]
    )

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
        patch(
            "app.repositories.data_entry_repo.DataEntryRepository",
            return_value=fake_entry_repo,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_recalculation_task(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            job_id=42,
        )

    # Data session committed exactly once
    data_session.commit.assert_awaited_once()
    data_session.rollback.assert_not_awaited()

    # Final job update was FINISHED / SUCCESS
    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_run_recalculation_task_partial_errors_returns_warning():
    """Some entry errors → job finishes with WARNING result."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 42

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(
        return_value={
            "recalculated": 3,
            "modules_refreshed": 1,
            "errors": 2,
            "error_details": [{"data_entry_id": 5, "error": "oops"}],
        }
    )

    fake_entry_repo = MagicMock()
    fake_entry_repo.list_by_data_entry_type_and_year = AsyncMock(return_value=[])

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
        patch(
            "app.repositories.data_entry_repo.DataEntryRepository",
            return_value=fake_entry_repo,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_recalculation_task(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            job_id=42,
        )

    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.WARNING


@pytest.mark.asyncio
async def test_run_recalculation_task_error_path():
    """Service raises → job finishes FINISHED/ERROR; data_session rolled back."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 42

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(
        side_effect=RuntimeError("db exploded")
    )

    fake_entry_repo = MagicMock()
    fake_entry_repo.list_by_data_entry_type_and_year = AsyncMock(
        return_value=[MagicMock()]
    )

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
        patch(
            "app.repositories.data_entry_repo.DataEntryRepository",
            return_value=fake_entry_repo,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_recalculation_task(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            job_id=42,
        )

    data_session.rollback.assert_awaited_once()
    data_session.commit.assert_not_awaited()

    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.ERROR


@pytest.mark.asyncio
async def test_run_recalculation_task_job_not_found():
    """When the job is not found the task returns early without raising."""
    job_session, data_session = _make_mock_sessions()

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=None)
    fake_repo.update_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        # Should not raise
        await run_recalculation_task(
            module_type_id=1,
            data_entry_type_id=20,
            year=2025,
            job_id=999,
        )

    fake_repo.update_ingestion_job.assert_not_awaited()


# ======================================================================
# run_module_recalculation_task — module-level bulk variant
# ======================================================================


@pytest.mark.asyncio
async def test_run_module_recalculation_task_all_success():
    """All types recalculate without errors → FINISHED/SUCCESS; commit once."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 99

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()
    fake_repo.create_ingestion_job = AsyncMock(return_value=MagicMock())

    per_type_result = {
        "recalculated": 3,
        "modules_refreshed": 1,
        "errors": 0,
        "error_details": [],
    }

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(return_value=per_type_result)

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_module_recalculation_task(
            module_type_id=1,
            data_entry_type_ids=[20, 21],
            year=2025,
            job_id=99,
        )

    # data_session.commit called exactly once (all-or-nothing)
    data_session.commit.assert_awaited_once()
    data_session.rollback.assert_not_awaited()

    # Final job result: SUCCESS
    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.SUCCESS

    # Both types processed
    assert fake_svc.recalculate_for_data_entry_type.await_count == 2

    # One per-type stub job created and marked current for each data entry type
    assert fake_repo.create_ingestion_job.await_count == 2
    assert fake_repo.mark_job_as_current.await_count == 3  # 1 module + 2 per-type


@pytest.mark.asyncio
async def test_run_module_recalculation_task_one_type_error_warning():
    """One type fails entirely → WARNING result; commit still called once."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 99

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()
    fake_repo.create_ingestion_job = AsyncMock(return_value=MagicMock())

    call_count = 0

    async def _svc_side_effect(data_entry_type, year):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("factor resolution failed")
        return {
            "recalculated": 3,
            "modules_refreshed": 1,
            "errors": 0,
            "error_details": [],
        }

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = _svc_side_effect

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_module_recalculation_task(
            module_type_id=1,
            data_entry_type_ids=[20, 21],
            year=2025,
            job_id=99,
        )

    # Data committed once despite the partial error
    data_session.commit.assert_awaited_once()
    data_session.rollback.assert_not_awaited()

    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.WARNING


@pytest.mark.asyncio
async def test_run_module_recalculation_task_all_types_error():
    """All types fail entirely → ERROR result; commit still called once."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 99

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()
    fake_repo.create_ingestion_job = AsyncMock(return_value=MagicMock())

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(
        side_effect=RuntimeError("catastrophic failure")
    )

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_module_recalculation_task(
            module_type_id=1,
            data_entry_type_ids=[20, 21],
            year=2025,
            job_id=99,
        )

    data_session.commit.assert_awaited_once()

    last_call_kwargs = fake_repo.update_ingestion_job.await_args_list[-1].kwargs
    assert last_call_kwargs["state"] == IngestionState.FINISHED
    assert last_call_kwargs["result"] == IngestionResult.ERROR


@pytest.mark.asyncio
async def test_run_module_recalculation_task_per_type_progress_messages():
    """Status messages are updated per type during iteration."""
    job_session, data_session = _make_mock_sessions()

    fake_job = MagicMock()
    fake_job.id = 99

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=fake_job)
    fake_repo.update_ingestion_job = AsyncMock()
    fake_repo.mark_job_as_current = AsyncMock()
    fake_repo.create_ingestion_job = AsyncMock(return_value=MagicMock())

    fake_svc = MagicMock()
    fake_svc.recalculate_for_data_entry_type = AsyncMock(
        return_value={
            "recalculated": 1,
            "modules_refreshed": 1,
            "errors": 0,
            "error_details": [],
        }
    )

    # DataEntryTypeEnum.plane = 20, DataEntryTypeEnum.train = 21
    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
        patch(
            "app.tasks.emission_recalculation_tasks.EmissionRecalculationWorkflow",
            return_value=fake_svc,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_module_recalculation_task(
            module_type_id=1,
            data_entry_type_ids=[20, 21],
            year=2025,
            job_id=99,
        )

    # Verify per-type progress messages were emitted (one per type during loop)
    all_status_messages = [
        c.kwargs.get("status_message", "")
        for c in fake_repo.update_ingestion_job.await_args_list
    ]
    progress_messages = [m for m in all_status_messages if "(1/2)" in m or "(2/2)" in m]
    assert len(progress_messages) == 2


@pytest.mark.asyncio
async def test_run_module_recalculation_task_job_not_found():
    """When the job is not found the task returns early without error."""
    job_session, data_session = _make_mock_sessions()

    fake_repo = MagicMock()
    fake_repo.get_job_by_id = AsyncMock(return_value=None)
    fake_repo.update_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl,
        patch(
            "app.tasks.emission_recalculation_tasks.DataIngestionRepository",
            return_value=fake_repo,
        ),
    ):
        _patch_session_local(mock_sl, job_session, data_session)

        await run_module_recalculation_task(
            module_type_id=1,
            data_entry_type_ids=[20, 21],
            year=2025,
            job_id=999,
        )

    fake_repo.update_ingestion_job.assert_not_awaited()
    data_session.commit.assert_not_awaited()
