"""Integration tests for ``POST /api/v1/year-configuration/{year}`` (#1403
slice a — year initialization checklist items).

Access control for this route is covered by
``test_permission_scope_e2e.py::TestYearConfigurationAdminOnlyGate`` (real
permission chain); this file uses a mocked ``is_permitted`` (matching
``test_year_configuration_list.py``'s convention) since it only needs an
admin/non-admin toggle to reach the create logic.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.data_ingestion import DataIngestionJob
from app.models.user import UserProvider
from tests.browser import SAME_ORIGIN_HEADERS
from tests.unit.v1.test_temp_upload_auth_ordering import valid_access_token

CREATE_URL = "/api/v1/year-configuration/{year}"


@pytest_asyncio.fixture
async def db_factory():
    """In-memory SQLite with all tables created, no seeded rows."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def client():
    # AuthFirstRoute (#2261) verifies the JWT cookie before dependencies
    # run, so the get_current_user override alone no longer gets past it.
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


def _user() -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = "11111"
    u.provider = UserProvider.DEFAULT
    return u


def _wire(monkeypatch, factory, *, is_admin: bool) -> None:
    """Real DB, mocked ``is_permitted`` (admin toggle), no-op background
    dispatch — the job ROW is the assertion target, not the sync handler's
    actual Accred call (out of scope: slow integration, per #1403's design
    doc).
    """
    app.dependency_overrides[deps_module.get_current_user] = _user

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    async def fake_is_permitted(user, path, action="view"):
        if path == "backoffice.configuration" and action == "edit":
            return is_admin
        return False

    monkeypatch.setattr("app.api.v1.year_configuration.is_permitted", fake_is_permitted)

    def fake_fire_and_forget(coro, *, name=None):
        coro.close()
        return None

    monkeypatch.setattr(
        "app.api.v1.year_configuration.fire_and_forget", fake_fire_and_forget
    )


# ---------------------------------------------------------------------------
# Year bounds — #1204 (PR #1737, merged) adds "MIN_CONFIGURABLE_YEAR <= year
# <= current_year" (default MIN_CONFIGURABLE_YEAR=2025, see Settings).
# ---------------------------------------------------------------------------


class TestYearBoundsValidation:
    def test_year_below_2025_rejected(self, client, monkeypatch, db_factory):
        _wire(monkeypatch, db_factory, is_admin=True)
        r = client.post(CREATE_URL.format(year=2024))
        assert r.status_code in (400, 422), r.text

    def test_year_above_current_year_rejected(self, client, monkeypatch, db_factory):
        _wire(monkeypatch, db_factory, is_admin=True)
        future_year = datetime.utcnow().year + 1
        r = client.post(CREATE_URL.format(year=future_year))
        assert r.status_code in (400, 422), r.text


# ---------------------------------------------------------------------------
# Issue #867 — creating a year auto-enqueues a unit_sync DataIngestionJob
# tied to a freshly-minted pipeline_id, so the frontend can subscribe to
# the Accred sync via SSE immediately.
# ---------------------------------------------------------------------------


class TestCreateYearConfigurationEnqueuesUnitSync:
    @pytest.mark.asyncio
    async def test_creates_persisted_unit_sync_job(
        self, client, monkeypatch, db_factory
    ):
        _wire(monkeypatch, db_factory, is_admin=True)

        r = client.post(CREATE_URL.format(year=2025))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["pipeline_id"]

        async with db_factory() as session:
            stmt = select(DataIngestionJob).where(
                col(DataIngestionJob.year) == 2025,
                col(DataIngestionJob.job_type) == "unit_sync",
            )
            jobs = (await session.exec(stmt)).all()
        assert len(jobs) == 1
        assert str(jobs[0].pipeline_id) == body["pipeline_id"]

    def test_non_admin_cannot_create(self, client, monkeypatch, db_factory):
        _wire(monkeypatch, db_factory, is_admin=False)
        r = client.post(CREATE_URL.format(year=2025))
        assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Checklist: "All modules show Incomplete on the config homepage before
# any data is uploaded" — asserted at the actual endpoint response, the
# real config homepage read (unit-level coverage of the same computation
# lives in test_year_configuration_incomplete_flag.py).
# ---------------------------------------------------------------------------


class TestFreshYearShowsAllModulesIncomplete:
    def test_all_modules_incomplete_in_create_response(
        self, client, monkeypatch, db_factory
    ):
        _wire(monkeypatch, db_factory, is_admin=True)

        r = client.post(CREATE_URL.format(year=2025))
        assert r.status_code == 201, r.text
        modules = r.json()["config"]["modules"]
        assert modules  # sanity: default config actually has modules
        for module_key, module_val in modules.items():
            assert module_val["incomplete"] is True, module_key
