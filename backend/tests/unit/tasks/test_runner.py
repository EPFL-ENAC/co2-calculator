"""Unit tests for ``app.tasks.runner`` (Plan 310-C unified dispatcher).

Covers the test matrix from
``docs/src/implementation-plans/310-c-dag-handler-registry.md`` lines
433-446: registry handling, claim/preemption semantics, success and
error paths, started_at / finished_at observability, and heartbeat
behavior.

``chain_job`` tests live in ``test_chain.py`` since chain_job moved
to ``app.tasks._chain`` to break the static import cycle CodeQL flagged
on PR #1050 (alerts #644/#645/#646).
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import (
    IngestionResult,
)
from app.tasks import runner as runner_mod
from app.tasks.registry import _REGISTRY, register


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot+restore the global registry between tests (matches the
    pattern in test_registry.py so this file stays order-independent
    once Tier 2 wires real handlers via import-time decorators)."""
    snapshot = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        yield
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(snapshot)


def _make_job(job_id: int = 1, job_type: str = "test_job") -> MagicMock:
    """A DataIngestionJob shaped for the runner."""
    job = MagicMock()
    job.id = job_id
    job.job_type = job_type
    job.module_type_id = 11
    job.data_entry_type_id = 22
    job.year = 2025
    job.pipeline_id = None
    job.locked_by = None
    return job


def _make_repo_returning(job: MagicMock | None) -> MagicMock:
    """Mock of ``DataIngestionRepository`` whose ``get_job_by_id``
    returns the given job (or None for the not-found case)."""
    repo = MagicMock()
    repo.get_job_by_id = AsyncMock(return_value=job)
    repo.claim_job = AsyncMock(return_value=True)
    repo.update_ingestion_job = AsyncMock(return_value=job)
    # B-C1: terminal write goes through ``finish_job`` (CAS on locked_by +
    # state=RUNNING).  Returns True on rowcount==1, False if the row was
    # preempted between the runner's pre-write check and the UPDATE.
    repo.finish_job = AsyncMock(return_value=True)
    repo.create_ingestion_job = AsyncMock(side_effect=lambda j: j)
    repo.heartbeat = AsyncMock(return_value=1)
    return repo


@asynccontextmanager
async def _mock_session_ctx():
    """An async context manager wrapping a MagicMock session.

    ``SessionLocal()`` is an async context manager in production; the
    runner uses ``async with SessionLocal() as session_a, SessionLocal()
    as session_b``.  This mock yields a fresh MagicMock per ``with``,
    matching that shape."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    yield session


def _patch_session_local():
    """Patch ``runner.SessionLocal`` to yield mock sessions."""
    return patch.object(runner_mod, "SessionLocal", _mock_session_ctx)


async def _noop_heartbeat(_job_id: int) -> None:
    """Drop-in for ``_heartbeat_loop`` that returns immediately so
    tests don't await real sleeps.  ``asyncio.create_task(noop())``
    produces a task that completes; the runner's cancel + await in
    ``finally`` is then a no-op."""
    return None


def _patch_heartbeat():
    """Patch ``_heartbeat_loop`` to a no-op so the runner's heartbeat
    spawn doesn't sleep through STALE_JOB_TIMEOUT_MINUTES/4 minutes."""
    return patch.object(runner_mod, "_heartbeat_loop", _noop_heartbeat)


# ---------------------------------------------------------------------------
# run_job — guard rails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_unknown_job_id_logs_and_returns():
    """Job not found → log error, no claim, no state change."""
    repo = _make_repo_returning(None)
    with (
        _patch_session_local(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(999)

    repo.claim_job.assert_not_called()
    repo.update_ingestion_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_null_job_type_refuses_to_dispatch():
    """``job_type IS NULL`` (legacy in-flight rows) → no dispatch."""
    job = _make_job()
    job.job_type = None
    repo = _make_repo_returning(job)
    with (
        _patch_session_local(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    repo.claim_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_claim_fails_returns_silently():
    """``claim_job`` returns False (already claimed / out of retries)
    → run_job exits without calling the handler or updating state."""
    job = _make_job()
    repo = _make_repo_returning(job)
    repo.claim_job = AsyncMock(return_value=False)

    handler = AsyncMock()

    @register("test_job")
    async def _handler(j, js, ds):
        return await handler(j, js, ds)

    with (
        _patch_session_local(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    handler.assert_not_called()
    repo.finish_job.assert_not_called()
    repo.update_ingestion_job.assert_not_called()


# ---------------------------------------------------------------------------
# run_job — success / error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_success_commits_and_marks_finished_success():
    """Happy path: handler returns a meta dict, data committed,
    state→FINISHED, result→SUCCESS, status_message from meta."""
    job = _make_job()
    job.locked_by = runner_mod.POD_ID
    repo = _make_repo_returning(job)

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        return {"status_message": "all good", "rows": 42}

    with (
        _patch_session_local(),
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    repo.claim_job.assert_awaited_once()
    repo.finish_job.assert_awaited_once()
    args, kwargs = repo.finish_job.call_args
    # finish_job(job_id, pod_id, result=..., status_message=..., metadata=...)
    assert args[0] == 1  # job_id
    assert args[1] == runner_mod.POD_ID
    assert kwargs["result"] == IngestionResult.SUCCESS
    assert kwargs["status_message"] == "all good"


@pytest.mark.asyncio
async def test_run_job_handler_raises_marks_finished_error_and_rolls_back():
    """Handler exception → data_session rolled back, state→FINISHED,
    result→ERROR, status_message captures the exception."""
    job = _make_job()
    job.locked_by = runner_mod.POD_ID
    repo = _make_repo_returning(job)

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        raise RuntimeError("boom")

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
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    # Two sessions opened (job_session + data_session); the data_session
    # should have rolled back, the job_session should still commit
    # the FINISHED+ERROR row update.
    assert len(captured_sessions) == 2
    job_session, data_session = captured_sessions
    data_session.rollback.assert_awaited()

    repo.finish_job.assert_awaited_once()
    args, kwargs = repo.finish_job.call_args
    assert args[1] == runner_mod.POD_ID
    assert kwargs["result"] == IngestionResult.ERROR
    assert "boom" in kwargs["status_message"]


# ---------------------------------------------------------------------------
# run_job — preemption check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_preempted_rolls_back_and_skips_state_update():
    """The pre-commit re-read sees a different ``locked_by`` (a stale-
    sweep recovered the row mid-handler) → roll back data_session,
    skip the state update so the new owner can finish without a
    racing FINISHED write."""
    job = _make_job()
    job.locked_by = runner_mod.POD_ID

    # ``get_job_by_id`` is called THREE times now: initial fetch (pre-
    # claim), post-claim re-fetch (so the handler sees the authoritative
    # post-claim row), and the preemption check (post-handler).  Only
    # the third call returns the preempted row.
    preempted = _make_job()
    preempted.locked_by = "some-other-pod"
    repo = _make_repo_returning(job)
    repo.get_job_by_id = AsyncMock(side_effect=[job, job, preempted])

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        return {}

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
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    _, data_session = captured_sessions
    data_session.rollback.assert_awaited()
    repo.update_ingestion_job.assert_not_called()
    repo.finish_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_preempted_to_deleted_rolls_back():
    """Preemption check sees job has vanished (recovered + recreated
    under a different id, or admin deleted) → same rollback path."""
    job = _make_job()
    job.locked_by = runner_mod.POD_ID
    repo = _make_repo_returning(job)
    # initial fetch, post-claim refetch, then preempt-check sees None.
    repo.get_job_by_id = AsyncMock(side_effect=[job, job, None])

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        return {}

    with (
        _patch_session_local(),
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    repo.update_ingestion_job.assert_not_called()
    repo.finish_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_handler_raise_with_preemption_skips_state_update():
    """Plan 310-C runner contract: the preemption check guards BOTH
    the success and the error paths.

    If the handler raises AND the row was preempted mid-handler, the
    runner must NOT write FINISHED+ERROR — that would race with the
    new owner's own FINISHED write.  Instead: roll back data_session
    and exit; the new owner closes out the job.
    """
    job = _make_job()
    job.locked_by = runner_mod.POD_ID

    preempted = _make_job()
    preempted.locked_by = "another-pod"
    repo = _make_repo_returning(job)
    # Same shape as the success-path preemption test: initial fetch,
    # post-claim refetch, then the preempt-check (after the handler
    # raised) returns the preempted row.
    repo.get_job_by_id = AsyncMock(side_effect=[job, job, preempted])

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        raise RuntimeError("handler exploded mid-preempt")

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
        _patch_heartbeat(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
    ):
        await runner_mod.run_job(1)

    _, data_session = captured_sessions
    data_session.rollback.assert_awaited()
    # Critical: the FINISHED+ERROR write must NOT fire when we no
    # longer own the row, even though the handler raised.
    repo.update_ingestion_job.assert_not_called()
    repo.finish_job.assert_not_called()


# chain_job tests live in ``test_chain.py``.
