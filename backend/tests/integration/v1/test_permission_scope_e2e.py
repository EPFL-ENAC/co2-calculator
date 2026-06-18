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
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.core.constants import ModuleStatus
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
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
# Backoffice affiliation scoping (#862) — over a real in-memory DB.
#
# A backoffice_metier scope token is a unit cf (institutional_id) at any level;
# scoping resolves it to that unit's descendant subtree via the indexed
# path_institutional_code. These E2E tests pin the route WIRING (gate → extract
# affiliations → pass as scope). The scope MATCHING itself is covered with real
# DB at the unit level by tests/unit/repositories/test_carbon_report_module_repo
# (TestResolveHierarchyUnitIdsScope, TestGetReportingOverview) and
# tests/unit/utils/test_scoping (TestBuildScopeSubtreePredicate).
# ─────────────────────────────────────────────────────────────────────────────


BACKOFFICE_UNITS_URL = "/api/v1/backoffice-reporting/units"
BACKOFFICE_AFFILIATIONS_URL = "/api/v1/backoffice-reporting/affiliations"
BACKOFFICE_YEARS_URL = "/api/v1/backoffice/years"
# The reporting overview page — the endpoint whose empty result started #862.
BACKOFFICE_REPORTING_UNITS_URL = "/api/v1/backoffice/units?years=2024&years=2025"

# Scope cfs (institutional_id) used in tests.
ENAC_CF = "13030"
STI_CF = "14000"
ABSENT_CF = "99999"


async def _seed_backoffice_db(session: AsyncSession) -> None:
    """Seed an ENAC subtree (lvl2→4) and a separate STI subtree.

    path_institutional_code is the self-inclusive root→leaf code path, so a
    unit is in ENAC's subtree iff ENAC's code (12635) is one of its tokens.
    ENAC-IT4R has reports for 2024/2025; STI-LAB for 2023.
    """
    units = [
        Unit(
            institutional_code="12635",
            institutional_id=ENAC_CF,
            name="ENAC",
            level=2,
            path_institutional_code="10582 12635",
            is_active=True,
        ),
        Unit(
            institutional_code="11435",
            institutional_id="13031",
            name="ENAC-SG",
            level=3,
            path_institutional_code="10582 12635 11435",
            is_active=True,
        ),
        Unit(
            institutional_code="14270",
            institutional_id="13032",
            name="ENAC-IT4R",
            level=4,
            path_institutional_code="10582 12635 11435 14270",
            is_active=True,
        ),
        Unit(
            institutional_code="13000",
            institutional_id=STI_CF,
            name="STI",
            level=2,
            path_institutional_code="10582 13000",
            is_active=True,
        ),
        Unit(
            institutional_code="13500",
            institutional_id="14500",
            name="STI-LAB",
            level=4,
            path_institutional_code="10582 13000 13500",
            is_active=True,
        ),
    ]
    session.add_all(units)
    await session.flush()
    by_name = {u.name: u for u in units}
    reports = {"ENAC-IT4R": [2024, 2025], "STI-LAB": [2023]}
    for name, years in reports.items():
        unit = by_name[name]
        project = CarbonProject(
            unit_id=unit.id, carbon_report_type=CarbonReportType.CALCULATOR
        )
        session.add(project)
        await session.flush()
        for year in years:
            session.add(
                CarbonReport(
                    year=year,
                    unit_id=unit.id,
                    carbon_project_id=project.id,
                    overall_status=ModuleStatus.NOT_STARTED,
                )
            )
    await session.commit()


@pytest_asyncio.fixture
async def backoffice_db():
    """In-memory SQLite seeded with the ENAC/STI fixtures; yields a factory."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await _seed_backoffice_db(session)
    yield factory
    await engine.dispose()


def _wire_db(user, factory) -> None:
    """Override the current user and bind the route's db to the seeded engine."""
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db


class TestBackofficeAffiliationScopeEndToEnd:
    """Affiliation-scoped backoffice users only see units inside their scope
    subtree; GlobalScope keeps full reach (#862)."""

    def test_global_backoffice_sees_all_units(self, client, backoffice_db):
        _wire_db(_user("11111", [_superadmin()]), backoffice_db)
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"ENAC", "ENAC-SG", "ENAC-IT4R", "STI", "STI-LAB"}

    def test_scoped_backoffice_sees_only_in_subtree_units(self, client, backoffice_db):
        """ENAC-scoped caller → only ENAC's subtree, never STI."""
        _wire_db(_user("11111", [_backoffice_scoped(ENAC_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"ENAC", "ENAC-SG", "ENAC-IT4R"}

    def test_scoped_backoffice_cross_affiliation_returns_empty(
        self, client, backoffice_db
    ):
        """Scope cf with no unit in this DB → gate passes, subtree is empty."""
        _wire_db(_user("11111", [_backoffice_scoped(ABSENT_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_scoped_backoffice_multi_affiliation_unions(self, client, backoffice_db):
        """Holding both ENAC and STI scopes → the union of both subtrees."""
        user = _user("11111", [_backoffice_scoped(ENAC_CF), _backoffice_scoped(STI_CF)])
        _wire_db(user, backoffice_db)
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"ENAC", "ENAC-SG", "ENAC-IT4R", "STI", "STI-LAB"}

    def test_no_backoffice_role_denied(self, client, backoffice_db):
        """Std user → 403 (gated on ``backoffice.reporting`` any-scope)."""
        _wire_db(_user("11111", [_std(UNIT_IID)]), backoffice_db)
        r = client.get(BACKOFFICE_UNITS_URL)
        assert r.status_code == 403, r.text

    def test_scoped_backoffice_affiliations_endpoint(self, client, backoffice_db):
        """``/affiliations`` shows only lvl2/3 within the ENAC subtree."""
        _wire_db(_user("11111", [_backoffice_scoped(ENAC_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_AFFILIATIONS_URL)
        assert r.status_code == 200, r.text
        names = {u["name"] for u in r.json()}
        assert names == {"ENAC", "ENAC-SG"}


class TestBackofficeReportingOverviewScoping:
    """``/backoffice/units`` reporting overview — the page that #862 fixed.

    Overview rows exist only for units with CarbonReports; the fixture seeds
    ENAC-IT4R (in ENAC's subtree, years 2024/25) and STI-LAB (outside, 2023).
    """

    def _names(self, payload) -> set[str]:
        return {row["unit_name"] for row in payload["data"]}

    def test_global_sees_in_year_units(self, client, backoffice_db):
        _wire_db(_user("11111", [_superadmin()]), backoffice_db)
        r = client.get(BACKOFFICE_REPORTING_UNITS_URL)
        assert r.status_code == 200, r.text
        assert self._names(r.json()) == {"ENAC-IT4R"}

    def test_scoped_sees_only_in_subtree(self, client, backoffice_db):
        _wire_db(_user("11111", [_backoffice_scoped(ENAC_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_REPORTING_UNITS_URL)
        assert r.status_code == 200, r.text
        assert self._names(r.json()) == {"ENAC-IT4R"}

    def test_scoped_cross_affiliation_returns_empty(self, client, backoffice_db):
        _wire_db(_user("11111", [_backoffice_scoped(STI_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_REPORTING_UNITS_URL)
        assert r.status_code == 200, r.text
        # STI's only report is 2023, outside the requested 2024/25 window.
        assert r.json()["data"] == []

    def test_scoped_out_of_scope_lvl4_filter_empty(self, client, backoffice_db):
        """ENAC-scoped caller requesting the STI lab → clamped to empty."""
        _wire_db(_user("11111", [_backoffice_scoped(ENAC_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_REPORTING_UNITS_URL + "&path_lvl4=STI-LAB")
        assert r.status_code == 200, r.text
        assert r.json()["data"] == []


class TestBackofficeYearsAffiliationScoping:
    """``/backoffice/years`` distinct CarbonReport.year values, scope-clamped."""

    def test_global_backoffice_sees_all_years(self, client, backoffice_db):
        _wire_db(_user("11111", [_superadmin()]), backoffice_db)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body["years"]) == {"2023", "2024", "2025"}
        assert body["latest"] == "2025"

    def test_scoped_backoffice_sees_only_in_subtree_years(self, client, backoffice_db):
        _wire_db(_user("11111", [_backoffice_scoped(ENAC_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        body = r.json()
        # ENAC subtree has 2024 + 2025; STI's 2023 is clamped out.
        assert set(body["years"]) == {"2024", "2025"}
        assert body["latest"] == "2025"

    def test_scoped_backoffice_cross_affiliation_returns_empty(
        self, client, backoffice_db
    ):
        _wire_db(_user("11111", [_backoffice_scoped(ABSENT_CF)]), backoffice_db)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 200, r.text
        assert r.json() == {"years": [], "latest": ""}

    def test_no_backoffice_role_denied(self, client, backoffice_db):
        _wire_db(_user("11111", [_std(UNIT_IID)]), backoffice_db)
        r = client.get(BACKOFFICE_YEARS_URL)
        assert r.status_code == 403, r.text

    def test_principal_denied(self, client, backoffice_db):
        """CO2_USER_PRINCIPAL does not grant backoffice.reporting → 403."""
        _wire_db(_user("11111", [_principal(UNIT_IID)]), backoffice_db)
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

    # skip until permission change TODO: add back when permission change is implemented
    # def test_scoped_backoffice_metier_denied(self, client, monkeypatch):
    #     """Metier holds reporting/users/documentation/ui_texts only — no
    #     configuration and no module sync — so it cannot read pipeline status."""
    #     user = _user("11111", [_backoffice_scoped("ENAC-SG")])
    #     _wire_active_pipelines(monkeypatch, user)
    #     r = client.get(ACTIVE_PIPELINES_URL)
    #     assert r.status_code == 403, r.text

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
