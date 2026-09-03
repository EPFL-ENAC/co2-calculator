"""Unit tests for carbon_report API endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report as module


def _db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock())
    return db


def _user():
    return MagicMock()


# ── list_carbon_reports_by_unit ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carbon_reports_by_unit_returns_list():
    db = _db()
    mock_reports = [MagicMock(), MagicMock()]
    svc = MagicMock()
    svc.list_by_unit = AsyncMock(return_value=mock_reports)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.list_carbon_reports_by_unit(1, db, _user())
        assert result == mock_reports
    finally:
        module.CarbonReportService = original


# ── get_carbon_report_by_unit_and_year ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_carbon_report_by_unit_and_year_found():
    db = _db()
    report = MagicMock()
    svc = MagicMock()
    svc.get_by_unit_and_year = AsyncMock(return_value=report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.get_carbon_report_by_unit_and_year(
                1, 2024, db, _user()
            )
        assert result == report
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_by_unit_and_year_not_found():
    db = _db()
    svc = MagicMock()
    svc.get_by_unit_and_year = AsyncMock(return_value=None)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                await module.get_carbon_report_by_unit_and_year(1, 2024, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


# ── create_carbon_report ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_carbon_report_commits_and_returns():
    db = _db()
    new_report = MagicMock()
    svc = MagicMock()
    svc.create = AsyncMock(return_value=new_report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        payload = MagicMock()
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.create_carbon_report(payload, db, _user())
        assert result == new_report
        db.commit.assert_awaited_once()
    finally:
        module.CarbonReportService = original


# ── get_carbon_report ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_carbon_report_found():
    db = _db()
    report = MagicMock()
    report.carbon_project_id = None
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)
    sentinel = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
            patch.object(
                module, "_carbon_report_read", AsyncMock(return_value=sentinel)
            ) as read_mock,
        ):
            result = await module.get_carbon_report(42, db, _user())
        assert result == sentinel
        read_mock.assert_awaited_once_with(db, report)
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_not_found():
    db = _db()
    svc = MagicMock()
    svc.get = AsyncMock(return_value=None)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.get_carbon_report(99, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


def _explore_report_db(report_type, created_by, unit=None):
    """DB stub returning a fixed report's project by CarbonProject, else unit."""
    from app.models.carbon_project import CarbonProject

    project = MagicMock()
    project.carbon_report_type = report_type
    project.created_by = created_by
    unit = unit if unit is not None else MagicMock()

    async def _get(model, key):
        if model is CarbonProject:
            return project
        return unit

    db = _db()
    db.get = AsyncMock(side_effect=_get)
    return db


@pytest.mark.asyncio
async def test_get_carbon_report_denies_non_creator_explore_by_id():
    """#2461: a same-unit colleague cannot GET another user's Explore sandbox."""
    from app.models.carbon_report import CarbonReportType

    report = MagicMock()
    report.carbon_project_id = 7
    report.unit_id = 1
    db = _explore_report_db(CarbonReportType.SIMULATOR_EXPLORE, created_by=1)
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)
    current_user = MagicMock(id=2)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with patch.object(module, "require_unit_access"):
            with pytest.raises(HTTPException) as exc:
                await module.get_carbon_report(7, db, current_user)
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_allows_creator_explore_by_id():
    from app.models.carbon_report import CarbonReportType

    report = MagicMock()
    report.carbon_project_id = 7
    report.unit_id = 1
    db = _explore_report_db(CarbonReportType.SIMULATOR_EXPLORE, created_by=1)
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)
    current_user = MagicMock(id=1)
    sentinel = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(
                module, "_carbon_report_read", AsyncMock(return_value=sentinel)
            ),
        ):
            result = await module.get_carbon_report(7, db, current_user)
        assert result is sentinel
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_plan_report_ignores_creator_mismatch():
    """SIMULATOR_PLAN must stay unaffected by the #2461 Explore ownership gate."""
    from app.models.carbon_report import CarbonReportType

    report = MagicMock()
    report.carbon_project_id = 7
    report.unit_id = 1
    db = _explore_report_db(CarbonReportType.SIMULATOR_PLAN, created_by=1)
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)
    current_user = MagicMock(id=2)
    sentinel = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(
                module, "_carbon_report_read", AsyncMock(return_value=sentinel)
            ),
        ):
            result = await module.get_carbon_report(7, db, current_user)
        assert result is sentinel
    finally:
        module.CarbonReportService = original


# ── list_carbon_report_modules ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carbon_report_modules_found():
    db = _db()
    report = MagicMock()
    modules = [MagicMock()]
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.list_modules = AsyncMock(return_value=modules)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.list_carbon_report_modules(1, db, _user())
        assert result == modules
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_list_carbon_report_modules_report_not_found():
    db = _db()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    module.CarbonReportService = lambda db: report_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.list_carbon_report_modules(1, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report


# ── update_carbon_report_module_status ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_status_success():
    db = _db()
    report = MagicMock()
    updated = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    report_svc.recompute_report_stats = AsyncMock()
    report_svc.recompute_report_progress = AsyncMock()
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(return_value=updated)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        update_payload = MagicMock()
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.update_carbon_report_module_status(
                1, 2, update_payload, db, _user()
            )
        assert result == updated
        db.commit.assert_awaited_once()
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_update_status_report_not_found():
    db = _db()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    module.CarbonReportService = lambda db: report_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.update_carbon_report_module_status(
                1, 2, MagicMock(), db, _user()
            )
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report


@pytest.mark.asyncio
async def test_update_status_module_not_found():
    db = _db()
    report = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                await module.update_carbon_report_module_status(
                    1, 2, MagicMock(), db, _user()
                )
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_update_status_value_error_raises_400():
    db = _db()
    report = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(side_effect=ValueError("bad status"))

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                await module.update_carbon_report_module_status(
                    1, 2, MagicMock(), db, _user()
                )
        assert exc.value.status_code == 400
        assert "bad status" in exc.value.detail
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


# ── get_simulator_explore_carbon_report (#2656) ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_simulator_explore_found_returns_it():
    """Found → return the report (with its resolved factor year, #2631).

    Read-only: no background task, ever.
    """
    db = _db()
    report = MagicMock()
    report.id = 42
    svc = MagicMock()
    svc.get_explore = AsyncMock(return_value=report)
    sentinel = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
            patch.object(
                module, "_carbon_report_read", AsyncMock(return_value=sentinel)
            ) as read_mock,
        ):
            result = await module.get_simulator_explore_carbon_report(1, db, _user())
        assert result == sentinel
        read_mock.assert_awaited_once_with(db, report)
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_simulator_explore_not_found_raises_404():
    """Missing report → 404, no create-fallback."""
    db = _db()
    svc = MagicMock()
    svc.get_explore = AsyncMock(return_value=None)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                await module.get_simulator_explore_carbon_report(1, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


# ── create_simulator_explore_carbon_report (#2656) ──────────────────────────────


@pytest.mark.asyncio
async def test_create_simulator_explore_always_creates_and_schedules_cleanup():
    """POST always creates — no existence check — and queues cleanup of the rest."""
    db = _db()
    new_report = MagicMock()
    new_report.id = 55
    new_report.carbon_project_id = 7
    workflow = MagicMock()
    workflow.create = AsyncMock(return_value=new_report)
    sentinel = MagicMock()

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.ExploreProvisioningWorkflow
    module.ExploreProvisioningWorkflow = lambda db: workflow
    user = _user()
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
            patch.object(
                module, "_carbon_report_read", AsyncMock(return_value=sentinel)
            ) as read_mock,
        ):
            result = await module.create_simulator_explore_carbon_report(
                1, background_tasks, db, user
            )
        assert result == sentinel
        read_mock.assert_awaited_once_with(db, new_report)
        workflow.create.assert_awaited_once_with(unit_id=1, created_by=user.id)
        background_tasks.add_task.assert_called_once_with(
            module._cleanup_old_explore_background,
            unit_id=1,
            created_by=user.id,
            keep_project_id=7,
        )
    finally:
        module.ExploreProvisioningWorkflow = original


@pytest.mark.asyncio
async def test_create_simulator_explore_raises_when_project_id_missing():
    """A created report without a project id is a server bug, not a 404/400."""
    db = _db()
    new_report = MagicMock()
    new_report.carbon_project_id = None
    workflow = MagicMock()
    workflow.create = AsyncMock(return_value=new_report)

    original = module.ExploreProvisioningWorkflow
    module.ExploreProvisioningWorkflow = lambda db: workflow
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                await module.create_simulator_explore_carbon_report(
                    1, MagicMock(), db, _user()
                )
        assert exc.value.status_code == 500
    finally:
        module.ExploreProvisioningWorkflow = original


# ── _carbon_report_read (#2631) ────────────────────────────────────────────────


def _explore_report_row(**overrides):
    fields = {
        "id": 42,
        "year": 2026,
        "reference_year": None,
        "unit_id": 1,
        "carbon_project_id": 7,
        "is_grant": False,
        "budget": None,
        "budget_currency": None,
        "stats": None,
        "last_updated": None,
        "completion_progress": None,
        "overall_status": 0,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.mark.asyncio
async def test_carbon_report_read_carries_resolved_factor_year():
    report = _explore_report_row()
    with patch.object(module, "resolve_factor_year_safe", AsyncMock(return_value=2025)):
        result = await module._carbon_report_read(_db(), report)
    assert result.factor_year == 2025
    assert result.year == 2026  # creation year untouched, distinct field (#2656)


@pytest.mark.asyncio
async def test_carbon_report_read_factor_year_none_when_unresolvable():
    """No published factors for either fallback year → None, not a 500 (#2631).

    The sandbox itself is real; only its dropdowns have nothing to price
    against yet.
    """
    report = _explore_report_row()
    with patch.object(module, "resolve_factor_year_safe", AsyncMock(return_value=None)):
        result = await module._carbon_report_read(_db(), report)
    assert result.factor_year is None
