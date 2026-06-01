"""End-to-end permission-scope tests for the routes tightened in #977.

Covers:
- ``carbon_report.py::list_carbon_report_modules`` (gated this PR)
- ``carbon_report.py::update_carbon_report_module_status`` (gated this PR)
- ``unit_results.py::get_unit_results`` (gated this PR)
- ``unit_results.py::get_unit_totals`` (gated this PR)
- ``unit_results.py::get_validated_emissions`` (gated this PR)
- ``files.py::list_files`` / ``get_file`` / ``upload_temp_files``
  / ``delete_temp_files`` — regression for the ``modules.*`` fallback removal.
- ``data_sync.py::sync_module_data_entries`` (dispatch)
  / ``job_stream_by_id`` — same fallback-removal regression.

For each tightened endpoint:
- cross-unit principal → 403
- in-unit principal → 200
- global backoffice → 200

For each ``modules.*``-fallback removal:
- a principal whose ONLY perms are ``modules.<x>/A`` (no backoffice) → 403
  (was 200 with the old fallback — this pins the regression).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.user import (
    GlobalScope,
    Role,
    RoleName,
    RoleScope,
    User,
    calculate_user_permissions,
)

UNIT_IID = "0184"
OTHER_IID = "9999"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
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


def _backoffice() -> Role:
    return Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())


def _wire_user(user) -> None:
    app.dependency_overrides[deps_module.get_current_user] = lambda: user


def _wire_db_unit(unit_iid: str) -> None:
    """Override ``get_db`` so ``.get(Unit, _)`` yields a unit with the iid."""
    mock_unit = MagicMock()
    mock_unit.institutional_id = unit_iid
    db = MagicMock()
    db.get = AsyncMock(return_value=mock_unit)
    db.commit = AsyncMock()

    async def mock_get_db():
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db


# ─────────────────────────────────────────────────────────────────────────────
# carbon_report.py — list_carbon_report_modules (gated this PR)
# ─────────────────────────────────────────────────────────────────────────────

CR_LIST_MODULES_URL = "/api/v1/carbon-reports/1/modules/"
CR_UPDATE_STATUS_URL = "/api/v1/carbon-reports/1/modules/1/status"


def _mock_carbon_report_with_unit(monkeypatch, unit_id: int = 1) -> None:
    """Stub CarbonReportService so any get() returns a report with unit_id."""
    report = MagicMock()
    report.unit_id = unit_id
    report.id = 1
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)
    svc.recompute_report_stats = AsyncMock()
    svc.recompute_report_progress = AsyncMock()
    monkeypatch.setattr("app.api.v1.carbon_report.CarbonReportService", lambda db: svc)


def _mock_carbon_report_module_service(monkeypatch) -> None:
    module_svc = MagicMock()
    module_svc.list_modules = AsyncMock(return_value=[])
    updated = {
        "id": 1,
        "carbon_report_id": 1,
        "module_type_id": 1,
        "status": 2,
        "stats": {},
    }
    module_svc.update_status = AsyncMock(return_value=updated)
    monkeypatch.setattr(
        "app.api.v1.carbon_report.CarbonReportModuleService", lambda db: module_svc
    )


class TestListCarbonReportModules:
    """``GET /carbon-reports/{id}/modules/`` — gated by ``require_unit_access``."""

    def test_cross_unit_principal_denied(self, client, monkeypatch):
        """principal scoped to UNIT_IID hits a report on OTHER_IID → 403."""
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(OTHER_IID)
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.get(CR_LIST_MODULES_URL)
        assert r.status_code == 403, r.text

    def test_in_unit_principal_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(UNIT_IID)
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.get(CR_LIST_MODULES_URL)
        assert r.status_code == 200, r.text

    def test_backoffice_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_backoffice()]))
        _wire_db_unit(OTHER_IID)  # any unit — global bypass
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.get(CR_LIST_MODULES_URL)
        assert r.status_code == 200, r.text


class TestUpdateCarbonReportModuleStatus:
    """``PATCH /carbon-reports/{id}/modules/{type}/status`` — gated this PR."""

    PAYLOAD = {"status": 2}

    def test_cross_unit_principal_denied(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(OTHER_IID)
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.patch(CR_UPDATE_STATUS_URL, json=self.PAYLOAD)
        assert r.status_code == 403, r.text

    def test_in_unit_principal_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(UNIT_IID)
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.patch(CR_UPDATE_STATUS_URL, json=self.PAYLOAD)
        assert r.status_code == 200, r.text

    def test_backoffice_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_backoffice()]))
        _wire_db_unit(OTHER_IID)
        _mock_carbon_report_with_unit(monkeypatch)
        _mock_carbon_report_module_service(monkeypatch)
        r = client.patch(CR_UPDATE_STATUS_URL, json=self.PAYLOAD)
        assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────────────
# unit_results.py — 3 endpoints (gated this PR)
# ─────────────────────────────────────────────────────────────────────────────

UR_RESULTS_URL = "/api/v1/unit/1/results"
UR_TOTALS_URL = "/api/v1/unit/1/2024/totals"
UR_EMISSIONS_URL = "/api/v1/unit/1/yearly-validated-emissions"


def _mock_unit_totals_service(monkeypatch) -> None:
    svc = MagicMock()
    svc.get_unit_totals = AsyncMock(return_value={"total_kg_co2eq": 0})
    svc.get_validated_emissions_by_unit = AsyncMock(return_value=[])
    monkeypatch.setattr("app.api.v1.unit_results.UnitTotalsService", lambda db: svc)


class TestUnitResults:
    """All three endpoints take ``unit_id`` and must gate on it."""

    def test_get_unit_results_cross_unit_denied(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(OTHER_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_RESULTS_URL)
        assert r.status_code == 403, r.text

    def test_get_unit_results_in_unit_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(UNIT_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_RESULTS_URL)
        assert r.status_code == 200, r.text

    def test_get_unit_results_backoffice_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_backoffice()]))
        _wire_db_unit(OTHER_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_RESULTS_URL)
        assert r.status_code == 200, r.text

    def test_get_unit_totals_cross_unit_denied(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(OTHER_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_TOTALS_URL)
        assert r.status_code == 403, r.text

    def test_get_unit_totals_in_unit_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(UNIT_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_TOTALS_URL)
        assert r.status_code == 200, r.text

    def test_get_validated_emissions_cross_unit_denied(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(OTHER_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_EMISSIONS_URL)
        assert r.status_code == 403, r.text

    def test_get_validated_emissions_in_unit_allowed(self, client, monkeypatch):
        _wire_user(_user("11111", [_principal(UNIT_IID)]))
        _wire_db_unit(UNIT_IID)
        _mock_unit_totals_service(monkeypatch)
        r = client.get(UR_EMISSIONS_URL)
        assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────────────
# files.py — modules.* fallback regression
# ─────────────────────────────────────────────────────────────────────────────
#
# Construct a CO2_USER_PRINCIPAL whose calculated perms include
# ``modules.headcount/0184`` (and other ``modules.*/0184`` entries) but
# NO ``backoffice.data_management.*``. Before #977 the route admitted
# them via the ``modules.*`` glob fallback; now they must hit 403.


def _scoped_principal_user() -> MagicMock:
    """Real role list — let ``calculate_user_permissions`` run for the
    ``is_permitted("modules.*", ...)`` admit-set comparison."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "principal@test.local"
    user.institutional_id = "11111"
    user.roles = [_principal(UNIT_IID)]
    user.calculate_permissions = lambda: calculate_user_permissions(user.roles)
    return user


class TestFilesPermissionFallbackRemoved:
    """Regression: principal with only ``modules.*/0184`` perms must be
    denied on /files/* now that the fallback is removed."""

    def test_list_files_rejects_scoped_principal_without_backoffice(self, client):
        _wire_user(_scoped_principal_user())
        r = client.get("/api/v1/files/")
        assert r.status_code == 403, r.text

    def test_get_file_rejects_scoped_principal_without_backoffice(self, client):
        _wire_user(_scoped_principal_user())
        r = client.get("/api/v1/files/processed/152/foo.csv")
        assert r.status_code == 403, r.text

    def test_upload_temp_files_rejects_scoped_principal_without_backoffice(
        self, client
    ):
        _wire_user(_scoped_principal_user())
        r = client.post(
            "/api/v1/files/temp-upload",
            files={"files": ("a.csv", b"col\n1\n", "text/csv")},
        )
        assert r.status_code == 403, r.text

    def test_delete_temp_files_rejects_scoped_principal_without_backoffice(
        self, client
    ):
        _wire_user(_scoped_principal_user())
        r = client.delete("/api/v1/files/tmp/123/foo.csv")
        assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────────────────────
# data_sync.py — modules.* fallback regression
# ─────────────────────────────────────────────────────────────────────────────


class TestDataSyncPermissionFallbackRemoved:
    """Regression: principal with only ``modules.*/0184`` perms must be
    denied on /sync/dispatch and /sync/jobs/{id}/stream now."""

    def test_dispatch_rejects_scoped_principal_without_backoffice(self, client):
        _wire_user(_scoped_principal_user())
        # Send a payload the SyncRequest schema accepts so body validation
        # passes and the request reaches the permission gate (which is what
        # we're asserting on).
        r = client.post(
            "/api/v1/sync/dispatch",
            json={
                "ingestion_method": 1,  # IngestionMethod.csv
                "target_type": 0,  # TargetType.DATA_ENTRIES
                "filters": {},
            },
        )
        assert r.status_code == 403, r.text

    def test_job_stream_rejects_scoped_principal_without_backoffice(self, client):
        _wire_user(_scoped_principal_user())
        r = client.get("/api/v1/sync/jobs/1/stream")
        assert r.status_code == 403, r.text
