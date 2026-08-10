"""Integration tests for the connectors API (#1552).

Mirrors the sync ``TestClient`` idiom from ``test_permission_scope_e2e.py``:
auth is faked by overriding ``get_current_user``, the DB is a real
in-memory SQLite engine bound via ``dependency_overrides`` (so audit rows
are actually written and can be inspected), and overrides are cleared after
each test.
"""

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.core import crypto, url_safety
from app.main import app
from app.models.audit import AuditDocument
from app.models.user import GlobalScope, Role, RoleName, calculate_user_permissions

CONNECTORS_URL = "/api/v1/connectors"
CONNECTION_URL = f"{CONNECTORS_URL}/EPFL_TABLEAU/connection"
DATASOURCES_URL = f"{CONNECTORS_URL}/EPFL_TABLEAU/datasources"
TEST_URL = f"{CONNECTORS_URL}/EPFL_TABLEAU/test"

VALID_BODY = {
    "label": "EPFL Tableau",
    "server_url": "https://tableau.epfl.ch/",
    "site_content_url": "co2fp",
    "username": "svc-calcco2-epfl-api",
    "client_id": "cid",
    "secret_id": "sid",
    "secret_value": "the-real-secret",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _crypto_env(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()


def _user(has_permission: bool = True, user_id: int = 1) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "test@example.com"
    u.institutional_id = "123456"
    roles = (
        [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        if has_permission
        else [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]
    )
    u.roles = roles
    u.calculate_permissions = lambda: calculate_user_permissions(roles)
    return u


@pytest_asyncio.fixture
async def db_factory():
    """Fresh in-memory SQLite engine per test, bound via dependency_overrides."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _wire(user, factory) -> None:
    app.dependency_overrides[deps_module.get_current_user] = lambda: user

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db


async def _audit_rows(factory, entity_type: str) -> list[AuditDocument]:
    async with factory() as session:
        result = await session.exec(
            select(AuditDocument).where(col(AuditDocument.entity_type) == entity_type)
        )
        return list(result.all())


def test_list_connectors_returns_registry(client, db_factory):
    _wire(_user(), db_factory)
    r = client.get(CONNECTORS_URL)
    assert r.status_code == 200, r.text
    assert r.json()[0]["connector"] == "EPFL_TABLEAU"


def test_no_permission_denied(client, db_factory):
    _wire(_user(has_permission=False), db_factory)
    r = client.get(CONNECTORS_URL)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_put_then_get_hides_secret_and_records_audit(client, db_factory):
    _wire(_user(), db_factory)

    listed = client.get(CONNECTORS_URL)
    assert listed.status_code == 200
    assert listed.json()[0]["connector"] == "EPFL_TABLEAU"

    put = client.put(CONNECTION_URL, json=VALID_BODY)
    assert put.status_code == 200, put.text
    body = put.json()
    assert "secret_value" not in body
    assert "secret_value_encrypted" not in body
    assert body["has_secret"] is True

    got = client.get(CONNECTION_URL)
    assert got.status_code == 200, got.text
    assert got.json()["client_id"] == "cid"
    assert "secret_value" not in got.json()

    rows = await _audit_rows(db_factory, "ConnectorConnection")
    assert len(rows) == 1
    snapshot = rows[0].data_snapshot
    assert "secret_value" not in snapshot
    assert "secret_value_encrypted" not in snapshot
    assert snapshot["has_secret"] is True


def test_put_rejects_disallowed_server_url_with_422(client, db_factory):
    _wire(_user(), db_factory)
    bad_body = dict(VALID_BODY, server_url="https://tableau.evil.com/")
    r = client.put(CONNECTION_URL, json=bad_body)
    assert r.status_code == 422, r.text
    assert "allowlist" in r.json()["detail"]


def test_put_new_connection_without_secret_returns_422(client, db_factory):
    _wire(_user(), db_factory)
    body = dict(VALID_BODY, secret_value=None)
    r = client.put(CONNECTION_URL, json=body)
    assert r.status_code == 422, r.text
    assert "secret_value is required" in r.json()["detail"]


def test_datasource_upsert_requires_existing_connection(client, db_factory):
    _wire(_user(), db_factory)
    r = client.post(
        DATASOURCES_URL,
        json={
            "module_type_id": 1,
            "connector_luid": "luid-1",
            "label": "Some datasource",
        },
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_datasource_upsert_records_audit_without_secret(client, db_factory):
    _wire(_user(), db_factory)
    put = client.put(CONNECTION_URL, json=VALID_BODY)
    assert put.status_code == 200, put.text

    r = client.post(
        DATASOURCES_URL,
        json={
            "module_type_id": 1,
            "connector_luid": "luid-1",
            "label": "Some datasource",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["connector_luid"] == "luid-1"

    rows = await _audit_rows(db_factory, "ConnectorDatasource")
    assert len(rows) == 1
    assert "secret_value" not in rows[0].data_snapshot
    assert "secret_value_encrypted" not in rows[0].data_snapshot


def test_test_endpoint_no_connection_and_rate_limit(client, db_factory):
    _wire(_user(), db_factory)
    first = client.post(TEST_URL)
    assert first.status_code == 200, first.text
    # No connection seeded → generic operator-safe detail (never a raw error).
    assert first.json() == {"ok": False, "detail": "No connection configured"}

    second = client.post(TEST_URL)
    assert second.status_code == 429, second.text


def test_test_endpoint_rate_limit_is_per_user(client, db_factory):
    """One user's cooldown must not block a different user."""
    _wire(_user(user_id=101), db_factory)
    first = client.post(TEST_URL)
    assert first.status_code == 200, first.text

    _wire(_user(user_id=102), db_factory)
    other = client.post(TEST_URL)
    assert other.status_code == 200, other.text


@pytest.mark.asyncio
async def test_test_endpoint_records_audit_without_secret(
    client, db_factory, monkeypatch
):
    """A connection test is audited (PRD): an audit row is persisted with the
    connector + boolean outcome, and no secret material leaks into it.
    """
    from app.models.connector import ConnectorConnection, ConnectorType
    from app.services.data_ingestion.api_providers.professional_travel_api_provider import (  # noqa: E501
        ProfessionalTravelApiProvider,
    )

    _wire(_user(user_id=201), db_factory)

    # Seed the connection directly (not via PUT) so /test creates the first
    # audit version — the partial-unique "one current row" index degrades to
    # a full unique index under SQLite, so we don't stack two versions here.
    async with db_factory() as session:
        session.add(
            ConnectorConnection(
                connector=ConnectorType.EPFL_TABLEAU,
                label="EPFL Tableau",
                server_url="https://tableau.epfl.ch/",
                site_content_url="co2fp",
                username="svc",
                client_id="cid",
                secret_id="sid",
                secret_value_encrypted="enc",
            )
        )
        await session.commit()

    # Stub the live probe so the test doesn't hit the network.
    async def _fake_test(db, connector):
        return True, "Connection OK"

    monkeypatch.setattr(ProfessionalTravelApiProvider, "test_connection", _fake_test)

    r = client.post(TEST_URL)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "detail": "Connection OK"}

    rows = await _audit_rows(db_factory, "ConnectorConnection")
    test_rows = [row for row in rows if "test" in (row.change_reason or "").lower()]
    assert len(test_rows) == 1
    snapshot = test_rows[0].data_snapshot
    assert snapshot["test_ok"] is True
    assert snapshot["connector"] == "EPFL_TABLEAU"
    assert "secret_value" not in snapshot
    assert "secret_value_encrypted" not in snapshot
