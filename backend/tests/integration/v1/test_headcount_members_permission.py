"""Integration tests for headcount members endpoint permission and data-filtering.

Tests the fix for issue #698:
- Professional Travel users can access the endpoint (not redirected to /unauthorized)
- Data-level filtering is UNIT-SCOPE-AWARE (fixes guilbep's role priority concern):
  * Principal for THIS unit → full list
  * Principal for ANOTHER unit + STD for THIS unit → own record only
  * STD for this unit only → own record only
  * Global role (superadmin/backoffice) → full list
- Users without either permission get 403
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.user import GlobalScope, Role, RoleName, RoleScope


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


UNIT_IID = "10208"  # institutional_id of the unit being accessed
OTHER_UNIT_IID = "99999"  # some other unit

ALL_MEMBERS = [
    {"institutional_id": "11111", "name": "Alice"},
    {"institutional_id": "22222", "name": "Bob"},
]


def _make_user(institutional_id: str, roles: list) -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.institutional_id = institutional_id
    user.roles = roles
    return user


def _principal_role(unit_iid: str) -> Role:
    return Role(
        role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id=unit_iid)
    )


def _std_role(unit_iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id=unit_iid))


def _global_role() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _wire(monkeypatch, module, user, decision_fn, unit_institutional_id=UNIT_IID):
    """Wire dependency overrides and service mocks for a test."""

    # Use FastAPI's dependency override mechanism for get_current_user
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.get_module_permission_decision",
        decision_fn,
    )

    mock_unit = MagicMock()
    mock_unit.institutional_id = unit_institutional_id
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.get_carbon_report_id",
        AsyncMock(return_value=1),
    )

    mock_service = MagicMock()

    async def mock_get_members(carbon_report_module_id):
        return list(ALL_MEMBERS)

    async def mock_get_member_by_iid(carbon_report_module_id, institutional_id):
        return next(
            (m for m in ALL_MEMBERS if m["institutional_id"] == institutional_id),
            None,
        )

    mock_service.get_headcount_members = mock_get_members
    mock_service.get_member_by_institutional_id = mock_get_member_by_iid
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.DataEntryService", lambda db: mock_service
    )

    async def mock_get_db():
        db = MagicMock()
        db.get = AsyncMock(return_value=mock_unit)
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db


async def _allow_travel_only(user, module_id, action):
    return {"allow": module_id == "professional-travel"}


async def _allow_headcount_only(user, module_id, action):
    return {"allow": module_id == "headcount"}


async def _allow_all(user, module_id, action):
    return {"allow": True}


async def _deny_all(user, module_id, action):
    return {"allow": False}


# ── Access gate ──────────────────────────────────────────────────────────────


def test_403_when_no_relevant_permission(client, monkeypatch):
    """User without headcount.view or professional_travel.view is denied."""
    import app.api.v1.carbon_report_module as module

    user = _make_user("11111", [_std_role(UNIT_IID)])
    _wire(monkeypatch, module, user, _deny_all)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 403
        assert "Permission denied" in r.json()["detail"]
    finally:
        app.dependency_overrides = {}
        app.dependency_overrides.clear()


# ── Data-level scope ─────────────────────────────────────────────────────────


def test_principal_for_this_unit_sees_all_members(client, monkeypatch):
    """CO2_USER_PRINCIPAL scoped to the accessed unit gets the full list."""
    import app.api.v1.carbon_report_module as module

    user = _make_user("11111", [_principal_role(UNIT_IID)])
    _wire(monkeypatch, module, user, _allow_headcount_only)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 200
        assert len(r.json()) == 2
    finally:
        app.dependency_overrides = {}
        app.dependency_overrides.clear()


def test_std_for_this_unit_sees_only_own_record(client, monkeypatch):
    """CO2_USER_STD scoped to the accessed unit sees only their own record."""
    import app.api.v1.carbon_report_module as module

    user = _make_user("11111", [_std_role(UNIT_IID)])
    _wire(monkeypatch, module, user, _allow_travel_only)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["institutional_id"] == "11111"
    finally:
        app.dependency_overrides = {}
        app.dependency_overrides.clear()


def test_principal_for_other_unit_sees_only_own_record(client, monkeypatch):
    """Principal of unit A accessing unit B sees only their own record
    (role priority fix)."""
    import app.api.v1.carbon_report_module as module

    # User is principal for OTHER_UNIT, only STD for UNIT_IID
    user = _make_user(
        "11111",
        [_principal_role(OTHER_UNIT_IID), _std_role(UNIT_IID)],
    )
    # headcount_decision would be True from the principal role (scope-blind check),
    # but data filter must use the unit-scoped role — which is STD here.
    _wire(monkeypatch, module, user, _allow_headcount_only)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["institutional_id"] == "11111"
    finally:
        app.dependency_overrides.clear()


def test_global_role_sees_all_members(client, monkeypatch):
    """Superadmin (global scope) always gets the full member list."""
    import app.api.v1.carbon_report_module as module

    user = _make_user("11111", [_global_role()])
    _wire(monkeypatch, module, user, _allow_all)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 200
        assert len(r.json()) == 2
    finally:
        app.dependency_overrides = {}
        app.dependency_overrides.clear()


def test_travel_user_not_in_headcount_gets_empty_list(client, monkeypatch):
    """Travel-only user whose institutional_id is absent from headcount gets []."""
    import app.api.v1.carbon_report_module as module

    user = _make_user("99999", [_std_role(UNIT_IID)])
    _wire(monkeypatch, module, user, _allow_travel_only)
    try:
        r = client.get("/api/v1/modules/1/2024/headcount/members")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        app.dependency_overrides.clear()
