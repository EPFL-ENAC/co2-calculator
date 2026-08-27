import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.config import RoleProviderType, UnitProviderType
from app.tasks._db_health import DBHealthState

client = TestClient(main.app)


def _state(
    status: str,
    *,
    age_seconds: float = 0.0,
    latency_ms: float = 5.0,
    error: str | None = None,
) -> DBHealthState:
    """Build a DBHealthState as if the background poller had just ticked
    (or, with age_seconds, gone stale a while ago).
    """
    return DBHealthState(
        status=status,
        latency_ms=latency_ms,
        checked_at_monotonic=time.monotonic() - age_seconds,
        error=error,
    )


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert "name" in resp.json()
    assert "version" in resp.json()
    assert "docs" in resp.json()


@pytest.mark.asyncio
async def test_healthz_never_checked_is_still_200(monkeypatch):
    """#2049: liveness never gates on DB state — only the body changes."""
    monkeypatch.setattr("app.main.get_db_health_state", lambda: None)
    resp = await main.healthz()
    assert resp.status_code == 200
    # Parse rather than substring-match: the body is compact JSON, and a
    # byte-level assertion breaks on serializer whitespace alone.
    assert json.loads(resp.body)["database"] == "unknown"


@pytest.mark.asyncio
async def test_healthz_reflects_db_status_without_flipping_status_code(monkeypatch):
    """Body content changes with DB state; the 200 never does (#2049)."""
    for internal, display in [
        ("ok", "ok"),
        ("slow", "sluggish"),
        ("down", "unresponsive"),
    ]:
        monkeypatch.setattr(
            "app.main.get_db_health_state", lambda internal=internal: _state(internal)
        )
        resp = await main.healthz()
        assert resp.status_code == 200
        assert display.encode() in resp.body


@pytest.mark.asyncio
async def test_healthz_stale_state_reported_as_unknown(monkeypatch):
    """A poller that stopped ticking must not report trusted-but-old data."""
    monkeypatch.setattr(
        "app.main.get_db_health_state",
        lambda: _state(
            "ok", age_seconds=main.settings.DB_HEALTH_CHECK_INTERVAL_SECONDS * 10
        ),
    )
    resp = await main.healthz()
    assert resp.status_code == 200
    # Parse rather than substring-match: the body is compact JSON, and a
    # byte-level assertion breaks on serializer whitespace alone.
    assert json.loads(resp.body)["database"] == "unknown"


@pytest.mark.asyncio
async def test_ready_db_ok(monkeypatch):
    monkeypatch.setattr("app.main.get_db_health_state", lambda: _state("ok"))
    resp = await main.ready()
    assert resp.status_code == 200
    assert b"healthy" in resp.body


@pytest.mark.asyncio
async def test_ready_db_slow_still_passes(monkeypatch):
    """Slow must not fail readiness (#2049): DB latency is shared state,
    so gating on it would take every pod unready at once.
    """
    monkeypatch.setattr("app.main.get_db_health_state", lambda: _state("slow"))
    resp = await main.ready()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ready_db_down(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_db_health_state",
        lambda: _state("down", error="connection refused"),
    )
    resp = await main.ready()
    assert resp.status_code == 503
    assert b"unhealthy" in resp.body


@pytest.mark.asyncio
async def test_ready_never_checked_is_unhealthy(monkeypatch):
    """Cold-start window before the poller's first tick must fail closed
    (no-silent-fallbacks), not default to ready.
    """
    monkeypatch.setattr("app.main.get_db_health_state", lambda: None)
    resp = await main.ready()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ready_stale_state_is_unhealthy(monkeypatch):
    """A poller that stopped ticking must not leave /ready trusting old
    'ok' data forever (#2049).
    """
    monkeypatch.setattr(
        "app.main.get_db_health_state",
        lambda: _state(
            "ok", age_seconds=main.settings.DB_HEALTH_CHECK_INTERVAL_SECONDS * 10
        ),
    )
    resp = await main.ready()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_health_deps_role_provider_skipped(monkeypatch):
    # neither ROLE_PROVIDER_TYPE nor UNIT_PROVIDER_TYPE is "accred"
    monkeypatch.setattr(main.settings, "ROLE_PROVIDER_TYPE", RoleProviderType.JWT)
    monkeypatch.setattr(main.settings, "UNIT_PROVIDER_TYPE", UnitProviderType.DATABASE)
    resp = await main.health_deps()
    assert b"skipped" in resp.body
    assert resp.status_code == 200


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
        assert resp.status_code == 200


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
        assert resp.status_code == 503, (
            "health_deps must return 503 on a real dependency failure so "
            "monitoring can key off status code, not just parse the body"
        )


@pytest.mark.asyncio
async def test_health_deps_role_provider_non_200_response(monkeypatch):
    # Accred responds, but with a non-200 status - distinct from the
    # exception path above, same 503 contract.
    monkeypatch.setattr(main.settings, "ROLE_PROVIDER_TYPE", RoleProviderType.ACCRED)
    monkeypatch.setattr(main.settings, "UNIT_PROVIDER_TYPE", UnitProviderType.DATABASE)
    monkeypatch.setattr(
        main.settings, "ACCRED_AUTHORIZATION_HEALTHCHECK_URL", "http://fake"
    )
    monkeypatch.setattr(main.settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(main.settings, "ACCRED_API_KEY", "k")

    mock_resp = MagicMock(status_code=500)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await main.health_deps()
        assert b"error (500)" in resp.body
        assert resp.status_code == 503


def test_main_block(monkeypatch):
    with patch("uvicorn.run") as mock_run:
        main.run_main()
        mock_run.assert_called()
