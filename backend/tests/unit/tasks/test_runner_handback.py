"""#2696 -- a cancelled ``run_job`` hands its row back.

On SIGTERM the lifespan cancels every in-flight job task. Before this the
CancelledError just unwound through ``run_job``: sessions closed, semaphore
released, and the row left RUNNING under a pod that no longer existed until
``sweep_stuck_running_jobs`` recovered it STALE_JOB_TIMEOUT_MINUTES later.
Now the runner stops the handler, drops its writes, and releases the row
so the next poller tick can re-dispatch it.
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


def _make_job(job_id: int = 1) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.job_type = "test_job"
    job.pipeline_id = None
    job.locked_by = runner_mod.POD_ID
    return job


@pytest.mark.asyncio
async def test_cancelled_run_job_releases_the_row_and_drops_its_writes(monkeypatch):
    job = _make_job()
    repo = MagicMock()
    repo.get_job_by_id = AsyncMock(return_value=job)
    repo.claim_job = AsyncMock(return_value=True)
    repo.heartbeat = AsyncMock(return_value=1)
    repo.release_job = AsyncMock(return_value=True)
    repo.finish_job = AsyncMock(return_value=True)
    sessions = []

    @asynccontextmanager
    async def _session():
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        sessions.append(session)
        yield session

    handler_started = asyncio.Event()
    handler_cancelled = asyncio.Event()

    @register("test_job")
    async def _handler(_job, _job_session, _data_session):
        handler_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            handler_cancelled.set()
            raise
        return {}

    with (
        patch.object(runner_mod, "SessionLocal", _session),
        patch.object(runner_mod, "DataIngestionRepository", lambda _s: repo),
    ):
        task = asyncio.create_task(runner_mod.run_job(1))
        await asyncio.wait_for(handler_started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)

    assert handler_cancelled.is_set()
    repo.release_job.assert_awaited_once_with(1, runner_mod.POD_ID)
    repo.finish_job.assert_not_awaited()
    job_session, data_session = sessions[0], sessions[1]
    data_session.rollback.assert_awaited()
    job_session.rollback.assert_awaited()
