"""Regression tests for CodeQL security alerts.

- py/stack-trace-exposure: /ready must not return exception details to callers.
- py/log-injection: location search logs must strip newlines from user queries.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.main import ready
from app.models.location import TransportModeEnum
from app.repositories.location_repo import LocationRepository


async def test_ready_response_omits_exception_details():
    with patch("app.db.get_db_session", side_effect=Exception("secret-stack-trace")):
        resp = await ready()
    assert resp.status_code == 503
    assert b"secret-stack-trace" not in resp.body
    assert b"details" not in resp.body


async def test_search_location_error_log_strips_newlines(caplog):
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("boom")
    repo = LocationRepository(session)
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        await repo.search_location("geneva\nFORGED LINE", TransportModeEnum.train)
    assert "\nFORGED" not in caplog.text
    assert "genevaFORGED LINE" in caplog.text
