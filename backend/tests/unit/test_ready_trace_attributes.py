"""/ready must put its cached DB verdict on the active span (#2566 follow-up).

The endpoint does zero I/O by design (#2049): the failing work lives in the
uninstrumented background health loop and never joins the request trace, so a
/ready 503 trace was a single ~1.5ms span with no cause attached — observed
useless during the 2026-08-31 incident review. The handler holds the verdict
in memory when it answers; these tests pin that it hands the cause to the
tracer on failure, and stays quiet on success.
"""

import time
from typing import Literal
from unittest.mock import MagicMock, patch

from app.main import ready
from app.tasks._db_health import DBHealthState


def _state(
    status: Literal["ok", "slow", "down"], error: str | None = None
) -> DBHealthState:
    return DBHealthState(
        status=status,
        latency_ms=12.5,
        checked_at_monotonic=time.monotonic(),
        error=error,
    )


async def test_failing_ready_attaches_the_verdict_to_the_span():
    span = MagicMock()
    down = _state("down", error="connection failed: FATAL: 53300")
    with (
        patch("app.main._fresh_db_state", return_value=down),
        patch("app.main.trace.get_current_span", return_value=span),
    ):
        resp = await ready()

    assert resp.status_code == 503
    span.set_attributes.assert_called_once_with(
        {
            "db.health.status": "down",
            "db.health.error": "connection failed: FATAL: 53300",
            "db.health.latency_ms": 12.5,
        }
    )
    # The security boundary from test_security_alert_fixes still holds: the
    # error goes to the span (internal telemetry), never the response body.
    assert b"53300" not in resp.body


async def test_healthy_ready_adds_no_span_attributes():
    span = MagicMock()
    with (
        patch("app.main._fresh_db_state", return_value=_state("ok")),
        patch("app.main.trace.get_current_span", return_value=span),
    ):
        resp = await ready()

    assert resp.status_code == 200
    span.set_attributes.assert_not_called()


async def test_never_checked_reports_unknown_to_the_span():
    span = MagicMock()
    with (
        patch("app.main._fresh_db_state", return_value=None),
        patch("app.main.trace.get_current_span", return_value=span),
    ):
        resp = await ready()

    assert resp.status_code == 503
    span.set_attributes.assert_called_once_with(
        {
            "db.health.status": "unknown",
            "db.health.error": "",
            "db.health.latency_ms": -1.0,
        }
    )
