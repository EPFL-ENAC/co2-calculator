"""Report-addressed routes run ``require_report_access`` (#3185).

Real routes and real policy chain; only the DB rows and the downstream
services are stubbed. Each case pins who may read or edit one report:
unit access, Explore ownership and Plan scope.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.unit import Unit
from app.schemas.carbon_report import CarbonReportRead
from tests.browser import SAME_ORIGIN_HEADERS
from tests.integration.v1.test_unit_gating_e2e import (
    OTHER_IID,
    UNIT_IID,
    USER_IID,
    _principal,
    _superadmin,
    _user,
)
from tests.unit.v1.test_temp_upload_auth_ordering import valid_access_token

STATS_URLS = [
    "/api/v1/modules-stats/1/report-stats",
    "/api/v1/modules-stats/1/validated-totals",
    "/api/v1/modules-stats/1/results-summary",
]
LIST_MODULES_URL = "/api/v1/carbon-reports/1/modules/"
STATUS_URL = "/api/v1/carbon-reports/1/modules/1/status"
REPORT_URL = "/api/v1/carbon-reports/1"
READ_URLS = [*STATS_URLS, LIST_MODULES_URL, REPORT_URL]

OWNER_ID = 1
OTHER_USER_ID = 2


@pytest.fixture
def client():
    with TestClient(
        app,
        cookies={"auth_token": valid_access_token()},
        headers=SAME_ORIGIN_HEADERS,
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _stub_services(monkeypatch):
    """Downstream reads return empty payloads; only the gate is under test."""
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module_stats.build_validated_totals",
        AsyncMock(return_value={"total_tonnes_co2eq": 0}),
    )
    totals_svc = MagicMock(
        get_results_summary=AsyncMock(
            return_value={
                "current_emissions": {},
                "current_fte": 0,
                "prev_emissions": {},
            }
        )
    )
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module_stats.UnitTotalsService",
        lambda db: totals_svc,
    )
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module_stats.compute_results_summary",
        lambda *_a, **_k: {},
    )
    report_svc = MagicMock()
    report_svc.get = AsyncMock(side_effect=lambda _id: _ROWS[CarbonReport])
    report_svc.recompute_report_stats = AsyncMock()
    report_svc.recompute_report_progress = AsyncMock()
    monkeypatch.setattr(
        "app.api.v1.carbon_report.CarbonReportService", lambda db: report_svc
    )
    monkeypatch.setattr(
        "app.api.v1.carbon_report._carbon_report_read",
        AsyncMock(return_value=CarbonReportRead(id=1, year=2024, unit_id=1)),
    )
    module_svc = MagicMock()
    module_svc.list_modules = AsyncMock(return_value=[])
    module_svc.update_status = AsyncMock(
        return_value={
            "id": 1,
            "carbon_report_id": 1,
            "module_type_id": 1,
            "status": 2,
            "stats": {},
        }
    )
    monkeypatch.setattr(
        "app.api.v1.carbon_report.CarbonReportModuleService", lambda db: module_svc
    )


_ROWS: dict = {}


def _wire(user, project_type=None, created_by=OWNER_ID, shared=False) -> None:
    """Serve one report on unit UNIT_IID, optionally inside a project."""
    unit = MagicMock(institutional_id=UNIT_IID, affiliation="SV_TEST")
    report = MagicMock(id=1, unit_id=1, stats={}, carbon_project_id=None)
    project = None
    if project_type is not None:
        report.carbon_project_id = 7
        project = MagicMock(
            carbon_report_type=project_type,
            created_by=created_by,
            is_viewable_by_unit_members=shared,
        )
    _ROWS.clear()
    _ROWS.update({CarbonReport: report, Unit: unit, CarbonProject: project})

    db = MagicMock()
    db.get = AsyncMock(side_effect=lambda model, _key: _ROWS[model])
    db.commit = AsyncMock()

    async def _get_db():
        yield db

    app.dependency_overrides[deps_module.get_db] = _get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: user


def _member(user_id: int = OWNER_ID):
    u = _user(USER_IID, [_principal(UNIT_IID)])
    u.id = user_id
    return u


@pytest.mark.parametrize("url", READ_URLS)
def test_user_without_role_on_unit_is_denied(client, url):
    _wire(_user(USER_IID, [_principal(OTHER_IID)]))
    assert client.get(url).status_code == 403


def test_status_patch_without_role_on_unit_is_denied(client):
    _wire(_user(USER_IID, [_principal(OTHER_IID)]))
    assert client.patch(STATUS_URL, json={"status": 2}).status_code == 403


@pytest.mark.parametrize("url", READ_URLS)
def test_unit_member_reads_calculator_report(client, url):
    _wire(_member())
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("url", READ_URLS)
def test_explore_report_hidden_from_other_member(client, url):
    _wire(_member(OTHER_USER_ID), CarbonReportType.SIMULATOR_EXPLORE)
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("url", READ_URLS)
def test_explore_report_visible_to_its_creator(client, url):
    _wire(_member(OWNER_ID), CarbonReportType.SIMULATOR_EXPLORE)
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("url", READ_URLS)
def test_unshared_plan_hidden_from_other_member(client, url):
    _wire(_member(OTHER_USER_ID), CarbonReportType.SIMULATOR_PLAN, shared=False)
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("url", READ_URLS)
def test_unshared_plan_visible_to_its_creator(client, url):
    _wire(_member(OWNER_ID), CarbonReportType.SIMULATOR_PLAN, shared=False)
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("url", READ_URLS)
def test_shared_plan_visible_to_other_member(client, url):
    _wire(_member(OTHER_USER_ID), CarbonReportType.SIMULATOR_PLAN, shared=True)
    assert client.get(url).status_code == 200


def test_status_patch_on_unshared_plan_of_other_member_is_rejected(client):
    _wire(_member(OTHER_USER_ID), CarbonReportType.SIMULATOR_PLAN, shared=False)
    assert client.patch(STATUS_URL, json={"status": 2}).status_code == 404


def test_status_patch_on_shared_plan_is_allowed(client):
    _wire(_member(OTHER_USER_ID), CarbonReportType.SIMULATOR_PLAN, shared=True)
    assert client.patch(STATUS_URL, json={"status": 2}).status_code == 200


@pytest.mark.parametrize("url", READ_URLS)
def test_global_role_reads_any_report(client, url):
    _wire(_user(USER_IID, [_superadmin()]))
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("url", STATS_URLS)
def test_missing_report_is_404(client, url):
    _wire(_member())
    _ROWS[CarbonReport] = None
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("url", STATS_URLS)
def test_report_of_missing_unit_is_404(client, url):
    _wire(_user(USER_IID, [_superadmin()]))
    _ROWS[Unit] = None
    assert client.get(url).status_code == 404
