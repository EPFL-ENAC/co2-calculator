from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_health_db_ok(monkeypatch):
    # Mock get_db_session to simulate DB OK
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr("app.db.get_db_session", AsyncMock(return_value=DummySession()))
    monkeypatch.setattr(main.settings, "PROVIDER_PLUGIN", "other")
    resp = await main.health()
    assert resp.status_code == 200
    assert resp.body
    assert b"healthy" in resp.body


@pytest.mark.asyncio
async def test_health_db_error(monkeypatch):
    # Mock get_db_session to raise error
    async def raise_exc():
        raise Exception("db fail")

    monkeypatch.setattr("app.db.get_db_session", raise_exc)
    monkeypatch.setattr(main.settings, "PROVIDER_PLUGIN", "other")
    resp = await main.health()
    assert resp.status_code == 503
    assert b"unhealthy" in resp.body


@pytest.mark.asyncio
async def test_health_role_provider_skipped(monkeypatch):
    # PROVIDER_PLUGIN != "accred"
    monkeypatch.setattr("app.db.get_db_session", AsyncMock())
    monkeypatch.setattr(main.settings, "PROVIDER_PLUGIN", "other")
    resp = await main.health()
    assert b"skipped" in resp.body


@pytest.mark.asyncio
async def test_health_role_provider_ok(monkeypatch):
    # PROVIDER_PLUGIN == "accred" and health returns 200
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr("app.db.get_db_session", AsyncMock(return_value=DummySession()))
    monkeypatch.setattr(main.settings, "PROVIDER_PLUGIN", "accred")
    monkeypatch.setattr(main.settings, "ACCRED_API_HEALTH_URL", "http://fake")
    monkeypatch.setattr(main.settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(main.settings, "ACCRED_API_KEY", "k")

    mock_resp = MagicMock(status_code=200)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await main.health()
        assert b"ok" in resp.body


@pytest.mark.asyncio
async def test_health_role_provider_error(monkeypatch):
    # PROVIDER_PLUGIN == "accred" and health raises error
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr("app.db.get_db_session", AsyncMock(return_value=DummySession()))
    monkeypatch.setattr(main.settings, "PROVIDER_PLUGIN", "accred")
    monkeypatch.setattr(main.settings, "ACCRED_API_HEALTH_URL", "http://fake")
    monkeypatch.setattr(main.settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(main.settings, "ACCRED_API_KEY", "k")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = Exception("fail")

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await main.health()
        assert b"error" in resp.body


def test_main_block(monkeypatch):
    with patch("uvicorn.run") as mock_run:
        main.run_main()
        mock_run.assert_called()
