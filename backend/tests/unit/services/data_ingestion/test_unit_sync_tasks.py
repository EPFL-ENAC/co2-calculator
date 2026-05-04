"""Tests for unit sync tasks from Accred API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.unit_sync_tasks import SyncUnitRequest, run_sync_task_accred


@pytest.fixture
def mock_accred_units_raw():
    """Mock raw units from Accred API."""
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
        {
            "id": "2",
            "name": "Unit 2",
            "labelfr": "Unité 2",
            "labelen": "Unit 2",
            "level": 1,
            "parentid": None,
            "pathcf": None,
            "path": "Unit 2",
            "cf": "2",
            "responsible": {
                "email": "user2@example.com",
                "id": "101",
                "name": "User 2",
            },
            "responsibleid": "101",
            "unittypeid": 1,
            "unittype": {"label": "Building"},
            "enddate": "0001-01-01T00:00:00Z",
            "ancestors": [],
        },
    ]


@pytest.fixture
def mock_accred_principal_users_raw():
    """Mock raw principal users from Accred API."""
    return [
        {"email": "user1@example.com", "id": "100", "name": "User 1"},
        {"email": "user2@example.com", "id": "101", "name": "User 2"},
    ]


@pytest.mark.asyncio
async def test_sync_units_creates_carbon_reports(
    mock_accred_units_raw,
    mock_accred_principal_users_raw,
):
    """Test that carbon reports are created for all units."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_unit_result = MagicMock()
    mock_unit_result.data = [
        MagicMock(id=1, institutional_id="1"),
        MagicMock(id=2, institutional_id="2"),
    ]

    mock_user_result = MagicMock()
    mock_user_result.data = [
        MagicMock(id="100", email="user1@example.com"),
        MagicMock(id="101", email="user2@example.com"),
    ]

    mock_reports = [
        MagicMock(id=1, year=2024, unit_id=1),
        MagicMock(id=2, year=2024, unit_id=2),
    ]

    mock_module_service = MagicMock()
    mock_module_service.ensure_modules_for_reports = AsyncMock()

    with (
        patch("app.tasks.unit_sync_tasks.SessionLocal") as mock_session_local,
        patch("app.tasks.unit_sync_tasks.get_unit_provider") as mock_get_unit_provider,
        patch("app.tasks.unit_sync_tasks.get_role_provider") as mock_get_role_provider,
    ):
        mock_provider = MagicMock()
        mock_provider.fetch_all_units = AsyncMock(
            return_value=(mock_accred_units_raw, mock_accred_principal_users_raw)
        )
        mock_provider.map_api_unit = MagicMock(
            side_effect=lambda u: MagicMock(id=None, institutional_id=u["id"])
        )
        mock_get_unit_provider.return_value = mock_provider

        mock_role_provider = MagicMock()
        mock_role_provider.map_api_user = MagicMock(
            side_effect=lambda u: MagicMock(id=u["id"], email=u["email"])
        )
        mock_get_role_provider.return_value = mock_role_provider

        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        with (
            patch("app.tasks.unit_sync_tasks.UnitService") as MockUnitService,
            patch("app.tasks.unit_sync_tasks.UserService") as MockUserService,
            patch(
                "app.tasks.unit_sync_tasks.CarbonReportService"
            ) as MockCarbonReportService,
        ):
            MockUnitService.return_value.bulk_upsert = AsyncMock(
                return_value=mock_unit_result
            )
            MockUserService.return_value.bulk_upsert = AsyncMock(
                return_value=mock_user_result
            )

            mock_cr_service_instance = MagicMock()
            mock_cr_service_instance.bulk_upsert = AsyncMock(return_value=mock_reports)
            mock_cr_service_instance.module_service = mock_module_service
            mock_cr_service_instance.ensure_modules_for_reports = AsyncMock()
            MockCarbonReportService.return_value = mock_cr_service_instance

            result = await run_sync_task_accred(SyncUnitRequest(target_year=2024))

        assert result["status"] == "success"
        assert result["units_synced"] == 2
        assert result["users_synced"] == 2
        assert result["carbon_reports_created"] == 2
        assert result["carbon_report_year"] == 2024

        mock_session.commit.assert_awaited_once()
        mock_cr_service_instance.ensure_modules_for_reports.assert_awaited_once_with(
            mock_reports
        )


@pytest.mark.asyncio
async def test_sync_units_upsert_existing_reports(
    mock_accred_units_raw,
    mock_accred_principal_users_raw,
):
    """Test that existing carbon reports are upserted (bulk_upsert behavior)."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_unit_result = MagicMock()
    mock_unit_result.data = [
        MagicMock(id=1, institutional_id="1"),
        MagicMock(id=2, institutional_id="2"),
    ]

    mock_user_result = MagicMock()
    mock_user_result.data = [
        MagicMock(id="100", email="user1@example.com"),
        MagicMock(id="101", email="user2@example.com"),
    ]

    mock_reports = [
        MagicMock(id=1, year=2024, unit_id=1),
    ]

    mock_module_service = MagicMock()
    mock_module_service.ensure_modules_for_reports = AsyncMock()

    with (
        patch("app.tasks.unit_sync_tasks.SessionLocal") as mock_session_local,
        patch("app.tasks.unit_sync_tasks.get_unit_provider") as mock_get_unit_provider,
        patch("app.tasks.unit_sync_tasks.get_role_provider") as mock_get_role_provider,
    ):
        mock_provider = MagicMock()
        mock_provider.fetch_all_units = AsyncMock(
            return_value=(mock_accred_units_raw, mock_accred_principal_users_raw)
        )
        mock_provider.map_api_unit = MagicMock(
            side_effect=lambda u: MagicMock(id=None, institutional_id=u["id"])
        )
        mock_get_unit_provider.return_value = mock_provider

        mock_role_provider = MagicMock()
        mock_role_provider.map_api_user = MagicMock(
            side_effect=lambda u: MagicMock(id=u["id"], email=u["email"])
        )
        mock_get_role_provider.return_value = mock_role_provider

        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        with (
            patch("app.tasks.unit_sync_tasks.UnitService") as MockUnitService,
            patch("app.tasks.unit_sync_tasks.UserService") as MockUserService,
            patch(
                "app.tasks.unit_sync_tasks.CarbonReportService"
            ) as MockCarbonReportService,
        ):
            MockUnitService.return_value.bulk_upsert = AsyncMock(
                return_value=mock_unit_result
            )
            MockUserService.return_value.bulk_upsert = AsyncMock(
                return_value=mock_user_result
            )

            mock_cr_service_instance = MagicMock()
            mock_cr_service_instance.bulk_upsert = AsyncMock(return_value=mock_reports)
            mock_cr_service_instance.module_service = mock_module_service
            mock_cr_service_instance.ensure_modules_for_reports = AsyncMock()
            MockCarbonReportService.return_value = mock_cr_service_instance

            result = await run_sync_task_accred(SyncUnitRequest(target_year=2024))

        assert result["status"] == "success"
        assert result["units_synced"] == 2
        assert result["carbon_reports_created"] == 1

        mock_cr_service_instance.bulk_upsert.assert_awaited_once()
        mock_cr_service_instance.ensure_modules_for_reports.assert_awaited_once_with(
            mock_reports
        )
