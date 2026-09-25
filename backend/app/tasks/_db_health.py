"""In-process DB health poller (#2049).

``/ready`` used to run its own bounded ``SELECT 1`` per probe (#2050 A1) —
correct, but every probe still paid a real DB round trip, and a saturated
pool made every one of them queue for a connection. This loop runs the
same check every ``DB_HEALTH_CHECK_INTERVAL_SECONDS`` in the background
and caches the verdict in a module-global; ``/ready``/``/healthz`` then
read memory, doing zero I/O of their own. Mirrors ``_pod_heartbeat.py``'s
shape (first tick before sleep, per-iteration try/except so a transient DB
hiccup can't kill the loop).

Single process per pod (no gunicorn workers — see plan 2050's Track A
rejected alternatives), so a bare module-global needs no lock: only this
loop ever writes it, and a single name rebind is atomic under the GIL.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from sqlmodel import text

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db import SessionLocal

logger = get_logger(__name__)

# Bare constant, not a Settings field — this PR's own /ready rewrite
# deleted the equivalent per-request constant from main.py
# (READY_DB_TIMEOUT_SECONDS), so there's no live symbol to point to
# anymore; kept as a constant since it never needs per-environment
# tuning. Bounds each check so a saturated pool can't make an iteration
# hang; a timeout here surfaces as status "down", same as any other DB
# failure.
DB_HEALTH_CHECK_TIMEOUT_SECONDS = 1

# Until the first ok/slow check, retry this often instead of the (long)
# interval: a pod booted during a DB blip then turns ready at the next
# readiness probe (every 10 s) after the DB recovers. A healthy boot never
# pays it — its first check already succeeds.
DB_HEALTH_BOOT_RETRY_SECONDS = 5

# A cached verdict older than this multiple of the check interval (plus
# one check timeout) means the loop stopped ticking (crashed, or
# RUN_DB_HEALTH_POLLER is off) — treated as unknown rather than trusted
# stale data.
_STALE_AFTER_INTERVALS = 3


@dataclass(frozen=True)
class DBHealthState:
    status: Literal["ok", "slow", "down"]
    latency_ms: float
    checked_at_monotonic: float
    error: str | None = None


_state: DBHealthState | None = None

# Set by the first ok/slow check, never cleared: /ready's boot gate must not
# re-arm when the shared DB later goes down, or every pod leaves together.
_ever_healthy = False

# The in-flight SELECT 1, kept as a module global so a hung probe is neither
# garbage-collected nor duplicated: the next tick re-awaits it instead of
# stacking a second connection behind the same stall (#2689).
_probe: asyncio.Task[tuple[float, str | None]] | None = None
_probe_started_at: float = 0.0


def get_db_health_state() -> DBHealthState | None:
    """Current cached verdict, or None if the loop hasn't ticked yet.

    A getter, not a re-exported module attribute: ``from _db_health import
    _state`` would bind the value present at import time, not future
    reassignments — callers must go through this function to see updates.
    """
    return _state


def db_ever_healthy() -> bool:
    """Whether any check since process start came back ok or slow. A getter
    for the same reason as ``get_db_health_state``.
    """
    return _ever_healthy


def is_fresh(state: DBHealthState, *, interval_seconds: int) -> bool:
    """False once the loop has stopped ticking for _STALE_AFTER_INTERVALS
    cycles — e.g. the task crashed, or RUN_DB_HEALTH_POLLER is off while
    something still reads the cache. monotonic(), not wall-clock: an NTP
    step must not false-trip this.
    """
    age = time.monotonic() - state.checked_at_monotonic
    # A hung DB stretches each tick to interval + timeout; without the
    # timeout term a short interval leaves almost no slack before a live
    # loop reads as dead.
    return age <= _STALE_AFTER_INTERVALS * interval_seconds + (
        DB_HEALTH_CHECK_TIMEOUT_SECONDS
    )


async def _run_probe() -> tuple[float, str | None]:
    """One SELECT 1 on its own connection: (latency_ms, error). Never
    raises, so an abandoned probe never leaves an unretrieved exception.
    """
    start = time.monotonic()
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        return (time.monotonic() - start) * 1000, str(e) or type(e).__name__
    return (time.monotonic() - start) * 1000, None


def _current_probe() -> asyncio.Task[tuple[float, str | None]]:
    global _probe, _probe_started_at
    if _probe is None or _probe.done():
        _probe = asyncio.create_task(_run_probe(), name="db-health-probe")
        _probe_started_at = time.monotonic()
    return _probe


async def _check_once(settings: Settings) -> None:
    """Wait up to DB_HEALTH_CHECK_TIMEOUT_SECONDS for the probe, classify
    it, and update the cached state.

    The probe runs as its own task and is only *waited for*, never
    cancelled: cancelling a SQLAlchemy call mid-checkout blocks in the
    connection teardown for as long as the DB is unreachable (2 min behind
    the DBaaS PgBouncer on 2026-09-08), which froze this loop and left
    /ready at 503 for every wave (#2689). A probe that outlives the wait is
    reported "down" now and re-awaited on the next tick.

    Never raises (except CancelledError) — a failed or timed-out check is a
    valid, expected outcome (status "down"), not a bug.
    """
    global _state, _ever_healthy
    probe = _current_probe()
    try:
        latency_ms, error = await asyncio.wait_for(
            asyncio.shield(probe), DB_HEALTH_CHECK_TIMEOUT_SECONDS
        )
    except TimeoutError:
        latency_ms = (time.monotonic() - _probe_started_at) * 1000
        error = "TimeoutError"

    status: Literal["ok", "slow", "down"] = "ok"
    if error is not None:
        status = "down"
    if error is None and latency_ms >= settings.DB_HEALTH_SLOW_THRESHOLD_MS:
        status = "slow"
    if error is None:
        _ever_healthy = True

    _state = DBHealthState(
        status=status,
        latency_ms=latency_ms,
        checked_at_monotonic=time.monotonic(),
        error=error,
    )


def _next_delay_seconds(interval: int) -> int:
    """The configured interval, or the short boot retry while the DB has
    never answered (never longer than the interval itself).
    """
    delay = interval
    if not _ever_healthy:
        delay = min(interval, DB_HEALTH_BOOT_RETRY_SECONDS)
    return delay


async def db_health_check_loop() -> None:
    """Run the DB health check on the configured cadence forever."""
    settings = get_settings()
    interval = settings.DB_HEALTH_CHECK_INTERVAL_SECONDS
    # First tick before the sleep so /ready isn't stuck at "never
    # checked" (503) for a full interval after the pod starts. Guarded
    # the same as every later tick — mirrors _pod_heartbeat_loop's
    # separately-guarded first tick — even though _check_once already
    # catches its own errors; belt-and-suspenders against a future edit
    # there breaking that invariant and killing the loop at boot.
    try:
        await _check_once(settings)
    except Exception:
        logger.warning(
            "db health check initial tick failed unexpectedly", exc_info=True
        )
    while True:
        try:
            await asyncio.sleep(_next_delay_seconds(interval))
            await _check_once(settings)
        except asyncio.CancelledError:
            if _probe is not None and not _probe.done():
                _probe.cancel()
            raise
        except Exception:
            logger.warning(
                "db health check iteration failed unexpectedly", exc_info=True
            )
