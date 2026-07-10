"""Regression: /sync/dispatch and /sync/factors must not 500 on a provider
config gap (#1552).

When no connection/datasource is configured — the normal post-deploy state —
``provider.validate_connection()`` raises a ``ValueError`` with an
operator-actionable message. The dispatch endpoint must map that to a clean
503 carrying the message, never let it escape as a bare 500 with a traceback.

Uses the same in-memory SQLite ``TestClient`` idiom as ``test_connectors.py``;
``ProviderFactory.create_provider`` is stubbed so the test drives only the
endpoint's error handling, not a real Tableau probe.
"""

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.user import GlobalScope, Role, RoleName, calculate_user_permissions
from app.services.data_ingestion.provider_factory import ProviderFactory

DISPATCH_URL = "/api/v1/sync/dispatch"
FACTORS_URL = "/api/v1/sync/factors/1/1"  # headcount / member

CONFIG_ERROR_MSG = (
    "No EPFL_TABLEAU connection configured — set one in the API connect "
    "form before importing."
)


class _StubProvider:
    async def validate_connection(self) -> bool:
        raise ValueError(CONFIG_ERROR_MSG)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _superadmin() -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = "123456"
    roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
    u.roles = roles
    u.calculate_permissions = lambda: calculate_user_permissions(roles)
    return u


@pytest_asyncio.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _wire(factory) -> None:
    app.dependency_overrides[deps_module.get_current_user] = _superadmin

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db


def test_dispatch_maps_provider_config_error_to_503(client, db_factory, monkeypatch):
    _wire(db_factory)

    async def _fake_create(**kwargs):
        return _StubProvider()

    monkeypatch.setattr(ProviderFactory, "create_provider", _fake_create)

    body = {
        "ingestion_method": 0,  # api
        "target_type": 0,  # DATA_ENTRIES
        "filters": {},
        "config": {},
    }
    r = client.post(DISPATCH_URL, json=body)
    # Clean, actionable client error — not a bare 500 with a traceback.
    assert r.status_code == 503, r.text
    assert "connection configured" in r.json()["detail"]


def test_factors_maps_provider_config_error_to_503(client, db_factory, monkeypatch):
    _wire(db_factory)

    async def _fake_create(**kwargs):
        return _StubProvider()

    monkeypatch.setattr(ProviderFactory, "create_provider", _fake_create)

    body = {
        "ingestion_method": 0,  # api
        "target_type": 0,  # DATA_ENTRIES
        "filters": {},
        "config": {},
        "year": 2025,
    }
    r = client.post(FACTORS_URL, json=body)
    # Same sibling bug: sync_module_factors was missing the ValueError->503
    # mapping that sync_module_data_entries already had.
    assert r.status_code == 503, r.text
    assert "connection configured" in r.json()["detail"]
