import time
from unittest.mock import AsyncMock, patch

import pytest

from app.core import crypto, url_safety
from app.models.connector import ConnectorType
from app.schemas.connector import ConnectorConnectionCreate
from app.services.connector_service import ConnectorConnectionService


@pytest.mark.asyncio
async def test_save_encrypts_blank_keeps_and_read_hides_secret(db_session, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    # SSRF guard fails closed by default (empty allowlist); the service always
    # validates server_url, so the happy path needs it configured too.
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()

    service = ConnectorConnectionService(db_session)
    base = ConnectorConnectionCreate(
        label="EPFL Tableau",
        server_url="https://tableau.epfl.ch/",
        site_content_url="co2fp",
        username="svc-calcco2-epfl-api",
        client_id="cid",
        secret_id="sid",
        secret_value="the-real-secret",
    )
    conn = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()
    assert conn.secret_value_encrypted != "the-real-secret"
    assert await service.get_decrypted_secret(conn) == "the-real-secret"

    # blank secret on update keeps the stored value
    base.username = "changed"
    base.secret_value = None
    conn2 = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()
    assert conn2.username == "changed"
    assert await service.get_decrypted_secret(conn2) == "the-real-secret"

    read = service.to_read(conn2)
    assert read.has_secret is True
    assert not hasattr(read, "secret_value")


@pytest.mark.asyncio
async def test_save_connection_advances_updated_at(db_session, monkeypatch):
    """The ``onupdate`` hook must bump ``updated_at`` on every save so the
    column stops being frozen at first-write time.
    """
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()

    service = ConnectorConnectionService(db_session)
    base = ConnectorConnectionCreate(
        label="EPFL Tableau",
        server_url="https://tableau.epfl.ch/",
        site_content_url="co2fp",
        username="svc-calcco2-epfl-api",
        client_id="cid",
        secret_id="sid",
        secret_value="the-real-secret",
    )
    conn = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()
    first_updated_at = conn.updated_at

    # Force a distinct wall-clock so the onupdate timestamp is provably newer
    # (sub-ms flushes could otherwise land on the same value).
    time.sleep(0.01)

    base.username = "changed"
    conn2 = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)
    await db_session.commit()

    assert conn2.username == "changed"
    assert conn2.updated_at > first_updated_at


@pytest.mark.asyncio
async def test_save_rejects_disallowed_server_url(db_session, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()

    service = ConnectorConnectionService(db_session)
    with pytest.raises(ValueError):
        await service.save_connection(
            ConnectorType.EPFL_TABLEAU,
            ConnectorConnectionCreate(
                label="x",
                server_url="https://tableau.evil.com/",
                username="u",
                client_id="c",
                secret_id="s",
                secret_value="v",
            ),
        )


@pytest.mark.asyncio
async def test_encrypt_and_decrypt_dispatch_via_to_thread(db_session, monkeypatch):
    """#2050 Track I3 regression: the Scrypt KDF is deliberately CPU-heavy
    and must never run inline on the event loop — proves the dispatch
    itself, not just the round-tripped value (which would pass identically
    whether or not `to_thread` is used).
    """
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt")
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", "epfl.ch")
    crypto.get_settings.cache_clear()
    url_safety.get_settings.cache_clear()

    service = ConnectorConnectionService(db_session)
    base = ConnectorConnectionCreate(
        label="EPFL Tableau",
        server_url="https://tableau.epfl.ch/",
        username="u",
        client_id="c",
        secret_id="s",
        secret_value="the-real-secret",
    )

    with patch(
        "app.services.connector_service.asyncio.to_thread",
        new=AsyncMock(return_value="encrypted-token"),
    ) as mock_to_thread:
        conn = await service.save_connection(ConnectorType.EPFL_TABLEAU, base)

    mock_to_thread.assert_called_once_with(crypto.encrypt_secret, "the-real-secret")
    assert conn.secret_value_encrypted == "encrypted-token"

    with patch(
        "app.services.connector_service.asyncio.to_thread",
        new=AsyncMock(return_value="the-real-secret"),
    ) as mock_to_thread:
        result = await service.get_decrypted_secret(conn)

    mock_to_thread.assert_called_once_with(crypto.decrypt_secret, "encrypted-token")
    assert result == "the-real-secret"
