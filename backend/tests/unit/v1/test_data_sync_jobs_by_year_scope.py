"""The year job lists are a backoffice view (code-scanning alert 1380).

``GET /sync/jobs/year/{year}`` and ``/latest`` return every unit's job
``meta`` (``config.file_path`` included), and only the backoffice Data
Management page calls them. A unit user with a module sync grant must get
403; a ``backoffice.configuration`` viewer gets 200.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.v1.data_sync as data_sync_module
from app.api.deps import get_db
from app.core.security import get_current_active_user
from app.main import app
from tests.integration.v1.test_unit_gating_e2e import _principal, _superadmin, _user

ROUTES = ["/api/v1/sync/jobs/year/2025", "/api/v1/sync/jobs/year/2025/latest"]


class _FakeRepo:
    def __init__(self, _session):
        pass

    async def get_jobs_by_year(self, _year):
        return []

    async def get_latest_jobs_by_year(self, _year):
        return []


def _client(monkeypatch, user) -> TestClient:
    async def _current_user():
        return user

    async def _db():
        yield None

    monkeypatch.setattr(data_sync_module, "DataIngestionRepository", _FakeRepo)
    app.dependency_overrides[get_current_active_user] = _current_user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize("route", ROUTES)
def test_module_sync_user_is_denied(monkeypatch, route):
    user = _user("1234", [_principal("1234")])
    # Precondition: the old gate (any modules.* sync grant) admitted this user.
    assert data_sync_module.can_view_module_flow(user)
    client = _client(monkeypatch, user)
    assert client.get(route).status_code == 403


@pytest.mark.parametrize("route", ROUTES)
def test_backoffice_configuration_viewer_is_allowed(monkeypatch, route):
    client = _client(monkeypatch, _user("1234", [_superadmin()]))
    assert client.get(route).status_code == 200
