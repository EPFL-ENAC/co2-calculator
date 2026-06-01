"""#1236 Phase 3 — pipeline reconciliation cron loop.

Covers the loop-hygiene contract that makes the sweep safe under the
"runner missed the post-finish write" hazard the cron exists to heal:

- The loop awaits the sweep, then ``asyncio.sleep(interval)``.
- A raised exception from one iteration does NOT kill the loop.
- ``CancelledError`` from ``sleep`` propagates so the lifespan shutdown
  can await the loop cleanly.
- A quiet sweep (corrected=0) does NOT spam logs.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _short_interval():
    """Force a tiny sleep so the loop cycles fast under test."""
    with patch("app.tasks._pipeline_reconciler.get_settings") as gs:
        gs.return_value = MagicMock(PIPELINE_RECONCILER_INTERVAL_SECONDS=0)
        yield


@pytest.mark.asyncio
async def test_loop_calls_reconcile_and_sleeps():
    """Happy path — one full iteration, then sleep."""
    from app.tasks._pipeline_reconciler import reconcile_pipeline_statuses_loop

    sleep_called = asyncio.Event()

    async def fake_sleep(*_a, **_kw):
        sleep_called.set()
        raise asyncio.CancelledError()  # break out after one tick

    with (
        patch("app.tasks._pipeline_reconciler.DataIngestionRepository") as repo_cls,
        patch("app.tasks._pipeline_reconciler.SessionLocal") as session_cls,
        patch("app.tasks._pipeline_reconciler.asyncio.sleep", side_effect=fake_sleep),
    ):
        repo_cls.return_value.reconcile_pipeline_statuses = AsyncMock(
            return_value={"checked": 3, "corrected": 1}
        )
        # Async context manager mock for ``async with SessionLocal() as session``.
        session_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(asyncio.CancelledError):
            await reconcile_pipeline_statuses_loop()

    assert sleep_called.is_set()
    repo_cls.return_value.reconcile_pipeline_statuses.assert_awaited_once()


@pytest.mark.asyncio
async def test_loop_survives_sweep_exception():
    """A raised exception from ``reconcile_pipeline_statuses`` does NOT
    kill the loop — the next iteration runs as usual."""
    from app.tasks._pipeline_reconciler import reconcile_pipeline_statuses_loop

    call_count = {"n": 0}

    async def boom_then_ok(*_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient DB error")
        return {"checked": 0, "corrected": 0}

    async def fake_sleep(*_a, **_kw):
        # Break out after the SECOND iteration so we prove the loop
        # survived the first iteration's exception.
        if call_count["n"] >= 2:
            raise asyncio.CancelledError()

    with (
        patch("app.tasks._pipeline_reconciler.DataIngestionRepository") as repo_cls,
        patch("app.tasks._pipeline_reconciler.SessionLocal") as session_cls,
        patch("app.tasks._pipeline_reconciler.asyncio.sleep", side_effect=fake_sleep),
    ):
        repo_cls.return_value.reconcile_pipeline_statuses = AsyncMock(
            side_effect=boom_then_ok
        )
        session_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(asyncio.CancelledError):
            await reconcile_pipeline_statuses_loop()

    assert call_count["n"] == 2, "loop must continue past the first exception"


@pytest.mark.asyncio
async def test_loop_skips_info_log_on_quiet_sweep(caplog):
    """corrected=0 → no INFO log (otherwise the cron would spam at 60s
    cadence in steady state)."""
    from app.tasks._pipeline_reconciler import reconcile_pipeline_statuses_loop

    async def fake_sleep(*_a, **_kw):
        raise asyncio.CancelledError()

    with (
        patch("app.tasks._pipeline_reconciler.DataIngestionRepository") as repo_cls,
        patch("app.tasks._pipeline_reconciler.SessionLocal") as session_cls,
        patch("app.tasks._pipeline_reconciler.asyncio.sleep", side_effect=fake_sleep),
    ):
        repo_cls.return_value.reconcile_pipeline_statuses = AsyncMock(
            return_value={"checked": 100, "corrected": 0}
        )
        session_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with caplog.at_level("INFO", logger="app.tasks._pipeline_reconciler"):
            with pytest.raises(asyncio.CancelledError):
                await reconcile_pipeline_statuses_loop()

    healed_logs = [r for r in caplog.records if "healed" in r.message]
    assert not healed_logs, "quiet sweeps must not log at INFO"
