"""#2049 T5 — event-loop lag probe.

Covers:
- A tick with no contention records ~0 lag (clamped, never negative).
- Loop hygiene mirrors _db_health: a raised exception doesn't kill the
  loop; CancelledError propagates for clean shutdown.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.tasks import _event_loop_lag


@pytest.mark.asyncio
async def test_tick_records_nonnegative_lag(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "EVENT_LOOP_LAG_PROBE_INTERVAL_SECONDS", 0.01)
    recorded = []
    monkeypatch.setattr(
        _event_loop_lag._event_loop_lag_seconds, "record", recorded.append
    )
    await _event_loop_lag._tick(settings)
    assert len(recorded) == 1
    assert recorded[0] >= 0.0


@pytest.mark.asyncio
async def test_loop_survives_iteration_exception():
    """A raised exception from one tick does not kill the loop — mirrors
    _db_health.db_health_check_loop's loop-hygiene contract.
    """
    call_count = {"n": 0}

    async def boom_then_ok(_settings):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient failure")
        raise asyncio.CancelledError()

    with (
        patch("app.tasks._event_loop_lag.get_settings") as gs,
        patch("app.tasks._event_loop_lag._tick", side_effect=boom_then_ok),
    ):
        gs.return_value = MagicMock()
        with pytest.raises(asyncio.CancelledError):
            await _event_loop_lag.event_loop_lag_probe_loop()

    assert call_count["n"] == 2, "loop must continue past the first exception"
