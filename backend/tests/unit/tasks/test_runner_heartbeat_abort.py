"""Unit tests for the B-H3 heartbeat-failure-abort path.

Plan 310 post-merge fix B-H3: when a heartbeat fails consecutively
for long enough that the auto-recovery sweep on another pod has
almost certainly preempted the row, ``_heartbeat_loop`` sets the
shared ``abort_event`` and the runner cancels the handler instead
of running it to completion against a row it no longer owns.

These tests:

1. Drive ``_heartbeat_loop`` directly with ``repo.heartbeat`` raising
   on every call, and assert the abort event is set after exactly
   ``failure_threshold`` failures.

2. Drive ``run_job`` with a handler that awaits an
   ``asyncio.Event()`` that never fires, alongside a heartbeat that
   trips the abort path almost immediately, and assert:

     - the handler task is cancelled within a bounded wall-clock window,
     - ``update_ingestion_job`` is NOT called (the new owner closes the row),
     - ``data_session.rollback`` IS called.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import runner as runner_mod
from app.tasks.registry import _REGISTRY, register


@pytest.fixture(autouse=True)
def _clean_registry():
    snapshot = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        yield
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(snapshot)


def _make_job(job_id: int = 1, job_type: str = "test_job") -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.job_type = job_type
    job.module_type_id = 11
    job.data_entry_type_id = 22
    job.year = 2025
    job.pipeline_id = None
    job.locked_by = runner_mod.POD_ID
    return job


def _make_repo_returning(job: MagicMock | None) -> MagicMock:
    repo = MagicMock()
    repo.get_job_by_id = AsyncMock(return_value=job)
    repo.claim_job = AsyncMock(return_value=True)
    repo.update_ingestion_job = AsyncMock(return_value=job)
    repo.heartbeat = AsyncMock(return_value=1)
    return repo


@asynccontextmanager
async def _mock_session_ctx():
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    yield session


def _patch_session_local():
    return patch.object(runner_mod, "SessionLocal", _mock_session_ctx)


# ---------------------------------------------------------------------------
# _heartbeat_loop — abort threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_loop_sets_abort_event_after_threshold_failures(
    monkeypatch,
):
    """Repeated heartbeat exceptions accumulate; on the threshold-th
    consecutive failure, ``abort_event`` is set and the loop returns.

    Use a short stale timeout (1 minute) so ``interval_seconds = 15``
    and ``failure_threshold = 4``.  Patch ``asyncio.sleep`` (on the
    real ``asyncio`` module the runner imported ``asyncio`` from) with
    a no-op coroutine so the test runs in real-time milliseconds.
    Capture the original ``asyncio.sleep`` first so the patched
    function can yield control without recursing into itself.
    """
    settings_mock = MagicMock()
    settings_mock.STALE_JOB_TIMEOUT_MINUTES = 1
    monkeypatch.setattr(runner_mod, "get_settings", lambda: settings_mock)

    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def _fast_sleep(secs: float) -> None:
        sleeps.append(secs)
        # Yield control via the *real* asyncio.sleep so the abort_event
        # waiter can wake — without recursing into the patched version.
        await real_sleep(0)

    monkeypatch.setattr(runner_mod.asyncio, "sleep", _fast_sleep)

    failing_repo = MagicMock()
    failing_repo.heartbeat = AsyncMock(side_effect=RuntimeError("db down"))
    monkeypatch.setattr(
        runner_mod, "DataIngestionRepository", lambda _s: failing_repo
    )
    monkeypatch.setattr(runner_mod, "SessionLocal", _mock_session_ctx)

    abort_event = asyncio.Event()

    # Loop should return on its own once threshold is hit; bound the
    # wait so a regression doesn't hang the suite forever.
    await asyncio.wait_for(
        runner_mod._heartbeat_loop(job_id=42, abort_event=abort_event),
        timeout=5.0,
    )

    assert abort_event.is_set(), "abort_event must be set after threshold failures"
    # 1-minute timeout / 15s interval = 4 attempts before abort.
    assert failing_repo.heartbeat.await_count == 4
    # And we slept four times, once per attempt.
    assert len(sleeps) == 4


@pytest.mark.asyncio
async def test_heartbeat_loop_resets_counter_on_success(monkeypatch):
    """A successful heartbeat between failures resets the counter,
    so the loop tolerates intermittent DB blips below the threshold."""
    settings_mock = MagicMock()
    settings_mock.STALE_JOB_TIMEOUT_MINUTES = 1  # 4 attempts to abort
    monkeypatch.setattr(runner_mod, "get_settings", lambda: settings_mock)

    real_sleep = asyncio.sleep

    async def _fast_sleep(_secs: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(runner_mod.asyncio, "sleep", _fast_sleep)

    # Pattern: fail, fail, fail, OK (resets to 0), fail, fail, fail (now
    # at 3 — still under threshold), then preempt-style 0-update which
    # short-circuits the loop.  Total: 7 calls; abort_event NEVER set.
    side_effects: list = [
        RuntimeError("blip 1"),
        RuntimeError("blip 2"),
        RuntimeError("blip 3"),
        1,  # success — resets counter
        RuntimeError("blip 4"),
        RuntimeError("blip 5"),
        0,  # preemption (updated == 0) — clean exit, NOT abort
    ]
    repo_mock = MagicMock()
    repo_mock.heartbeat = AsyncMock(side_effect=side_effects)
    monkeypatch.setattr(
        runner_mod, "DataIngestionRepository", lambda _s: repo_mock
    )
    monkeypatch.setattr(runner_mod, "SessionLocal", _mock_session_ctx)

    abort_event = asyncio.Event()
    await asyncio.wait_for(
        runner_mod._heartbeat_loop(job_id=7, abort_event=abort_event),
        timeout=5.0,
    )

    # The counter reset means we never reach the threshold even though
    # there were five failure exceptions in total.
    assert not abort_event.is_set()
    assert repo_mock.heartbeat.await_count == 7


# ---------------------------------------------------------------------------
# run_job — abort cancels the handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_aborts_handler_when_heartbeat_signals(monkeypatch):
    """Production scenario: the handler is stuck (``await never_done``)
    and the heartbeat trips the abort event.  Runner must:

      - cancel the handler task,
      - skip the FINISHED state write (the new owner does that),
      - roll back the data_session.
    """
    job = _make_job()
    repo = _make_repo_returning(job)

    # The handler awaits an event that is never set, so it would
    # otherwise hang forever.
    never_done = asyncio.Event()
    handler_was_cancelled = asyncio.Event()

    @register("test_job")
    async def _stuck_handler(j, js, ds) -> dict:
        try:
            await never_done.wait()
            return {}
        except asyncio.CancelledError:
            handler_was_cancelled.set()
            raise

    # Replace ``_heartbeat_loop`` with a fast version that sets the
    # abort event after a single tick — no need to drive the real
    # threshold logic again here (the dedicated tests above already
    # cover that); this test exercises the runner-side wait/cancel.
    async def _fast_aborting_heartbeat(
        _job_id: int, abort_event: asyncio.Event
    ) -> None:
        # Yield once so the handler actually gets to ``await never_done``
        # before we trip the abort event — exercises the FIRST_COMPLETED
        # race path rather than a synchronous shortcut.
        await asyncio.sleep(0)
        abort_event.set()

    captured_sessions = []

    @asynccontextmanager
    async def _capture_session():
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        captured_sessions.append(session)
        yield session

    with (
        patch.object(runner_mod, "SessionLocal", _capture_session),
        patch.object(runner_mod, "_heartbeat_loop", _fast_aborting_heartbeat),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        # Bound the test so a regression that loses the cancel doesn't
        # hang the suite forever.
        await asyncio.wait_for(runner_mod.run_job(1), timeout=5.0)

    assert handler_was_cancelled.is_set(), (
        "handler must observe a CancelledError after the heartbeat aborts"
    )
    # The new owner closes the row out — we MUST NOT race a FINISHED write.
    repo.update_ingestion_job.assert_not_called()

    # Two sessions opened (job_session + data_session); the data_session
    # MUST have rolled back.
    assert len(captured_sessions) == 2
    _job_session, data_session = captured_sessions
    data_session.rollback.assert_awaited()
