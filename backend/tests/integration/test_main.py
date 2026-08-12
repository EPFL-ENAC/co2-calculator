import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.config import RoleProviderType, UnitProviderType

client = TestClient(main.app)


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert "name" in resp.json()
    assert "version" in resp.json()
    assert "docs" in resp.json()


@pytest.mark.asyncio
async def test_healthz():
    """Test lightweight liveness check endpoint."""
    resp = await main.healthz()
    assert resp.status_code == 200
    assert resp.body
    data = resp.body
    assert b'"status": "ok"' in data or b'"status":"ok"' in data


@pytest.mark.asyncio
async def test_ready_db_ok(monkeypatch):
    # Mock get_db_session to simulate DB OK
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr("app.db.get_db_session", AsyncMock(return_value=DummySession()))
    resp = await main.ready()
    assert resp.status_code == 200
    assert resp.body
    assert b"healthy" in resp.body


@pytest.mark.asyncio
async def test_ready_db_error(monkeypatch):
    # Mock get_db_session to raise error
    async def raise_exc():
        raise Exception("db fail")

    monkeypatch.setattr("app.db.get_db_session", raise_exc)
    resp = await main.ready()
    assert resp.status_code == 503
    assert b"unhealthy" in resp.body


@pytest.mark.asyncio
async def test_ready_db_timeout_is_bounded(monkeypatch):
    """A hung DB check must not outlive READY_DB_TIMEOUT_SECONDS (#2050 A1).

    Regression test: before the fix, /ready awaited get_db_session()'s
    query with no bound, so a saturated pool (DB_POOL_TIMEOUT defaults to
    30s) could make /ready hang past the k8s probe's own timeoutSeconds,
    taking a healthy pod out of Service rotation. Simulates that hang and
    asserts ready() resolves on its own well under the bound, with a 503
    — not that the test's own outer timeout fires first.
    """

    class HangingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def execute(self, *a, **k):
            await asyncio.sleep(main.READY_DB_TIMEOUT_SECONDS + 5)

    monkeypatch.setattr(
        "app.db.get_db_session", AsyncMock(return_value=HangingSession())
    )

    start = asyncio.get_event_loop().time()
    resp = await asyncio.wait_for(
        main.ready(), timeout=main.READY_DB_TIMEOUT_SECONDS + 2
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert resp.status_code == 503
    assert elapsed < main.READY_DB_TIMEOUT_SECONDS + 1


@pytest.mark.asyncio
async def test_health_deps_role_provider_skipped(monkeypatch):
    # neither ROLE_PROVIDER_TYPE nor UNIT_PROVIDER_TYPE is "accred"
    monkeypatch.setattr(main.settings, "ROLE_PROVIDER_TYPE", RoleProviderType.JWT)
    monkeypatch.setattr(main.settings, "UNIT_PROVIDER_TYPE", UnitProviderType.DATABASE)
    resp = await main.health_deps()
    assert b"skipped" in resp.body


@pytest.mark.asyncio
async def test_health_deps_role_provider_ok(monkeypatch):
    # ROLE_PROVIDER_TYPE == "accred" and health returns 200
    monkeypatch.setattr(main.settings, "ROLE_PROVIDER_TYPE", RoleProviderType.ACCRED)
    monkeypatch.setattr(main.settings, "UNIT_PROVIDER_TYPE", UnitProviderType.DATABASE)
    monkeypatch.setattr(
        main.settings, "ACCRED_AUTHORIZATION_HEALTHCHECK_URL", "http://fake"
    )
    monkeypatch.setattr(main.settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(main.settings, "ACCRED_API_KEY", "k")

    mock_resp = MagicMock(status_code=200)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await main.health_deps()
        assert b"ok" in resp.body


@pytest.mark.asyncio
async def test_health_deps_role_provider_error(monkeypatch):
    # ROLE_PROVIDER_TYPE == "accred" and health raises error
    monkeypatch.setattr(main.settings, "ROLE_PROVIDER_TYPE", RoleProviderType.ACCRED)
    monkeypatch.setattr(main.settings, "UNIT_PROVIDER_TYPE", UnitProviderType.DATABASE)
    monkeypatch.setattr(
        main.settings, "ACCRED_AUTHORIZATION_HEALTHCHECK_URL", "http://fake"
    )
    monkeypatch.setattr(main.settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(main.settings, "ACCRED_API_KEY", "k")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = Exception("fail")

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await main.health_deps()
        assert b"error" in resp.body


def test_main_block(monkeypatch):
    with patch("uvicorn.run") as mock_run:
        main.run_main()
        mock_run.assert_called()
