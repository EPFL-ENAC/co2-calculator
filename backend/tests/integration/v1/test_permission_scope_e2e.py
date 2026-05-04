"""End-to-end permission-scope tests for unit-scoped module routes.

Unlike ``test_headcount_members_permission.py`` (which mocks
``get_module_permission_decision`` to isolate the route logic), these tests
exercise the FULL permission chain in one go:

    request
      → route
        → _check_module_permission_for_unit / get_module_permission_decision
          → check_module_permission
            → query_policy
              → _evaluate_permission_policy
                → has_permission
                  ↑ matched against ↑
    calculate_user_permissions(user.roles)

This is the chain PR #974 broke: keys were stored as
``modules.X/{institutional_id}`` but every gate looked up bare ``modules.X``.
A test of this shape would have caught the regression — these are the tests
that pin the chain back together.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.user import GlobalScope, Role, RoleName, RoleScope

UNIT_IID = "0184"
OTHER_IID = "9999"

_ALL_MEMBERS = [
    {"institutional_id": "11111", "name": "Alice"},
    {"institutional_id": "22222", "name": "Bob"},
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Make sure no test leaks dependency overrides into the next."""
    yield
    app.dependency_overrides.clear()


def _user(institutional_id: str, roles: list) -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = institutional_id
    u.roles = roles
    return u


def _principal(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id=iid))


def _std(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id=iid))


def _backoffice() -> Role:
    return Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())


def _superadmin() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _wire(monkeypatch, user, unit_iid: str = UNIT_IID) -> None:
    """Wire dependency overrides + service stubs.

    Crucially, ``get_module_permission_decision`` is NOT patched — the real
    policy chain runs. Only the data layer (Unit fetch, DataEntryService,
    carbon-report id lookup) is stubbed so the test stays in-process.
    """
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    mock_unit = MagicMock()
    mock_unit.institutional_id = unit_iid

    async def mock_get_db():
        db = MagicMock()
        db.get = AsyncMock(return_value=mock_unit)
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db

    mock_service = MagicMock()

    async def mock_get_members(carbon_report_module_id):
        return list(_ALL_MEMBERS)

    async def mock_get_member_by_iid(carbon_report_module_id, institutional_id):
        return next(
            (m for m in _ALL_MEMBERS if m["institutional_id"] == institutional_id),
            None,
        )

    mock_service.get_headcount_members = mock_get_members
    mock_service.get_member_by_institutional_id = mock_get_member_by_iid
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.DataEntryService", lambda db: mock_service
    )
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.get_carbon_report_id",
        AsyncMock(return_value=1),
    )


URL = "/api/v1/modules/1/2024/headcount/members"


class TestPermissionScopeEndToEnd:
    def test_principal_on_target_unit_passes(self, client, monkeypatch):
        """principal/0184 hitting unit-with-iid-0184 → 200 (full list).
        Pins the bug fix: bare-path lookup would have returned 403."""
        user = _user("11111", [_principal(UNIT_IID)])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2

    def test_principal_on_other_unit_denied(self, client, monkeypatch):
        """principal/0184 hitting unit-with-iid-9999 → 403. Pins scope
        enforcement: PR #974 explicitly tightened this."""
        user = _user("11111", [_principal(UNIT_IID)])
        _wire(monkeypatch, user, unit_iid=OTHER_IID)
        r = client.get(URL)
        assert r.status_code == 403, r.text

    def test_std_passes_via_travel_view_on_their_unit(self, client, monkeypatch):
        """Std user has only travel + cloud_and_ai, no headcount. The
        list_headcount_members gate accepts when travel.view passes; data
        layer narrows the result to the user's own record."""
        user = _user("11111", [_std(UNIT_IID)])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 1
        assert data[0]["institutional_id"] == "11111"

    def test_std_on_other_unit_denied(self, client, monkeypatch):
        user = _user("11111", [_std(UNIT_IID)])
        _wire(monkeypatch, user, unit_iid=OTHER_IID)
        r = client.get(URL)
        assert r.status_code == 403, r.text

    def test_no_roles_denied(self, client, monkeypatch):
        user = _user("11111", roles=[])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 403, r.text

    def test_backoffice_metier_passes_via_global_bypass(self, client, monkeypatch):
        """Backoffice metier has ``GlobalScope`` and no ``modules.*`` perms.
        The route's ``is_global`` escape hatch lets them through."""
        user = _user("11111", [_backoffice()])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2

    def test_superadmin_passes_via_global_bypass(self, client, monkeypatch):
        user = _user("11111", [_superadmin()])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2

    def test_principal_other_unit_with_std_on_target_unit(self, client, monkeypatch):
        """User is principal/9999 AND std/0184. Hitting unit-iid-0184:
          - the gate passes via std's travel.view
          - data-level check resolves to std for this unit (role priority),
            so only the user's own record is returned.
        Verifies that scope-blind acceptance does NOT happen — without
        the iid forwarding, the principal/9999 role would have falsely
        granted full headcount access on unit 0184."""
        user = _user("11111", [_principal(OTHER_IID), _std(UNIT_IID)])
        _wire(monkeypatch, user, unit_iid=UNIT_IID)
        r = client.get(URL)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 1
        assert data[0]["institutional_id"] == "11111"
