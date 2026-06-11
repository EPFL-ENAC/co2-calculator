"""Integration test for #930 — GET /api/v1/users/units returns only level-4 units.

Wires a real (in-memory SQLite) session through the FastAPI dependency override,
seeds a user with roles on units across levels 2, 3, 4, and asserts the
endpoint only returns the level-4 lab. Documents the contract the workspace
LabSelector relies on.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.user import RoleName


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
    """Patch query_policy at the unit_service binding site (no filters, allow)."""

    async def _mock(*args, **kwargs):
        return {"allow": True, "filters": {}}

    monkeypatch.setattr("app.services.unit_service.query_policy", _mock)


async def test_users_units_endpoint_filters_to_level_4(
    client,
    db_session,
    make_unit,
    make_user,
    make_unit_user,
    policy_allow,
):
    """End-to-end: user with roles across levels 2/3/4 only sees the level-4 lab."""
    user = await make_user(db_session)
    unit_l2 = await make_unit(db_session, level=2, name="Faculty-930")
    unit_l3 = await make_unit(db_session, level=3, name="Institute-930")
    unit_l4 = await make_unit(db_session, level=4, name="Lab-930")
    for unit in (unit_l2, unit_l3, unit_l4):
        await make_unit_user(
            db_session,
            unit_id=unit.id,
            user_id=user.id,
            role=RoleName.CO2_USER_PRINCIPAL,
        )

    async def _override_db():
        yield db_session

    app.dependency_overrides[deps_module.get_db] = _override_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    response = client.get("/api/v1/users/units")

    assert response.status_code == 200
    payload = response.json()
    # Response schema (UnitWithUserRole) does not expose `level`; assert by
    # unit name — the seeded names are unique per level above.
    names = [row["name"] for row in payload]
    assert names == ["Lab-930"]
