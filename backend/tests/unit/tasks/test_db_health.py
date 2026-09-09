"""#2049 — background DB health poller.

Covers the classification logic /ready and /healthz now depend on
entirely (they do no DB I/O of their own):

- SELECT 1 under the threshold -> "ok", over it -> "slow", failing or
  hanging -> "down".
- A hung checkout is bounded by DB_HEALTH_CHECK_TIMEOUT_SECONDS — the
  same failure mode #2050 A1 fixed for /ready's old per-request check,
  now guarded here instead (regression test, mirrors the deleted
  test_ready_db_timeout_is_bounded).
- Loop hygiene mirrors _pipeline_reconciler: a raised exception doesn't
  kill the loop; CancelledError propagates for clean shutdown.
- #2689: a probe whose teardown hangs after the timeout (SQLAlchemy
  cancelled mid-checkout behind a stalled PgBouncer) must not freeze the
  loop -- the tick reports "down" on time and the next tick re-awaits the
  same probe instead of stacking another connection behind it.
"""

import asyncio
import contextlib
import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.tasks import _db_health
from app.tasks._db_health import DBHealthState, is_fresh


class _Session:
    """Async-context-manager stub for ``async with SessionLocal() as s``."""

    def __init__(self, *, delay: float = 0.0, error: Exception | None = None):
        self._delay = delay
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def execute(self, *a, **k):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error


@pytest.fixture(autouse=True)
async def _drop_leftover_probe():
    """Neither a probe that outlives its test nor a fresh verdict may leak
    into the next test: /ready reads the same module global.
    """
    yield
    probe = getattr(_db_health, "_probe", None)
    _db_health._probe = None
    _db_health._state = None
    if probe is not None and not probe.done():
        probe.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            _ = await probe


class _StuckTeardownSession(_Session):
    """Models SQLAlchemy behind a stalled bouncer: the cancel from the
    1 s timeout lands, but the connection teardown then blocks until the
    server answers (120 s on 2026-09-08). Here: swallow the cancel, hang
    ``hang`` more seconds, then finish normally.
    """

    created = 0

    def __init__(self, *, hang: float):
        super().__init__(delay=60)
        self._hang = hang
        type(self).created += 1

    async def execute(self, *a, **k):
        try:
            await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            await asyncio.sleep(self._hang)


@pytest.mark.asyncio
async def test_check_once_marks_ok_under_threshold(monkeypatch):
    monkeypatch.setattr(_db_health, "SessionLocal", _Session)
    settings = get_settings()
    monkeypatch.setattr(settings, "DB_HEALTH_SLOW_THRESHOLD_MS", 10_000)
    await _db_health._check_once(settings)
    state = _db_health.get_db_health_state()
    assert state.status == "ok"
    assert state.error is None


@pytest.mark.asyncio
async def test_check_once_marks_slow_over_threshold(monkeypatch):
    monkeypatch.setattr(_db_health, "SessionLocal", _Session)
    settings = get_settings()
    monkeypatch.setattr(settings, "DB_HEALTH_SLOW_THRESHOLD_MS", 0)
    await _db_health._check_once(settings)
    assert _db_health.get_db_health_state().status == "slow"


@pytest.mark.asyncio
async def test_check_once_marks_down_on_error(monkeypatch):
    monkeypatch.setattr(
        _db_health,
        "SessionLocal",
        lambda: _Session(error=RuntimeError("connection refused")),
    )
    settings = get_settings()
    await _db_health._check_once(settings)
    state = _db_health.get_db_health_state()
    assert state.status == "down"
    assert "connection refused" in state.error


@pytest.mark.asyncio
async def test_check_once_is_bounded_by_its_own_timeout(monkeypatch):
    """Regression: a hung checkout (saturated pool) must not outlive
    DB_HEALTH_CHECK_TIMEOUT_SECONDS.
    """
    monkeypatch.setattr(
        _db_health,
        "SessionLocal",
        lambda: _Session(delay=_db_health.DB_HEALTH_CHECK_TIMEOUT_SECONDS + 5),
    )
    settings = get_settings()
    start = time.monotonic()
    await asyncio.wait_for(
        _db_health._check_once(settings),
        timeout=_db_health.DB_HEALTH_CHECK_TIMEOUT_SECONDS + 2,
    )
    elapsed = time.monotonic() - start
    assert elapsed < _db_health.DB_HEALTH_CHECK_TIMEOUT_SECONDS + 1
    assert _db_health.get_db_health_state().status == "down"


@pytest.mark.asyncio
async def test_stuck_probe_teardown_does_not_freeze_the_loop(monkeypatch):
    """Regression #2689: with the old ``asyncio.timeout`` around the
    session, the cancelled checkout blocked in teardown and ``_check_once``
    itself took the whole hang -- /ready reported "unknown" for two minutes
    per PgBouncer wave. Now the tick returns on time, reports "down", the
    next tick re-awaits the same probe (no second connection queued behind
    the stall), and a fresh probe runs once the stuck one has drained.
    """
    _StuckTeardownSession.created = 0
    hang = 1.5
    monkeypatch.setattr(
        _db_health, "SessionLocal", lambda: _StuckTeardownSession(hang=hang)
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "DB_HEALTH_SLOW_THRESHOLD_MS", 10_000)
    budget = _db_health.DB_HEALTH_CHECK_TIMEOUT_SECONDS + 0.5

    start = time.monotonic()
    await asyncio.wait_for(_db_health._check_once(settings), timeout=budget)
    assert time.monotonic() - start < budget
    assert _db_health.get_db_health_state().status == "down"
    assert _db_health.get_db_health_state().error == "TimeoutError"

    # Second tick while the first probe is still hanging: still bounded,
    # still "down", and no second session was opened.
    await asyncio.wait_for(_db_health._check_once(settings), timeout=budget)
    assert _db_health.get_db_health_state().status == "down"
    assert _StuckTeardownSession.created == 1

    # Once the stuck probe drains, the next tick starts a fresh one.
    await asyncio.wait_for(_db_health._probe, timeout=hang + 1)
    monkeypatch.setattr(_db_health, "SessionLocal", _Session)
    await _db_health._check_once(settings)
    assert _db_health.get_db_health_state().status == "ok"


def test_is_fresh_true_within_window():
    state = DBHealthState(
        status="ok", latency_ms=1.0, checked_at_monotonic=time.monotonic()
    )
    assert is_fresh(state, interval_seconds=1)


def test_is_fresh_false_once_stale():
    state = DBHealthState(
        status="ok", latency_ms=1.0, checked_at_monotonic=time.monotonic() - 10
    )
    assert not is_fresh(state, interval_seconds=1)


@pytest.mark.asyncio
async def test_loop_survives_iteration_exception():
    """A raised exception from one tick does not kill the loop — mirrors
    _pipeline_reconciler's loop-hygiene contract.
    """
    call_count = {"n": 0}

    async def boom_then_ok(_settings):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient failure")

    async def fake_sleep(*_a, **_kw):
        if call_count["n"] >= 2:
            raise asyncio.CancelledError()

    with (
        patch("app.tasks._db_health.get_settings") as gs,
        patch("app.tasks._db_health._check_once", side_effect=boom_then_ok),
        patch("app.tasks._db_health.asyncio.sleep", side_effect=fake_sleep),
    ):
        gs.return_value = MagicMock(DB_HEALTH_CHECK_INTERVAL_SECONDS=0)
        with pytest.raises(asyncio.CancelledError):
            await _db_health.db_health_check_loop()

    assert call_count["n"] == 2, "loop must continue past the first exception"
