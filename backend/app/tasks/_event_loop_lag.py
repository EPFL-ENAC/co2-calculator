"""Event-loop lag probe (#2049, T5).

683 ms of CPU-bound taxonomy-response serialisation was measured blocking
the event loop under load (#1402's investigation), but nothing in this
app had ever measured that directly — every existing latency number is
traffic-shaped (volume, payload size, client speed all confound it).
This is the clean test: ask the loop to sleep for exactly ``interval``
seconds: any excess over that is scheduling delay, i.e. the loop was busy
doing something else. Immune to traffic volume, client speed and payload
size — none of those things exist in this measurement.

Mirrors ``_db_health.py``'s loop shape (per-iteration try/except so one
bad tick can't kill the loop; ``CancelledError`` propagates for clean
shutdown). No cached state to expose here — unlike DB health, nothing
reads this synchronously; it only ever needs to reach the OTel exporter.
"""

import asyncio
import time

from opentelemetry.metrics import get_meter

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_event_loop_lag_seconds = get_meter(__name__).create_histogram(
    "event_loop_lag_seconds",
    unit="s",
    description=(
        "Drift between a requested and actual asyncio.sleep duration -- "
        "a direct measure of event-loop scheduling delay, independent of "
        "request volume, payload size or client speed."
    ),
)


async def _tick(settings: Settings) -> None:
    interval = settings.EVENT_LOOP_LAG_PROBE_INTERVAL_SECONDS
    start = time.perf_counter()
    await asyncio.sleep(interval)
    # asyncio.sleep never returns early, so lag is >=0 barring clock
    # weirdness; clamp defensively rather than ever recording a negative
    # duration into a histogram.
    lag = max(time.perf_counter() - start - interval, 0.0)
    _event_loop_lag_seconds.record(lag)


async def event_loop_lag_probe_loop() -> None:
    """Record event-loop scheduling lag on the configured cadence forever."""
    settings = get_settings()
    while True:
        try:
            await _tick(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "event loop lag probe iteration failed unexpectedly",
                exc_info=True,
            )
