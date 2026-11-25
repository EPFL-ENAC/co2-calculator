"""The Active toggle applies to Simulator plans only (code-scanning 1379).

On a Calculator report, switching a module off would drop it from the
unit's totals, so the route refuses before touching the module. Calculator
reports also belong to a CarbonProject, so the route must check the
project's type, not only that a project exists.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report as route_module
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.schemas.carbon_report import CarbonReportModuleActiveUpdate
from app.services.carbon_report_service import CarbonReportService


@pytest.fixture
def module_service(monkeypatch):
    service = MagicMock()
    service.update_is_active = AsyncMock(return_value={"is_active": False})
    monkeypatch.setattr(route_module, "CarbonReportModuleService", lambda db: service)
    monkeypatch.setattr(route_module, "require_report_access", AsyncMock())
    monkeypatch.setattr(CarbonReportService, "recompute_report_stats", AsyncMock())
    monkeypatch.setattr(CarbonReportService, "recompute_report_progress", AsyncMock())
    return service


async def _report(db_session, make_unit, make_carbon_report, report_type):
    unit = await make_unit(db_session)
    project_id = None
    if report_type is not None:
        project = CarbonProject(unit_id=unit.id, carbon_report_type=report_type)
        db_session.add(project)
        await db_session.flush()
        project_id = project.id
    return await make_carbon_report(
        db_session, unit_id=unit.id, carbon_project_id=project_id
    )


async def _toggle(db_session, report_id):
    return await route_module.update_carbon_report_module_active(
        carbon_report_id=report_id,
        module_type_id=1,
        update=CarbonReportModuleActiveUpdate(is_active=False),
        db=db_session,
        current_user=MagicMock(),
    )


@pytest.mark.parametrize("report_type", [CarbonReportType.CALCULATOR, None])
async def test_non_plan_report_refuses_active_toggle(
    db_session, make_unit, make_carbon_report, module_service, report_type
):
    report = await _report(db_session, make_unit, make_carbon_report, report_type)
    with pytest.raises(HTTPException) as exc:
        await _toggle(db_session, report.id)
    assert exc.value.status_code == 409
    module_service.update_is_active.assert_not_called()


async def test_plan_report_toggles_active(
    db_session, make_unit, make_carbon_report, module_service
):
    report = await _report(
        db_session, make_unit, make_carbon_report, CarbonReportType.SIMULATOR_PLAN
    )
    result = await _toggle(db_session, report.id)
    assert result == {"is_active": False}
    module_service.update_is_active.assert_awaited_once_with(report.id, 1, False)
