"""Statement budgets for the hot read endpoints (#2527 tasks 4, 5, 6).

On the dev DB a query costs ~14 ms of network round trip (#2529), so these
endpoints' latency is their statement count times 14 ms. The budgets below
are the guardrail that keeps that count from creeping back up.

Every merged endpoint is asserted twice: once against a ceiling, and once for
**equality between one unit and three**. The ceiling only catches a
regression after someone tunes it; the fan-out equality catches a
loop-over-reports the moment it reappears, and reads unambiguously in CI.

Statements are counted through the real HTTP route on real Postgres —
psycopg3 batches some round trips, so an ORM-level count would lie.

Requires Docker — see this package's ``conftest.py``.
"""

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.core.constants import ModuleStatus
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.unit_user import UnitUser
from app.models.user import RoleName, User, UserProvider
from app.models.year_configuration import YearConfiguration
from tests.integration.statement_budget import count_statements

YEAR = 2025

# Ratchets set at the *exact* counts measured on the fixtures below — no
# headroom on purpose. Slack in a ceiling is room for an N+1 to hide on a small
# fixture, which is the regression these tests exist to catch. Lower one when a
# path gets cheaper; never raise one without a written reason in plan 2527.
#
# The caller is injected via ``dependency_overrides``, so these exclude the
# ``get_current_user`` lookup every authenticated route pays in production —
# add 1 to compare against the plan's tables.
MERGED_REPORT_STATS_BUDGET = 5
MERGED_RESULTS_SUMMARY_BUDGET = 4
MERGED_MULTI_YEAR_BUDGET = 3
WORKSPACE_HOME_BUDGET = 6


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres, with a real seeded caller.

    The caller has to be a real ``User`` row: ``get_user_units`` joins on
    ``unit_users.user_id``, so a mock would resolve to no units and the
    merged endpoints would 404 before issuing the queries under test.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        user = User(
            institutional_id="BUDGET-USER",
            email="budget@example.com",
            display_name="Budget User",
            provider=UserProvider.DEFAULT,
        )
        session.add(user)
        session.add(YearConfiguration(year=YEAR, provider=UserProvider.DEFAULT))
        await session.commit()
        await session.refresh(user)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: user

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr("app.core.policy.require_unit_access", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.api.v1.workspace_home.require_unit_access", lambda *_a, **_k: None
    )

    yield {"factory": factory, "engine": engine, "user": user}

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_units(session, user: User, count: int, *, years=(YEAR,)) -> list[int]:
    """``count`` level-4 units the caller belongs to, each with a report.

    Every report carries one validated module and one in-progress one, so the
    folds that filter on status are actually exercised.

    The caller also gets a ``CO2_USER_STD`` role per unit: ``PlanPolicy``
    reads ``current_user.roles``, not ``unit_users``, so without them workspace
    home 403s on the planner section. Standard rather than superadmin on
    purpose — a global breadth short-circuits ``PlanPolicy.can_view`` and would
    skip the per-plan filtering the merged query has to keep intact.
    """
    unit_ids: list[int] = []
    roles: list[dict] = list(user.roles_raw or [])
    for index in range(count):
        unit = Unit(
            provider=UserProvider.DEFAULT,
            institutional_code=f"BUDGET-{index}",
            institutional_id=f"BUDGET-CF-{index}",
            name=f"Budget Unit {index}",
            level=4,
            is_active=True,
        )
        session.add(unit)
        await session.flush()
        session.add(
            UnitUser(unit_id=unit.id, user_id=user.id, role=RoleName.CO2_USER_STD)
        )
        roles.append(
            {
                "role": RoleName.CO2_USER_STD.value,
                "on": {"kind": "own", "institutional_id": unit.institutional_id},
            }
        )
        project = CarbonProject(
            unit_id=unit.id, carbon_report_type=CarbonReportType.CALCULATOR
        )
        session.add(project)
        await session.flush()
        for year in years:
            report = CarbonReport(
                unit_id=unit.id,
                year=year,
                carbon_project_id=project.id,
                overall_status=ModuleStatus.NOT_STARTED,
                stats={"total": 41700.0, "buckets": {}, "validated_buckets": []},
            )
            session.add(report)
            await session.flush()
            session.add(
                CarbonReportModule(
                    carbon_report_id=report.id,
                    module_type_id=ModuleTypeEnum.equipment.value,
                    status=ModuleStatus.VALIDATED,
                    stats={"total": 41700.0},
                )
            )
            session.add(
                CarbonReportModule(
                    carbon_report_id=report.id,
                    module_type_id=ModuleTypeEnum.professional_travel.value,
                    status=ModuleStatus.IN_PROGRESS,
                    stats={"total": 15000.0},
                )
            )
        unit_ids.append(unit.id)
    await session.commit()
    # The routes read the object ``get_current_user`` is overridden with, so
    # the in-memory assignment is what the policy sees.
    user.roles_raw = roles
    return unit_ids


async def _get(pg_app, url: str) -> tuple[int, object, int]:
    """GET ``url`` through the real ASGI stack; returns (status, body, count)."""
    with count_statements(pg_app["engine"]) as log:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(url)
    print(f"\n>>> GET {url}: {log.breakdown()}\n{log.numbered()}\n")
    assert resp.status_code == 200, resp.text
    return resp.status_code, resp.json(), log.total


def _merged_url(path: str, unit_ids: list[int], *, year: int | None = YEAR) -> str:
    params = "&".join(f"unit_ids={unit_id}" for unit_id in unit_ids)
    if year is not None:
        params += f"&year={year}"
    return f"/v1/modules-stats/{path}?{params}"


@pytest.mark.asyncio
async def test_merged_report_stats_is_constant_in_report_count(pg_app):
    """One statement for every report's validated totals, not two each."""
    async with pg_app["factory"]() as session:
        unit_ids = await _seed_units(session, pg_app["user"], 3)

    _, one_body, one = await _get(
        pg_app, _merged_url("merged/report-stats", unit_ids[:1])
    )
    _, three_body, three = await _get(
        pg_app, _merged_url("merged/report-stats", unit_ids)
    )

    assert three == one, (
        f"merged/report-stats issued {one} statements for 1 unit and {three} for 3 "
        "— the per-report loop is back (#2527 task 4)."
    )
    assert three <= MERGED_REPORT_STATS_BUDGET
    # Three units' worth of validated equipment, summed.
    assert three_body["total_tonnes_validated_co2eq"] == pytest.approx(
        3 * one_body["total_tonnes_validated_co2eq"]
    )


@pytest.mark.asyncio
async def test_merged_results_summary_is_constant_in_report_count(pg_app):
    """Previous year included, still two reads whatever the unit count."""
    async with pg_app["factory"]() as session:
        unit_ids = await _seed_units(session, pg_app["user"], 3, years=(YEAR - 1, YEAR))

    _, _, one = await _get(pg_app, _merged_url("merged/results-summary", unit_ids[:1]))
    _, body, three = await _get(pg_app, _merged_url("merged/results-summary", unit_ids))

    assert three == one, (
        f"merged/results-summary issued {one} statements for 1 unit and {three} for "
        "3 — the per-report loop is back (#2527 task 4)."
    )
    assert three <= MERGED_RESULTS_SUMMARY_BUDGET
    # The in-progress module must not reach the payload, and the validated one
    # must — including its previous-year comparison basis.
    module_ids = {m["module_type_id"] for m in body["module_results"]}
    assert module_ids == {ModuleTypeEnum.equipment.value}
    equipment = body["module_results"][0]
    assert equipment["previous_year_total_tonnes_co2eq"] == pytest.approx(
        equipment["total_tonnes_co2eq"]
    )


@pytest.mark.asyncio
async def test_merged_multi_year_report_stats_holds_at_its_budget(pg_app):
    """Ratchet on the one merged endpoint that was already grouped."""
    async with pg_app["factory"]() as session:
        unit_ids = await _seed_units(session, pg_app["user"], 3, years=(YEAR - 1, YEAR))

    url = "merged/multi-year-report-stats"
    _, _, one = await _get(pg_app, _merged_url(url, unit_ids[:1], year=None))
    _, _, three = await _get(pg_app, _merged_url(url, unit_ids, year=None))

    assert three == one
    assert three <= MERGED_MULTI_YEAR_BUDGET


@pytest.mark.asyncio
async def test_workspace_home_statement_budget(pg_app):
    """The fattest single read in the app — every workspace page load pays it."""
    async with pg_app["factory"]() as session:
        unit_ids = await _seed_units(session, pg_app["user"], 1)

    _, body, total = await _get(pg_app, f"/v1/workspace/{unit_ids[0]}/{YEAR}/home")

    assert total <= WORKSPACE_HOME_BUDGET, (
        f"workspace home issued {total} statements, budget is "
        f"{WORKSPACE_HOME_BUDGET} (#2527 task 5)."
    )
    # One read serves both consumers, so the status filter lives in the fold:
    # the sidebar keeps the in-progress module while the headline counts only
    # the validated one. Pushing that filter into the WHERE clause would empty
    # the sidebar silently.
    assert {state["module_type_id"] for state in body["module_states"]} == {
        ModuleTypeEnum.equipment.value,
        ModuleTypeEnum.professional_travel.value,
    }
    assert body["stats"]["total_tonnes_validated_co2eq"] == pytest.approx(41.7)
