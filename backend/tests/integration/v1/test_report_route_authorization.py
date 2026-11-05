"""Every report- or item-addressed route refuses a caller outside its scope (#3185).

The routes are enumerated from the app, so a new route that takes
``{carbon_report_id}`` or ``{item_id}`` is covered the day it lands. Real
routes, real policy chain, real SQL on an in-memory database: only the
caller is injected. A route that can't refuse must be gated, or listed in
``EXEMPT`` with its reason.
"""

import httpx
import pytest
from fastapi.routing import iter_route_contexts
from sqlalchemy import event

import app.api.deps as deps_module
from app.main import app
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from tests.browser import SAME_ORIGIN_HEADERS
from tests.integration.v1.test_unit_gating_e2e import (
    USER_IID,
    _principal,
    _user,
)
from tests.unit.v1.test_temp_upload_auth_ordering import valid_access_token

UNIT_A_IID = "CF-A"
UNIT_B_IID = "CF-B"
REFUSED = {403, 404}
MEMBER = {
    "name": "A member",
    "fte": 1.0,
    "sius_code": "BG",
    "user_institutional_id": "1",
}

# Route path (as declared, method-prefixed) -> reason it needs no gate.
EXEMPT: dict[str, str] = {}

# Minimal valid bodies, so body validation (422) can't stand in for a refusal.
BODIES = {
    "status": {"status": 1},
    "active": {"is_active": True},
    "budget": {"budget": 1.0},
    "reference-percentage": {"percentage": 10.0},
    "reset": None,
}
QUERY = {"check-unique": {"field": "name", "value": "x"}}


def _addressed_routes() -> list[tuple[str, str]]:
    routes = []
    for ctx in iter_route_contexts(app.routes):
        path = ctx.path
        if "{carbon_report_id}" not in path and "{item_id}" not in path:
            continue
        for method in sorted(ctx.route.methods or []):
            if f"{method} {path}" not in EXEMPT:
                routes.append((method, path))
    return routes


ROUTES = _addressed_routes()


def _fill(path: str, report_id: int, item_id: int) -> str:
    return (
        path.replace("{carbon_report_id}", str(report_id))
        .replace("{module_id}", "headcount")
        .replace("{module_type_id}", str(ModuleTypeEnum.headcount.value))
        .replace("{submodule_id}", "member")
        .replace("{item_id}", str(item_id))
    )


def _body(path: str) -> dict | None:
    leaf = path.rstrip("/").rsplit("/", 1)[-1]
    if leaf == "budget" and "{module_type_id}" in path:
        return {"submodule": "member", "budget": 1.0}
    if leaf in BODIES:
        return BODIES[leaf]
    return MEMBER


@pytest.fixture
async def world(
    db_session,
    make_unit,
    make_carbon_report,
    make_carbon_report_module,
    make_data_entry,
):
    """Two units, each with a report, two modules and one headcount entry."""
    ids = {}
    for key, iid in (("a", UNIT_A_IID), ("b", UNIT_B_IID)):
        unit = await make_unit(db_session, institutional_id=iid)
        report = await make_carbon_report(db_session, unit_id=unit.id)
        module = await make_carbon_report_module(
            db_session,
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.headcount.value,
        )
        await make_carbon_report_module(
            db_session,
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.professional_travel.value,
        )
        entry = await make_data_entry(
            db_session,
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            data=MEMBER,
        )
        ids[key] = {"report": report.id, "module": module.id, "entry": entry.id}
    await db_session.commit()
    return ids


@pytest.fixture
async def call(db_session):
    """Send one request as ``user`` against the seeded session."""

    async def _get_db():
        yield db_session

    app.dependency_overrides[deps_module.get_db] = _get_db
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver/api",
        cookies={"auth_token": valid_access_token()},
        headers=SAME_ORIGIN_HEADERS,
    ) as client:

        async def _send(user, method: str, path: str, report_id: int, item_id: int):
            app.dependency_overrides[deps_module.get_current_user] = lambda: user
            url = _fill(path, report_id, item_id)
            return await client.request(
                method,
                url,
                json=_body(path) if method in ("POST", "PATCH") else None,
                params=QUERY.get(path.rsplit("/", 1)[-1]),
            )

        yield _send
    app.dependency_overrides.clear()


def _caller(role):
    """A user mock complete enough for routes that validate it as UserRead."""
    u = _user(USER_IID, [role])
    u.display_name = "A unit member"
    u.last_login = None
    u.provider = UserProvider.DEFAULT
    return u


def _member_of_a():
    return _caller(_principal(UNIT_A_IID))


def test_guard_found_the_routes():
    """An empty enumeration would pass every case below vacuously."""
    assert len(ROUTES) >= 20


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_other_units_report_is_refused(world, call, method, path):
    b = world["b"]
    r = await call(_member_of_a(), method, path, b["report"], b["entry"])
    assert r.status_code in REFUSED, f"{method} {path}: {r.status_code} {r.text}"


ITEM_ROUTES = [(m, p) for m, p in ROUTES if p.endswith("{item_id}")]


@pytest.mark.parametrize(("method", "path"), ITEM_ROUTES)
async def test_entry_is_reachable_only_through_its_own_module(
    world, call, db_session, method, path
):
    """An entry answers only under the module that holds it."""
    a, b = world["a"], world["b"]
    r = await call(_member_of_a(), method, path, a["report"], b["entry"])
    assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"

    db_session.expire_all()
    row = await db_session.get(DataEntry, b["entry"])
    assert row is not None
    assert row.carbon_report_module_id == b["module"]
    assert row.data == MEMBER


READ_ROUTES = [(m, p) for m, p in ROUTES if m == "GET"]


@pytest.mark.parametrize(("method", "path"), READ_ROUTES)
async def test_owning_unit_is_not_refused(world, call, method, path):
    """Positive control: the rig refuses on who calls, not on everyone."""
    b = world["b"]
    r = await call(
        _caller(_principal(UNIT_B_IID)), method, path, b["report"], b["entry"]
    )
    assert r.status_code not in REFUSED, f"{method} {path}: {r.status_code}"


# Statements per request on SQLite. Dev before #3185 in brackets: the gate
# adds primary-key reads of the report, unit and project, nothing else.
ITEM_PATH = (
    "/v1/carbon-reports/{carbon_report_id}/modules/{module_id}/{submodule_id}/{item_id}"
)
STATEMENT_BUDGET = {
    "/v1/carbon-reports/{carbon_report_id}": 4,  # (3)
    "/v1/carbon-reports/{carbon_report_id}/modules/": 4,  # (3)
    ITEM_PATH: 6,  # (6)
    "/v1/modules-stats/{carbon_report_id}/report-stats": 5,  # (3)
    "/v1/modules-stats/{carbon_report_id}/results-summary": 6,  # (3)
    "/v1/modules-stats/{carbon_report_id}/validated-totals": 5,  # (2)
}


@pytest.mark.parametrize("path", sorted(STATEMENT_BUDGET))
async def test_gated_read_stays_in_statement_budget(world, call, db_session, path):
    statements = []

    def _count(*_args, **_kwargs):
        statements.append(1)

    engine = db_session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", _count)
    b = world["b"]
    try:
        r = await call(
            _caller(_principal(UNIT_B_IID)), "GET", path, b["report"], b["entry"]
        )
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    assert r.status_code == 200, r.text
    assert len(statements) <= STATEMENT_BUDGET[path]
