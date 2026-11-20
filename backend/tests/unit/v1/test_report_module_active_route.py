"""The Active toggle applies to Simulator plans only (code-scanning 1379).

On a Calculator report, switching a module off would drop it from the
unit's totals, so the route refuses before touching the module.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report as route_module
from app.schemas.carbon_report import CarbonReportModuleActiveUpdate


def _patch(monkeypatch, carbon_project_id):
    report = SimpleNamespace(id=1, carbon_project_id=carbon_project_id)
    report_service = MagicMock()
    report_service.get = AsyncMock(return_value=report)
    report_service.recompute_report_stats = AsyncMock()
    report_service.recompute_report_progress = AsyncMock()
    module_service = MagicMock()
    module_service.update_is_active = AsyncMock(return_value={"is_active": False})
    monkeypatch.setattr(route_module, "CarbonReportService", lambda db: report_service)
    monkeypatch.setattr(
        route_module, "CarbonReportModuleService", lambda db: module_service
    )
    monkeypatch.setattr(route_module, "require_report_access", AsyncMock())
    return module_service


async def _toggle():
    db = MagicMock()
    db.commit = AsyncMock()
    return await route_module.update_carbon_report_module_active(
        carbon_report_id=1,
        module_type_id=1,
        update=CarbonReportModuleActiveUpdate(is_active=False),
        db=db,
        current_user=MagicMock(),
    )


async def test_calculator_report_refuses_active_toggle(monkeypatch):
    module_service = _patch(monkeypatch, carbon_project_id=None)
    with pytest.raises(HTTPException) as exc:
        await _toggle()
    assert exc.value.status_code == 409
    module_service.update_is_active.assert_not_called()


async def test_plan_report_still_toggles_active(monkeypatch):
    module_service = _patch(monkeypatch, carbon_project_id=7)
    result = await _toggle()
    assert result == {"is_active": False}
    module_service.update_is_active.assert_awaited_once_with(1, 1, False)
