"""Tests for unit sync tasks from Accred API.

Plan 310B Part 5 — ``run_sync_task_accred`` now claims a tracked
DataIngestionJob (entity_type=GLOBAL_PER_YEAR), updates ``status_message``
between steps via the dual-session pattern, and finishes by stamping the
job FINISHED+SUCCESS (or ERROR on failure).  These tests assert the new
contract: that the job lifecycle transitions are emitted in order.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionResult, IngestionState
from app.tasks.unit_sync_tasks import SyncUnitRequest, run_sync_task_accred


@pytest.fixture
def mock_accred_units_raw():
    return [
        {
            "id": "1",
            "name": "Unit 1",
            "labelfr": "Unité 1",
            "labelen": "Unit 1",
            "level": 1,
            "parentid": None,
            "pathcf": None,
            "path": "Unit 1",
            "cf": "1",
            "responsible": {
                "email": "user1@example.com",
                "id": "100",
                "name": "User 1",
            },
            "responsibleid": "100",
            "unittypeid": 1,
            "unittype": {"label": "Building"},
            "enddate": "0001-01-01T00:00:00Z",
            "ancestors": [],
        },
    ]


@pytest.fixture
def mock_accred_principal_users_raw():
    return [{"email": "user1@example.com", "id": "100", "name": "User 1"}]


def _patched_session_local():
    """Build a MagicMock SessionLocal whose async-context-manager returns a
    fresh mock session each call (job_session and data_session must be
    distinct so call_count assertions stay meaningful)."""
    session_local = MagicMock()

    def _new_session(*_args, **_kwargs):
        sess = MagicMock()
        sess.commit = AsyncMock()
        sess.rollback = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=sess)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    session_local.side_effect = _new_session
    return session_local


def _common_provider_patches(units_raw, users_raw):
    """Build the (unit_provider, role_provider) MagicMocks used by both tests."""
    unit_provider = MagicMock()
    unit_provider.fetch_all_units = AsyncMock(return_value=(units_raw, users_raw))
    unit_provider.map_api_unit = MagicMock(
        side_effect=lambda u: MagicMock(id=None, institutional_id=u["id"])
    )
    role_provider = MagicMock()
    role_provider.map_api_user = MagicMock(
        side_effect=lambda u: MagicMock(id=u["id"], email=u["email"])
    )
    return unit_provider, role_provider


@pytest.mark.asyncio
async def test_run_sync_task_accred_claims_job_and_finishes(
    mock_accred_units_raw,
    mock_accred_principal_users_raw,
):
    """Happy path: claim_job→RUNNING→…steps…→FINISHED+SUCCESS."""
    unit_provider, role_provider = _common_provider_patches(
        mock_accred_units_raw, mock_accred_principal_users_raw
    )
    repo = MagicMock()
    repo.claim_job = AsyncMock(return_value=True)
    repo.update_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.unit_sync_tasks.SessionLocal", _patched_session_local()),
        patch("app.tasks.unit_sync_tasks.DataIngestionRepository", return_value=repo),
        patch(
            "app.tasks.unit_sync_tasks.get_unit_provider", return_value=unit_provider
        ),
        patch(
            "app.tasks.unit_sync_tasks.get_role_provider", return_value=role_provider
        ),
        patch("app.tasks.unit_sync_tasks.UnitService") as MockUnitService,
        patch("app.tasks.unit_sync_tasks.UserService") as MockUserService,
        patch("app.tasks.unit_sync_tasks.CarbonReportService") as MockCRService,
    ):
        unit_result = MagicMock()
        unit_result.data = [MagicMock(id=1, institutional_id="1")]
        user_result = MagicMock()
        user_result.data = [MagicMock(id="100", email="user1@example.com")]
        MockUnitService.return_value.bulk_upsert = AsyncMock(return_value=unit_result)
        MockUserService.return_value.bulk_upsert = AsyncMock(return_value=user_result)

        cr_service = MagicMock()
        reports = [MagicMock(id=1, year=2024, unit_id=1)]
        cr_service.bulk_upsert = AsyncMock(return_value=reports)
        cr_service.ensure_modules_for_reports = AsyncMock()
        MockCRService.return_value = cr_service

        await run_sync_task_accred(SyncUnitRequest(target_year=2024), job_id=99)

    repo.claim_job.assert_awaited_once_with(99, mock_pod_id_arg(repo.claim_job))
    final_call = repo.update_ingestion_job.call_args_list[-1]
    assert final_call.kwargs["state"] == IngestionState.FINISHED
    assert final_call.kwargs["result"] == IngestionResult.SUCCESS
    cr_service.ensure_modules_for_reports.assert_awaited_once_with(reports)


@pytest.mark.asyncio
async def test_run_sync_task_accred_claim_failed_returns_silently(
    mock_accred_units_raw,
    mock_accred_principal_users_raw,
):
    """If claim_job returns False, the task returns without fetching anything."""
    unit_provider, role_provider = _common_provider_patches(
        mock_accred_units_raw, mock_accred_principal_users_raw
    )
    repo = MagicMock()
    repo.claim_job = AsyncMock(return_value=False)
    repo.update_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.unit_sync_tasks.SessionLocal", _patched_session_local()),
        patch("app.tasks.unit_sync_tasks.DataIngestionRepository", return_value=repo),
        patch(
            "app.tasks.unit_sync_tasks.get_unit_provider", return_value=unit_provider
        ),
        patch(
            "app.tasks.unit_sync_tasks.get_role_provider", return_value=role_provider
        ),
    ):
        await run_sync_task_accred(SyncUnitRequest(target_year=2024), job_id=99)

    repo.claim_job.assert_awaited_once()
    repo.update_ingestion_job.assert_not_awaited()
    unit_provider.fetch_all_units.assert_not_awaited()


def mock_pod_id_arg(claim_mock):
    """Read the second positional arg passed to claim_job (POD_ID is module-
    scoped so we just echo whatever was actually used)."""
    return claim_mock.call_args.args[1]


@pytest.mark.asyncio
async def test_run_sync_task_accred_marks_job_error_when_provider_fails(
    mock_accred_units_raw,
    mock_accred_principal_users_raw,
):
    """Service raises mid-sync → except block runs: data_session rolled back,
    job stamped FINISHED+ERROR with the exception message.

    The task does NOT re-raise: the endpoint schedules it via
    ``fire_and_forget`` (no awaiter), so re-raising would surface as
    "Task exception was never retrieved" warnings.  Operators see the
    error via the persisted job state + status_message; that's what
    this test asserts.
    """
    unit_provider, role_provider = _common_provider_patches(
        mock_accred_units_raw, mock_accred_principal_users_raw
    )
    # Make fetch_all_units the failure point — an Accred outage is the
    # most realistic trigger for the except branch.
    unit_provider.fetch_all_units = AsyncMock(side_effect=RuntimeError("Accred down"))

    repo = MagicMock()
    repo.claim_job = AsyncMock(return_value=True)
    repo.update_ingestion_job = AsyncMock()

    with (
        patch("app.tasks.unit_sync_tasks.SessionLocal", _patched_session_local()),
        patch("app.tasks.unit_sync_tasks.DataIngestionRepository", return_value=repo),
        patch(
            "app.tasks.unit_sync_tasks.get_unit_provider", return_value=unit_provider
        ),
        patch(
            "app.tasks.unit_sync_tasks.get_role_provider", return_value=role_provider
        ),
    ):
        # Must NOT raise — the task swallows the exception by design so
        # fire_and_forget callers don't see "Task exception was never
        # retrieved" warnings.
        await run_sync_task_accred(SyncUnitRequest(target_year=2024), job_id=99)

    # The error path's final update should mark the job FINISHED+ERROR with
    # the exception message in status_message — operators need to see why
    # it failed without digging through logs.
    final_call = repo.update_ingestion_job.call_args_list[-1]
    assert final_call.kwargs["state"] == IngestionState.FINISHED
    assert final_call.kwargs["result"] == IngestionResult.ERROR
    assert "Accred down" in final_call.kwargs["status_message"]
