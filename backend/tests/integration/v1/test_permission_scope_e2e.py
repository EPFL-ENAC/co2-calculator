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

import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.unit import Unit
from app.models.user import (
    AffiliationScope,
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    UnitScope,
    calculate_user_permissions,
)

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
    # Route handlers that call ``current_user.calculate_permissions()``
    # directly (e.g. the backoffice endpoints scoped by affiliation in #459)
    # need the mock to return real permission keys.
    u.calculate_permissions = lambda: calculate_user_permissions(roles)
    return u


def _principal(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id=iid))


def _std(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=iid))


def _backoffice() -> Role:
    return Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())


def _backoffice_scoped(affiliation: str) -> Role:
    return Role(
        role=RoleName.CO2_BACKOFFICE_METIER,
        on=AffiliationScope(affiliation=affiliation),
    )


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


# ─────────────────────────────────────────────────────────────────────────────
# Backoffice ACCRED affiliation scoping (#459)
#
# Affiliation-scoped backoffice managers (e.g. an SV-scoped admin) only hold
# ``backoffice.X/<affiliation>`` permission keys. Endpoints that swap
# ``require_permission`` for an inline ``any_scope=True`` gate must:
#   1. let the request through (the user IS a backoffice manager),
#   2. narrow results to units whose ``path_name`` carries the affiliation.
# GlobalScope backoffice / superadmin keep the bare keys and bypass narrowing.
# ─────────────────────────────────────────────────────────────────────────────


BACKOFFICE_UNITS_URL = "/api/v1/backoffice-reporting/units"
BACKOFFICE_AFFILIATIONS_URL = "/api/v1/backoffice-reporting/affiliations"


def _unit(uid: int, iid: str, name: str, path_name: str, level: int = 3) -> Unit:
    """Construct a fixture Unit (active by default)."""
    return Unit(
        id=uid,
        institutional_code=str(uid),
        institutional_id=iid,
        name=name,
        level=level,
        path_name=path_name,
        is_active=True,
    )


# Two-school fixture: one unit under SV, one under STI.
_SV_UNIT = _unit(1, "sv-cf", "SV-LAB", "EPFL > SV > SV-LAB")
_STI_UNIT = _unit(2, "sti-cf", "STI-LAB", "EPFL > STI > STI-LAB")


def _wire_backoffice(monkeypatch, user, units: list) -> None:
    """Wire dependency overrides for the backoffice endpoints.

    Captures every ``where`` clause the route attaches and applies them to the
    in-memory ``units`` fixture, so SQL-level filters (level, affiliation
    predicate) actually narrow results. The route uses ``db.exec(query).all()``;
    we honour ``query.where(...)`` chaining without touching real SQL.
    """
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    async def mock_get_db():
        db = MagicMock()

        async def mock_exec(query):
            # Compile the query and emulate the affiliation predicate in
            # memory. We extract every ``LIKE '% <token> %'`` literal from
            # the compiled SQL and require a unit's padded ``path_name`` to
            # contain at least one of them. If no such literal appears, the
            # query is un-narrowed (global caller) and we return all units.
            #
            # Coupled to the exact predicate shape from
            # ``_affiliation_predicate``: any refactor that drops the
            # ``LIKE lower('% <aff> %')`` form flips this to "no tokens" →
            # all rows return → the scoped tests fail with the unscoped
            # row count. That IS the signal that the predicate moved.
            compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
            tokens = re.findall(r"like\s+lower\('% ([^ ]+?) %'\)", compiled, re.I)

            def keep(u: Unit) -> bool:
                if not tokens:
                    return True
                padded = f" {(u.path_name or '').lower()} "
                return any(f" {t.lower()} " in padded for t in tokens)

            result = MagicMock()
            result.all = lambda: [u for u in units if keep(u)]
            return result

        db.exec = mock_exec
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db


class TestBackofficeAffiliationScopeEndToEnd:
    """Affiliation-scoped backoffice users only see units inside their
    sub-perimeter; GlobalScope keeps full reach (#459)."""

    def test_global_backoffice_sees_all_units(self, client, monkeypatch):
        """Superadmin → bare ``backoffice.users`` key → no narrowing.
        (CO2_BACKOFFICE_METIER is always sub-perimeter-bound; cross-affiliation
        reach is exclusive to CO2_SUPERADMIN.)"""
        user = _user("11111", [_superadmin()])
        _wire_backoffice(monkeypatch, user, [_SV_UNIT, _STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"SV-LAB", "STI-LAB"}

    def test_scoped_backoffice_sees_only_in_affiliation_units(
        self, client, monkeypatch
    ):
        """SV-scoped caller → only SV unit in the response."""
        user = _user("11111", [_backoffice_scoped("SV")])
        _wire_backoffice(monkeypatch, user, [_SV_UNIT, _STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"SV-LAB"}

    def test_scoped_backoffice_cross_affiliation_returns_empty(
        self, client, monkeypatch
    ):
        """SV-scoped caller against STI-only data → 200 empty list.
        The gate accepts (the user holds ``backoffice.users/SV``) but the
        affiliation predicate filters everything out."""
        user = _user("11111", [_backoffice_scoped("SV")])
        _wire_backoffice(monkeypatch, user, [_STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_scoped_backoffice_multi_affiliation_unions(self, client, monkeypatch):
        """A user holding both SV and STI roles sees the union."""
        user = _user("11111", [_backoffice_scoped("SV"), _backoffice_scoped("STI")])
        _wire_backoffice(monkeypatch, user, [_SV_UNIT, _STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"SV-LAB", "STI-LAB"}

    def test_no_backoffice_role_denied(self, client, monkeypatch):
        """Std user → 403 (still gated on ``backoffice.users.view``)."""
        user = _user("11111", [_std(UNIT_IID)])
        _wire_backoffice(monkeypatch, user, [_SV_UNIT, _STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 403, r.text

    def test_superadmin_sees_all_units(self, client, monkeypatch):
        """Regression guard: superadmin still bypasses narrowing."""
        user = _user("11111", [_superadmin()])
        _wire_backoffice(monkeypatch, user, [_SV_UNIT, _STI_UNIT])
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2

    def test_scoped_backoffice_affiliations_endpoint(self, client, monkeypatch):
        """``/backoffice/affiliations`` mirrors ``/units`` for narrowing.
        Build the fixture at level 2/3 (the endpoint filters levels in [2, 3])."""
        sv_aff = _unit(10, "sv-fac", "SV-FAC", "EPFL > SV", level=2)
        sti_aff = _unit(11, "sti-fac", "STI-FAC", "EPFL > STI", level=2)
        user = _user("11111", [_backoffice_scoped("SV")])
        _wire_backoffice(monkeypatch, user, [sv_aff, sti_aff])
        r = client.get(BACKOFFICE_AFFILIATIONS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"SV-FAC"}


# ─────────────────────────────────────────────────────────────────────────────
# /api/v1/backoffice/* (six endpoints previously gated by strict
# ``require_permission`` — Phase 2 / #459 opened them under ``any_scope=True``
# with server-side affiliation narrowing).
# ─────────────────────────────────────────────────────────────────────────────


BACKOFFICE_YEARS_URL = "/api/v1/backoffice/years"


def _wire_backoffice_years(
    monkeypatch, user, years_by_unit_path: dict[str, list[int]]
) -> None:
    """Stub the ``/backoffice/years`` query path.

    ``years_by_unit_path`` maps a unit ``path_name`` → years that unit has
    reports for. The mock inspects the compiled SQL for the affiliation
    ILIKE literals (same trick as ``_wire_backoffice``) and returns the
    union of years whose unit's ``path_name`` matches any literal. With
    no literals (global caller), all years are returned.
    """
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    async def mock_get_db():
        db = MagicMock()

        async def mock_exec(query):
            compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
            tokens = re.findall(r"like\s+lower\('% ([^ ]+?) %'\)", compiled, re.I)

            def path_matches(path: str) -> bool:
                if not tokens:
                    return True
                padded = f" {(path or '').lower()} "
                return any(f" {t.lower()} " in padded for t in tokens)

            collected = sorted(
                {
                    y
                    for path, years in years_by_unit_path.items()
                    if path_matches(path)
                    for y in years
                },
                reverse=True,
            )
            result = MagicMock()
            result.all = lambda: collected
            return result

        db.exec = mock_exec
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db


class TestBackofficeYearsAffiliationScoping:
    """``/backoffice/years`` exposes distinct CarbonReport.year values.

    For non-global callers the query joins ``Unit`` and applies the
    affiliation predicate, so scoped users only see years for which their
    affiliation has reports.
    """

    YEARS_BY_PATH = {
        "EPFL > SV > SV-LAB": [2024, 2025],
        "EPFL > STI > STI-LAB": [2023],
    }

    def test_global_backoffice_sees_all_years(self, client, monkeypatch):
        """Superadmin (the only role with cross-affiliation reach) sees every year."""
        user = _user("11111", [_superadmin()])
        _wire_backoffice_years(monkeypatch, user, self.YEARS_BY_PATH)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body["years"]) == {"2023", "2024", "2025"}
        assert body["latest"] == "2025"

    def test_scoped_backoffice_sees_only_in_affiliation_years(
        self, client, monkeypatch
    ):
        user = _user("11111", [_backoffice_scoped("SV")])
        _wire_backoffice_years(monkeypatch, user, self.YEARS_BY_PATH)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        body = r.json()
        # SV has 2024 + 2025; STI's 2023 must be filtered out.
        assert set(body["years"]) == {"2024", "2025"}
        assert body["latest"] == "2025"

    def test_scoped_backoffice_cross_affiliation_returns_empty(
        self, client, monkeypatch
    ):
        user = _user("11111", [_backoffice_scoped("CDH")])
        _wire_backoffice_years(monkeypatch, user, self.YEARS_BY_PATH)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        assert r.json() == {"years": [], "latest": ""}

    def test_no_backoffice_role_denied(self, client, monkeypatch):
        user = _user("11111", [_std(UNIT_IID)])
        _wire_backoffice_years(monkeypatch, user, self.YEARS_BY_PATH)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 403, r.text

    def test_principal_denied_after_backoffice_grant_removal(self, client, monkeypatch):
        """Pin the Phase 2 removal: CO2_USER_PRINCIPAL no longer grants
        backoffice.users.edit, so a principal-only user must NOT pass the
        backoffice gate."""
        user = _user("11111", [_principal(UNIT_IID)])
        _wire_backoffice_years(monkeypatch, user, self.YEARS_BY_PATH)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────────────────────
# /api/v1/sync/active-pipelines/year/{year} — shared by the configuration
# (data-management) page and the logs page. Both Backoffice Administrators
# (scoped) and Super Admin (global) must reach it (#459 follow-up).
# ─────────────────────────────────────────────────────────────────────────────


ACTIVE_PIPELINES_URL = "/api/v1/sync/active-pipelines/year/2026"


def _wire_active_pipelines(monkeypatch, user) -> None:
    """Stub the DataIngestionRepository so the route handler can run."""
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    async def mock_get_db():
        yield MagicMock()

    app.dependency_overrides[deps_module.get_db] = mock_get_db

    mock_repo = MagicMock()
    mock_repo.get_active_year_level_pipeline_ids = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.api.v1.data_sync.DataIngestionRepository", lambda db: mock_repo
    )


class TestActivePipelinesPerYearGate:
    """Module-flow read gated by ``require_module_or_config_view`` (#862).

    Allowed for a backoffice configuration operator (``backoffice.configuration``
    view — Super Admin) or any module user who can *sync* (``modules.<name>.sync``
    — principals polling their own upload progress). A metier user without
    configuration, and a std user without sync, are denied.
    """

    def test_superadmin_passes(self, client, monkeypatch):
        user = _user("11111", [_superadmin()])
        _wire_active_pipelines(monkeypatch, user)
        r = client.get(ACTIVE_PIPELINES_URL)
        assert r.status_code == 200, r.text

    def test_scoped_backoffice_metier_denied(self, client, monkeypatch):
        """Metier holds reporting/users/documentation/ui_texts only — no
        configuration and no module sync — so it cannot read pipeline status."""
        user = _user("11111", [_backoffice_scoped("ENAC-SG")])
        _wire_active_pipelines(monkeypatch, user)
        r = client.get(ACTIVE_PIPELINES_URL)
        assert r.status_code == 403, r.text

    def test_principal_passes(self, client, monkeypatch):
        """A principal can sync modules (modules.<name>.sync) and therefore may
        poll their own job/pipeline progress."""
        user = _user("11111", [_principal(UNIT_IID)])
        _wire_active_pipelines(monkeypatch, user)
        r = client.get(ACTIVE_PIPELINES_URL)
        assert r.status_code == 200, r.text

    def test_std_denied(self, client, monkeypatch):
        """Std has view/edit but no sync on its modules → denied."""
        user = _user("11111", [_std(UNIT_IID)])
        _wire_active_pipelines(monkeypatch, user)
        r = client.get(ACTIVE_PIPELINES_URL)
        assert r.status_code == 403, r.text
