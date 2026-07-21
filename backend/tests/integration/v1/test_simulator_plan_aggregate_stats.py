"""Integration tests for the plan-wide stats aggregate (#1858).

The Project Planner results card shows one headline total and one chart for
the whole Year Selection range, so the endpoint has to sum every plan-year
report's persisted stats. These tests pin that the sum is arithmetic, that a
year whose report was never computed does not poison it, and that an empty
range still answers with a usable zero payload rather than a 404.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.core.constants import ModuleStatus
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum
from app.models.user import RoleName

EQUIPMENT = ModuleTypeEnum.equipment.value
EMISSION_ID = str(EmissionType.food.value)


def report_stats(total_kg: float, fte: float) -> dict:
    """A persisted carbon_report.stats payload with one populated bucket."""
    return {
        "buckets": {
            "equipment": {
                "scope": 2,
                "additional": False,
                "total_kg": total_kg,
                "by_emission_type": {EMISSION_ID: total_kg},
                "by_additional_value": {},
            }
        },
        "validated_buckets": ["equipment"],
        "total": total_kg,
        "validated_total": total_kg,
        "total_fte": fte,
        "by_emission_type": {EMISSION_ID: total_kg},
        "by_additional_value": {},
        "entry_count": 1,
    }


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def plan_workspace(
    db_session,
    make_unit,
    make_user,
    make_carbon_report,
    make_carbon_report_module,
):
    """A plan over 2026-2028 whose middle year has no computed stats."""
    unit = await make_unit(db_session, level=4, name="Lab-A")
    # require_unit_access walks the user's roles, not the unit_users table.
    user = await make_user(
        db_session,
        roles_raw=[
            {
                "role": RoleName.CO2_USER_PRINCIPAL.value,
                "on": {"kind": "unit", "institutional_id": unit.institutional_id},
            }
        ],
    )

    async def _make_plan(name: str, years: list[tuple[int, dict | None]]):
        project = CarbonProject(
            unit_id=unit.id,
            carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
            name=name,
            start_year=years[0][0] if years else None,
            end_year=years[-1][0] if years else None,
            created_by=user.id,
        )
        db_session.add(project)
        await db_session.flush()
        for year, stats in years:
            report = await make_carbon_report(
                db_session,
                unit_id=unit.id,
                year=year,
                carbon_project_id=project.id,
                stats=stats,
            )
            await make_carbon_report_module(
                db_session,
                carbon_report_id=report.id,
                module_type_id=EQUIPMENT,
                status=ModuleStatus.IN_PROGRESS,
                stats={"total": (stats or {}).get("total", 0.0)},
            )
        return project

    plan = await _make_plan(
        "proj",
        [
            (2026, report_stats(1000.0, 10.0)),
            (2027, None),
            (2028, report_stats(3000.0, 5.0)),
        ],
    )
    empty_plan = await _make_plan("empty-proj", [])
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[deps_module.get_db] = _override_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    return {"user": user, "unit": unit, "plan": plan, "empty_plan": empty_plan}


async def test_aggregate_stats_sums_plan_years(client, plan_workspace):
    plan_id = plan_workspace["plan"].id

    response = client.get(f"/api/v1/project-plans/{plan_id}/aggregate-stats")

    assert response.status_code == 200, response.text
    payload = response.json()
    # 2027 has no stats yet and contributes nothing rather than breaking the sum.
    assert payload["total"] == 4000.0
    assert payload["total_fte"] == 15.0
    assert payload["buckets"]["equipment"]["total_kg"] == 4000.0
    assert payload["buckets"]["equipment"]["by_emission_type"][EMISSION_ID] == 4000.0
    assert payload["scope2"] == 4000.0


async def test_aggregate_stats_empty_range_is_zero_shaped(client, plan_workspace):
    """A plan with no year sections answers 200 with an empty payload."""
    plan_id = plan_workspace["empty_plan"].id

    response = client.get(f"/api/v1/project-plans/{plan_id}/aggregate-stats")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["buckets"] == {}
    assert payload["total"] == 0.0
    assert payload["total_fte"] == 0.0


async def test_aggregate_stats_unknown_plan_is_404(client, plan_workspace):
    response = client.get("/api/v1/project-plans/999999/aggregate-stats")

    assert response.status_code == 404, response.text
