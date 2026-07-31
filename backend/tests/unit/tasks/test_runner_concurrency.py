"""Unit tests for the #1723 per-pod job-concurrency semaphore.

``app.tasks.runner.run_job`` acquires a process-wide
``asyncio.Semaphore(MAX_CONCURRENT_JOBS)`` BEFORE ``claim_job``. Two
properties matter, and both are exercised with real ``asyncio``
synchronization primitives (an ``asyncio.Event`` the fake handler
blocks on, plus a bounded spin-poll to drive the loop deterministically)
rather than fixed-duration sleeps:

1. No more than ``MAX_CONCURRENT_JOBS`` handlers run at once, even
   when more jobs are ready to dispatch.
2. A job blocked on the semaphore has NOT been claimed — it stays
   ``NOT_STARTED`` with no ``locked_by`` — so another pod's poller
   could pick it up instead of it queueing behind this pod's busy
   workers (the load-balancing property the acquire-before-claim
   ordering exists for).

A third test confirms the heartbeat task is unaffected by the
semaphore: it keeps beating for a claimed, running job even while
other jobs sit blocked waiting for a semaphore slot.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.data_ingestion import IngestionState
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


@pytest.fixture(autouse=True)
def _reset_job_semaphore():
    """The semaphore is a lazily-created module singleton that binds to
    the event loop it first acquires on. pytest-asyncio gives each test
    function its own loop, so a semaphore left over from a previous test
    would raise ``RuntimeError`` ("got Future ... attached to a different
    loop") the moment this test tries to acquire it. Reset before AND
    after so a failing test doesn't poison the next one either.
    """
    runner_mod._job_semaphore = None
    try:
        yield
    finally:
        runner_mod._job_semaphore = None


def _patch_settings(monkeypatch, **overrides) -> Settings:
    settings = Settings(**overrides)
    monkeypatch.setattr(runner_mod, "get_settings", lambda: settings)
    return settings


def _make_job(job_id: int, job_type: str) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.job_type = job_type
    job.module_type_id = 11
    job.data_entry_type_id = 22
    job.year = 2025
    job.pipeline_id = None
    job.locked_by = None
    job.state = IngestionState.NOT_STARTED
    return job


def _make_multi_job_repo(jobs: dict[int, MagicMock]) -> MagicMock:
    """A ``DataIngestionRepository`` stand-in keyed by job id, so several
    concurrently-running ``run_job(id)`` calls each see their own row.
    """
    repo = MagicMock()

    async def _get(job_id: int):
        return jobs.get(job_id)

    async def _claim(job_id: int, pod_id: str) -> bool:
        job = jobs[job_id]
        job.locked_by = pod_id
        job.state = IngestionState.RUNNING
        return True

    async def _finish(job_id: int, _pod_id: str, **_kwargs) -> bool:
        jobs[job_id].state = IngestionState.FINISHED
        return True

    repo.get_job_by_id = AsyncMock(side_effect=_get)
    repo.claim_job = AsyncMock(side_effect=_claim)
    repo.finish_job = AsyncMock(side_effect=_finish)
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


async def _noop_heartbeat(_job_id: int, _abort_event=None) -> None:
    return None


def _patch_heartbeat():
    return patch.object(runner_mod, "_heartbeat_loop", _noop_heartbeat)


async def _spin_until(predicate, *, timeout: float = 2.0) -> None:
    """Yield control to the event loop until ``predicate()`` is true.

    Not a fixed-duration sleep: this drives the loop with ``sleep(0)``
    (a pure yield-point, no timing assumption) so it resolves as soon as
    the awaited coroutines make progress. ``timeout`` is a deadlock
    guard, not a timing assertion — a correct implementation resolves
    in a handful of loop iterations.
    """

    async def _poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(_poll(), timeout=timeout)


# ---------------------------------------------------------------------------
# Concurrency bound + load-balancing (no claim while queued)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_bounds_concurrency_and_leaves_queued_jobs_unclaimed(
    monkeypatch,
):
    """5 blocking jobs, MAX_CONCURRENT_JOBS=2: at most 2 handlers run at
    once, and the other 3 jobs are never claimed (still NOT_STARTED,
    no locked_by) while they wait — proving the semaphore is acquired
    BEFORE claim_job, not after.
    """
    max_concurrent = 2
    n_jobs = 5
    _patch_settings(monkeypatch, MAX_CONCURRENT_JOBS=max_concurrent)

    release = asyncio.Event()
    running = 0
    peak = 0

    @register("concurrency_test")
    async def _handler(job, job_session, data_session) -> dict:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await release.wait()
        running -= 1
        return {"status_message": "ok"}

    jobs = {i: _make_job(i, "concurrency_test") for i in range(1, n_jobs + 1)}
    repo = _make_multi_job_repo(jobs)

    with (
        _patch_session_local(),
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        gathered = asyncio.gather(*(runner_mod.run_job(i) for i in jobs))

        # Drive the loop until exactly `max_concurrent` handlers have
        # started and are blocked on `release` — the semaphore is full.
        await _spin_until(lambda: running == max_concurrent)

        claimed = [j for j in jobs.values() if j.state == IngestionState.RUNNING]
        queued = [j for j in jobs.values() if j.state == IngestionState.NOT_STARTED]
        assert len(claimed) == max_concurrent
        assert len(queued) == n_jobs - max_concurrent
        for job in queued:
            assert job.locked_by is None, (
                "a job blocked on the semaphore must NOT hold a claim — "
                "another pod's poller should be able to pick it up"
            )

        release.set()
        await asyncio.wait_for(gathered, timeout=5.0)

    assert peak == max_concurrent, (
        f"handler concurrency peaked at {peak}, expected exactly "
        f"{max_concurrent} (never above the semaphore bound)"
    )
    assert all(j.state == IngestionState.FINISHED for j in jobs.values())


# ---------------------------------------------------------------------------
# Heartbeat is exempt from the semaphore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_keeps_beating_while_other_jobs_queue_on_semaphore(
    monkeypatch,
):
    """MAX_CONCURRENT_JOBS=1: job 1 holds the sole slot and runs the
    REAL ``_heartbeat_loop`` (not the no-op test double); job 2 is
    blocked on the semaphore the whole time. The heartbeat for job 1
    must still fire — it is a separate asyncio.Task that never touches
    the semaphore, so it is unaffected by job 2 queueing.
    """
    _patch_settings(monkeypatch, MAX_CONCURRENT_JOBS=1, STALE_JOB_TIMEOUT_MINUTES=1)

    # Same trick as test_runner_heartbeat_abort.py: patch asyncio.sleep
    # (as seen by the runner module) to a real-yield no-op so the
    # heartbeat loop's cadence doesn't cost real wall-clock time.
    real_sleep = asyncio.sleep

    async def _fast_sleep(_secs: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(runner_mod.asyncio, "sleep", _fast_sleep)

    release = asyncio.Event()

    @register("heartbeat_test")
    async def _handler(job, job_session, data_session) -> dict:
        await release.wait()
        return {"status_message": "ok"}

    jobs = {
        1: _make_job(1, "heartbeat_test"),
        2: _make_job(2, "heartbeat_test"),
    }
    repo = _make_multi_job_repo(jobs)

    with (
        _patch_session_local(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        gathered = asyncio.gather(*(runner_mod.run_job(i) for i in jobs))

        # Job 1 claims the sole slot and blocks in its handler; job 2
        # is blocked on the semaphore and never gets claimed.
        await _spin_until(lambda: jobs[1].state == IngestionState.RUNNING)
        assert jobs[2].state == IngestionState.NOT_STARTED

        # The heartbeat for job 1 must still fire despite job 2 queueing.
        await _spin_until(lambda: repo.heartbeat.await_count >= 1)

        assert jobs[2].state == IngestionState.NOT_STARTED, (
            "job 2 must still be unclaimed — the heartbeat firing must "
            "not have let it slip past the semaphore"
        )

        release.set()
        await asyncio.wait_for(gathered, timeout=5.0)

    assert repo.heartbeat.await_count >= 1
