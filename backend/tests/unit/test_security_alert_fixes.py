"""Regression tests for CodeQL security alerts.

- py/stack-trace-exposure: /ready and /health/deps must not return exception
  details to callers.
- py/log-injection: location search logs must strip newlines from user queries.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import RoleProviderType
from app.main import health_deps, ready, settings
from app.models.location import TransportModeEnum
from app.repositories.location_repo import LocationRepository


async def test_ready_response_omits_exception_details():
    with patch("app.db.get_db_session", side_effect=Exception("secret-stack-trace")):
        resp = await ready()
    assert resp.status_code == 503
    assert b"secret-stack-trace" not in resp.body
    assert b"details" not in resp.body


async def test_health_deps_response_omits_exception_details(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ROLE_PROVIDER_TYPE", RoleProviderType.ACCRED)
    monkeypatch.setattr(settings, "ACCRED_AUTHORIZATION_HEALTHCHECK_URL", "http://x")
    monkeypatch.setattr(settings, "ACCRED_API_USERNAME", "u")
    monkeypatch.setattr(settings, "ACCRED_API_KEY", "k")
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = Exception("secret-stack-trace")

    with (
        patch("httpx.AsyncClient", return_value=client),
        caplog.at_level(logging.WARNING),
    ):
        resp = await health_deps()

    assert resp.status_code == 503
    assert b"secret-stack-trace" not in resp.body
    record = next(
        r for r in caplog.records if r.getMessage() == "Accred health check failed"
    )
    # repr, not str: httpx timeouts have an empty str(e), which logs no reason.
    assert record.__dict__["role_provider_error"] == repr(client.get.side_effect)


async def test_search_location_error_log_strips_newlines(caplog):
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("boom")
    repo = LocationRepository(session)
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        await repo.search_location("geneva\nFORGED LINE", TransportModeEnum.train)
    assert "\nFORGED" not in caplog.text
    assert "genevaFORGED LINE" in caplog.text
