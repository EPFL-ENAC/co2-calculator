"""Integration tests for the combined-units Results endpoints (#385).

The Results page sums several units' carbon reports into one view. These tests
pin the three properties that make that safe:

* the merged payloads equal the arithmetic sum of the single-unit ones;
* the IT top-class detail is re-ranked across units rather than dropped
  (``merge_report_stats`` deliberately discards it, so the endpoint has to put
  it back);
* a unit the caller cannot reach yields 404, never 403 — the frontend turns any
  403 into a hard redirect to /unauthorized.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.core.constants import ModuleStatus
from app.main import app
from app.models.data_entry import DataEntryTypeEnum
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
def policy_allow(monkeypatch):
    async def _mock(*args, **kwargs):
        return {"allow": True, "filters": {}}

    monkeypatch.setattr("app.services.unit_service.query_policy", _mock)


@pytest.fixture
async def workspace(
    db_session,
    make_unit,
    make_user,
    make_unit_user,
    make_carbon_report,
    make_carbon_report_module,
    make_data_entry,
    make_data_entry_emission,
):
    """Two reachable level-4 units with equipment data, and one unreachable."""
    user = await make_user(db_session)
    units = {}
    reports = {}

    async def _seed_unit(name: str, total_kg: float, fte: float, reachable: bool):
        unit = await make_unit(db_session, level=4, name=name)
        if reachable:
            await make_unit_user(
                db_session,
                unit_id=unit.id,
                user_id=user.id,
                role=RoleName.CO2_USER_PRINCIPAL,
            )
        report = await make_carbon_report(
            db_session, unit_id=unit.id, year=2026, stats=report_stats(total_kg, fte)
        )
        module = await make_carbon_report_module(
            db_session,
            carbon_report_id=report.id,
            module_type_id=EQUIPMENT,
            status=ModuleStatus.VALIDATED,
            stats={"total": total_kg},
        )
        entry = await make_data_entry(
            db_session,
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            data={"equipment_class": "Server"},
        )
        await make_data_entry_emission(
            db_session, data_entry_id=entry.id, kg_co2eq=total_kg
        )
        units[name] = unit
        reports[name] = report

    await _seed_unit("Lab-A", 1000.0, 10.0, reachable=True)
    await _seed_unit("Lab-B", 3000.0, 5.0, reachable=True)
    await _seed_unit("Lab-Forbidden", 9999.0, 1.0, reachable=False)
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[deps_module.get_db] = _override_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    return {"user": user, "units": units, "reports": reports}


async def test_merged_report_stats_sums_units(client, workspace, policy_allow):
    unit_ids = [workspace["units"]["Lab-A"].id, workspace["units"]["Lab-B"].id]

    response = client.get(
        "/api/v1/modules-stats/merged/report-stats",
        params={"unit_ids": unit_ids, "year": 2026},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 4000.0
    assert payload["total_fte"] == 15.0
    assert payload["buckets"]["equipment"]["total_kg"] == 4000.0
    assert payload["scope2"] == 4000.0
    # Validated headline is summed across the reports, not taken from one.
    assert payload["total_tonnes_validated_co2eq"] == pytest.approx(4.0)


async def test_merged_report_stats_reranks_it_top_classes(
    client, workspace, policy_allow
):
    """merge_report_stats drops top_class_detail; the endpoint must restore it."""
    unit_ids = [workspace["units"]["Lab-A"].id, workspace["units"]["Lab-B"].id]

    response = client.get(
        "/api/v1/modules-stats/merged/report-stats",
        params={"unit_ids": unit_ids, "year": 2026},
    )

    assert response.status_code == 200, response.text
    top_class_detail = response.json()["it"]["top_class_detail"]
    assert top_class_detail, "IT top-class detail must survive the merge"

    equipment_rows = top_class_detail["equipment_it"]
    # Both units contribute the same class, so it ranks once at their sum.
    server_values = [
        child["value"]
        for row in equipment_rows
        for child in row["children"]
        if child["name"] == "Server"
    ]
    assert server_values == [pytest.approx(4000.0)]


async def test_merged_results_summary_equals_sum_of_singles(
    client, workspace, policy_allow
):
    unit_ids = [workspace["units"]["Lab-A"].id, workspace["units"]["Lab-B"].id]

    merged = client.get(
        "/api/v1/modules-stats/merged/results-summary",
        params={"unit_ids": unit_ids, "year": 2026},
    )
    assert merged.status_code == 200, merged.text

    singles = [
        client.get(
            f"/api/v1/modules-stats/{workspace['reports'][name].id}/results-summary"
        ).json()
        for name in ("Lab-A", "Lab-B")
    ]

    merged_total = merged.json()["unit_totals"]["total_tonnes_co2eq"]
    assert merged_total == pytest.approx(
        sum(single["unit_totals"]["total_tonnes_co2eq"] for single in singles)
    )


async def test_unreachable_unit_yields_404_not_403(client, workspace, policy_allow):
    """A 403 here would hard-redirect the SPA to /unauthorized."""
    unit_ids = [
        workspace["units"]["Lab-A"].id,
        workspace["units"]["Lab-Forbidden"].id,
    ]

    response = client.get(
        "/api/v1/modules-stats/merged/report-stats",
        params={"unit_ids": unit_ids, "year": 2026},
    )

    assert response.status_code == 404


async def test_merged_route_wins_over_carbon_report_id_route(
    client, workspace, policy_allow
):
    """`/merged/report-stats` must not be parsed as carbon_report_id="merged"."""
    response = client.get(
        "/api/v1/modules-stats/merged/report-stats",
        params={"unit_ids": [workspace["units"]["Lab-A"].id], "year": 2026},
    )

    assert response.status_code != 422
    assert response.status_code == 200


async def test_units_without_a_report_for_the_year_are_skipped(
    client, workspace, policy_allow
):
    unit_ids = [workspace["units"]["Lab-A"].id, workspace["units"]["Lab-B"].id]

    response = client.get(
        "/api/v1/modules-stats/merged/report-stats",
        params={"unit_ids": unit_ids, "year": 2023},
    )

    assert response.status_code == 404
