"""Tests for BaseTableauApiProvider DB-backed credential loading (#1552).

Exercises the real ``_ensure_credentials`` path against a seeded
``ConnectorConnection`` + ``ConnectorDatasource`` in an in-memory SQLite DB.
Only the network hop (``_signin_with_jwt``) is monkeypatched — JWT signing,
SSRF re-validation, and DB loading all run for real.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import crypto, url_safety
from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.models.connector import (
    ConnectorConnection,
    ConnectorDatasource,
    ConnectorType,
)
from app.models.data_entry import BULK_PER_YEAR_SOURCES, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
)

SERVER_URL = "https://tableau.epfl.ch/"
SECRET_VALUE = "secretvalue1234567890123456789012"


class _StubTableauProvider(BaseTableauApiProvider):
    """Minimal concrete subclass so the abstract base can be instantiated."""

    CONNECTOR = ConnectorType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.professional_travel
    DATA_ENTRY_TYPE = DataEntryTypeEnum.plane
    REQUIRED_CAPTIONS: list[str] = []

    async def transform_data(self, raw_data):
        return raw_data

    async def _load_data(self, data):
        return {"inserted": len(data)}


@pytest.fixture(autouse=True)
def _crypto_env(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()
    get_settings.cache_clear()
    yield
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_connection(s: AsyncSession) -> ConnectorConnection:
    conn = ConnectorConnection(
        connector=ConnectorType.EPFL_TABLEAU,
        label="EPFL Tableau",
        server_url=SERVER_URL,
        site_content_url="co2fp",
        username="svc-account",
        client_id="cid",
        secret_id="sid",
        secret_value_encrypted=encrypt_secret(SECRET_VALUE),
    )
    s.add(conn)
    await s.flush()
    return conn


async def _seed_datasource(s: AsyncSession, connection_id: int) -> None:
    ds = ConnectorDatasource(
        connection_id=connection_id,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=None,
        connector_luid="ds-luid-123",
        label="Flights",
    )
    s.add(ds)
    await s.flush()


def _make_provider(session: AsyncSession) -> _StubTableauProvider:
    return _StubTableauProvider(
        {"module_type_id": int(ModuleTypeEnum.professional_travel), "year": 2024},
        None,
        None,
        data_session=session,
    )


async def test_validate_connection_true_with_seeded_connection(session, monkeypatch):
    conn = await _seed_connection(session)
    assert conn.id is not None
    await _seed_datasource(session, conn.id)

    provider = _make_provider(session)
    monkeypatch.setattr(
        provider, "_signin_with_jwt", AsyncMock(return_value="x-auth-token")
    )

    assert await provider.validate_connection() is True
    # Credentials were loaded from the DB, not the environment.
    assert provider.server_url == SERVER_URL
    assert provider.secret_value == SECRET_VALUE
    assert provider.datasource_luid == "ds-luid-123"
    assert provider.username == "svc-account"


async def test_validate_connection_raises_without_connection(session, monkeypatch):
    provider = _make_provider(session)
    monkeypatch.setattr(
        provider, "_signin_with_jwt", AsyncMock(return_value="x-auth-token")
    )

    with pytest.raises(ValueError, match="No EPFL_TABLEAU connection configured"):
        await provider.validate_connection()


async def test_ensure_credentials_raises_without_datasource(session):
    await _seed_connection(session)  # connection but no datasource

    provider = _make_provider(session)
    with pytest.raises(ValueError, match="No datasource"):
        await provider._ensure_credentials()


async def test_test_connection_undecryptable_secret_returns_generic(session):
    """A rotated/corrupt secret must not 500: the Fernet decrypt now runs
    inside ``test_connection``'s try, so a garbage ``secret_value_encrypted``
    yields ``(False, <generic detail>)`` with no exception text leaked.
    """
    conn = ConnectorConnection(
        connector=ConnectorType.EPFL_TABLEAU,
        label="EPFL Tableau",
        server_url=SERVER_URL,
        site_content_url="co2fp",
        username="svc-account",
        client_id="cid",
        secret_id="sid",
        # Not a valid Fernet token → decrypt raises InvalidToken.
        secret_value_encrypted="not-a-valid-fernet-token",
    )
    session.add(conn)
    await session.flush()

    ok, detail = await _StubTableauProvider.test_connection(
        session, ConnectorType.EPFL_TABLEAU
    )
    assert ok is False
    assert detail == "Connection test failed"
    # Generic detail only — never the raw exception / token material.
    assert "not-a-valid-fernet-token" not in detail
    assert "InvalidToken" not in detail


async def test_ensure_credentials_is_idempotent(session, monkeypatch):
    conn = await _seed_connection(session)
    assert conn.id is not None
    await _seed_datasource(session, conn.id)

    provider = _make_provider(session)
    await provider._ensure_credentials()
    # Second call must be a no-op (guard flag) — swap the service so a
    # reload would blow up, proving we don't hit the DB twice.
    provider.datasource_luid = "sentinel"
    await provider._ensure_credentials()
    assert provider.datasource_luid == "sentinel"


async def test_delete_existing_api_entries_replaces_same_year_and_type(session):
    provider = _make_provider(session)
    delete = AsyncMock(return_value=7)

    with patch(
        "app.services.data_ingestion.api_providers."
        "base_tableau_api_provider.DataEntryService",
        return_value=SimpleNamespace(
            repo=SimpleNamespace(bulk_delete_by_source_year=delete)
        ),
    ):
        deleted = await provider._delete_existing_api_entries()

    assert deleted == 7
    # Cross-source replace: an API sync also replaces prior per-year CSV
    # uploads, so the two bulk mechanisms never collide on duplicates.
    delete.assert_awaited_once_with(
        year=2024,
        data_entry_type_ids=[DataEntryTypeEnum.plane.value],
        sources=[s.value for s in BULK_PER_YEAR_SOURCES],
    )
