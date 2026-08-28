"""Unit tests for carbon_report API endpoints."""

from datetime import UTC, datetime
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
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.get_carbon_report(42, db, _user())
        assert result == report
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


# ── get_simulator_explore_carbon_report ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_simulator_explore_found_fresh_no_refresh():
    """Found, within TTL → return report, no background refresh scheduled."""
    db = _db()
    fresh_ts = int(datetime.now(UTC).timestamp())
    report = MagicMock()
    report.id = 42
    report.last_updated = fresh_ts
    svc = MagicMock()
    svc.get_explore = AsyncMock(return_value=report)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.get_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, _user()
            )
        assert result == report
        background_tasks.add_task.assert_not_called()
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_simulator_explore_not_found_raises_404():
    """Missing report → 404."""
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
                await module.get_simulator_explore_carbon_report(
                    1, 2024, MagicMock(), db, _user()
                )
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_simulator_explore_expired_schedules_background_refresh():
    """Stale report (>24 h) → returned immediately, background refresh queued."""
    db = _db()
    stale_ts = int(datetime.now(UTC).timestamp()) - (25 * 60 * 60)
    report = MagicMock()
    report.id = 99
    report.last_updated = stale_ts
    svc = MagicMock()
    svc.get_explore = AsyncMock(return_value=report)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    user = _user()
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.get_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, user
            )
        assert result == report  # stale report returned immediately
        background_tasks.add_task.assert_called_once_with(
            module._refresh_explore_background,
            unit_id=1,
            old_report_id=99,
            reference_year=2024,
            created_by=user.id,
        )
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_simulator_explore_null_last_updated_schedules_refresh():
    """last_updated=None (no timestamp) → treated as expired, refresh queued."""
    db = _db()
    report = MagicMock()
    report.id = 7
    report.last_updated = None
    svc = MagicMock()
    svc.get_explore = AsyncMock(return_value=report)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.get_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, _user()
            )
        assert result == report
        background_tasks.add_task.assert_called_once()
    finally:
        module.CarbonReportService = original


# ── put_simulator_explore_carbon_report (#2487) ────────────────────────────────


@pytest.mark.asyncio
async def test_put_simulator_explore_creates_when_missing():
    """PUT is idempotent: missing sandbox → workflow creates it, no refresh."""
    db = _db()
    fresh_ts = int(datetime.now(UTC).timestamp())
    new_report = MagicMock()
    new_report.id = 55
    new_report.last_updated = fresh_ts
    workflow = MagicMock()
    workflow.ensure = AsyncMock(return_value=new_report)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.ExploreProvisioningWorkflow
    module.ExploreProvisioningWorkflow = lambda db: workflow
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.put_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, _user()
            )
        assert result == new_report
        workflow.ensure.assert_awaited_once()
        background_tasks.add_task.assert_not_called()
    finally:
        module.ExploreProvisioningWorkflow = original


@pytest.mark.asyncio
async def test_put_simulator_explore_returns_existing_without_recreating():
    """PUT is idempotent: an existing, fresh sandbox is returned as-is."""
    db = _db()
    fresh_ts = int(datetime.now(UTC).timestamp())
    existing = MagicMock()
    existing.id = 42
    existing.last_updated = fresh_ts
    workflow = MagicMock()
    workflow.ensure = AsyncMock(return_value=existing)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.ExploreProvisioningWorkflow
    module.ExploreProvisioningWorkflow = lambda db: workflow
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.put_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, _user()
            )
        assert result == existing
        background_tasks.add_task.assert_not_called()
    finally:
        module.ExploreProvisioningWorkflow = original


@pytest.mark.asyncio
async def test_put_simulator_explore_schedules_refresh_when_stale():
    """A stale existing sandbox is returned immediately; refresh is queued."""
    db = _db()
    stale_ts = int(datetime.now(UTC).timestamp()) - (25 * 60 * 60)
    existing = MagicMock()
    existing.id = 99
    existing.last_updated = stale_ts
    workflow = MagicMock()
    workflow.ensure = AsyncMock(return_value=existing)

    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()

    original = module.ExploreProvisioningWorkflow
    module.ExploreProvisioningWorkflow = lambda db: workflow
    user = _user()
    try:
        with (
            patch.object(module, "require_unit_access"),
            patch.object(module, "require_module_unit_scope"),
        ):
            result = await module.put_simulator_explore_carbon_report(
                1, 2024, background_tasks, db, user
            )
        assert result == existing
        background_tasks.add_task.assert_called_once_with(
            module._refresh_explore_background,
            unit_id=1,
            old_report_id=99,
            reference_year=2024,
            created_by=user.id,
        )
    finally:
        module.ExploreProvisioningWorkflow = original
