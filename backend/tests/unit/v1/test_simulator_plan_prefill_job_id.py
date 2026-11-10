"""GET on a plan reports its unfinished prefill job (#2778).

Only the PATCH that queued the ``simulator_plan_prefill`` job used to return
its id, so a reloaded planner lost track of it, hid the "prefill running"
banner and let the user edit years the job was about to wipe and rebuild.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import RoleName, UserProvider


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def plans(db_session, make_unit, make_user):
    """Two plans of one unit, viewed by a principal of that unit."""
    unit = await make_unit(db_session, level=4, name="Lab-A")
    user = await make_user(
        db_session,
        roles_raw=[
            {
                "role": RoleName.CO2_USER_PRINCIPAL.value,
                "on": {"kind": "unit", "institutional_id": unit.institutional_id},
            }
        ],
    )
    projects = [
        CarbonProject(
            unit_id=unit.id,
            carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
            name=name,
            created_by=user.id,
        )
        for name in ("proj", "other-proj")
    ]
    db_session.add_all(projects)
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[deps_module.get_db] = _override_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    return projects


async def _add_prefill_job(
    db_session,
    plan_id: int,
    state: IngestionState,
    result: IngestionResult | None = None,
) -> int:
    job = DataIngestionJob(
        job_type="simulator_plan_prefill",
        ingestion_method=IngestionMethod.computed,
        target_type=TargetType.DATA_ENTRIES,
        entity_type=EntityType.GLOBAL_PER_YEAR,
        state=state,
        result=result,
        provider=UserProvider.DEFAULT,
        meta={"config": {"plan_id": plan_id, "report_ids": [1]}},
    )
    db_session.add(job)
    await db_session.commit()
    if job.id is None:
        raise ValueError("job was not persisted")
    return job.id


@pytest.mark.parametrize("state", [IngestionState.NOT_STARTED, IngestionState.RUNNING])
async def test_get_plan_returns_the_unfinished_prefill_job(
    client, plans, db_session, state
):
    plan = plans[0]
    job_id = await _add_prefill_job(db_session, plan.id, state)

    response = client.get(f"/api/v1/project-plans/{plan.id}")

    assert response.status_code == 200, response.text
    assert response.json()["prefill_job_id"] == job_id


async def test_get_plan_ignores_a_finished_prefill_job(client, plans, db_session):
    plan = plans[0]
    await _add_prefill_job(
        db_session, plan.id, IngestionState.FINISHED, IngestionResult.SUCCESS
    )

    response = client.get(f"/api/v1/project-plans/{plan.id}")

    assert response.status_code == 200, response.text
    assert response.json()["prefill_job_id"] is None


async def test_get_plan_ignores_another_plans_prefill_job(client, plans, db_session):
    plan, other_plan = plans
    await _add_prefill_job(db_session, other_plan.id, IngestionState.RUNNING)

    response = client.get(f"/api/v1/project-plans/{plan.id}")

    assert response.status_code == 200, response.text
    assert response.json()["prefill_job_id"] is None
