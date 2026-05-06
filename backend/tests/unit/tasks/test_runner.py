"""Unit tests for ``app.tasks.runner`` (Plan 310-C unified dispatcher).

Covers the test matrix from
``docs/src/implementation-plans/310-c-dag-handler-registry.md`` lines
433-446: registry handling, claim/preemption semantics, success and
error paths, started_at / finished_at observability, chain_job
inheritance, and heartbeat behavior.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
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
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.run_job(1)

    repo.claim_job.assert_awaited_once()
    repo.update_ingestion_job.assert_awaited_once()
    args, kwargs = repo.update_ingestion_job.call_args
    assert kwargs["state"] == IngestionState.FINISHED
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
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.run_job(1)

    # Two sessions opened (job_session + data_session); the data_session
    # should have rolled back, the job_session should still commit
    # the FINISHED+ERROR row update.
    assert len(captured_sessions) == 2
    job_session, data_session = captured_sessions
    data_session.rollback.assert_awaited()

    repo.update_ingestion_job.assert_awaited_once()
    _, kwargs = repo.update_ingestion_job.call_args
    assert kwargs["state"] == IngestionState.FINISHED
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

    # On the second get_job_by_id call (the preemption check), return a
    # row owned by a different pod.
    preempted = _make_job()
    preempted.locked_by = "some-other-pod"
    repo = _make_repo_returning(job)
    repo.get_job_by_id = AsyncMock(side_effect=[job, preempted])

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
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.run_job(1)

    _, data_session = captured_sessions
    data_session.rollback.assert_awaited()
    repo.update_ingestion_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_preempted_to_deleted_rolls_back():
    """Preemption check sees job has vanished (recovered + recreated
    under a different id, or admin deleted) → same rollback path."""
    job = _make_job()
    job.locked_by = runner_mod.POD_ID
    repo = _make_repo_returning(job)
    repo.get_job_by_id = AsyncMock(side_effect=[job, None])

    @register("test_job")
    async def _handler(j, js, ds) -> dict:
        return {}

    with (
        _patch_session_local(),
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.run_job(1)

    repo.update_ingestion_job.assert_not_called()


# ---------------------------------------------------------------------------
# chain_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_job_inherits_pipeline_id_and_fires_run_job():
    """Child created NOT_STARTED, inherits parent's pipeline_id,
    parent_job_id stamped in meta, run_job scheduled via
    fire_and_forget."""
    parent = _make_job(job_id=100)
    parent.pipeline_id = uuid4()

    repo = _make_repo_returning(parent)
    captured_child = MagicMock()
    captured_child.id = 200

    async def _create(child):
        # Mirror what create_ingestion_job does: assign id post-flush.
        child.id = 200
        return child

    repo.create_ingestion_job = AsyncMock(side_effect=_create)

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    fired = []

    def _fake_fire_and_forget(coro, *, name=None):
        # Close the coroutine to avoid "coroutine was never awaited"
        # warnings; we only care that the dispatcher would have fired.
        coro.close()
        fired.append(name)
        return MagicMock()

    with (
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(runner_mod, "fire_and_forget", side_effect=_fake_fire_and_forget),
    ):
        child_id = await runner_mod.chain_job(
            parent,
            job_type="emission_recalc",
            session=session,
        )

    assert child_id == 200
    repo.create_ingestion_job.assert_awaited_once()
    created = repo.create_ingestion_job.await_args.args[0]
    assert created.pipeline_id == parent.pipeline_id
    assert created.state == IngestionState.NOT_STARTED
    assert created.meta["parent_job_id"] == 100
    assert created.module_type_id == parent.module_type_id  # inherited
    assert created.year == parent.year  # inherited

    # Default kw values applied.
    assert created.target_type == TargetType.DATA_ENTRIES
    assert created.ingestion_method == IngestionMethod.computed
    assert created.entity_type == EntityType.MODULE_PER_YEAR

    assert fired == [f"run_job-{child_id}"]


@pytest.mark.asyncio
async def test_chain_job_generates_pipeline_id_when_parent_has_none():
    """Parent without pipeline_id → chain_job generates a UUID and
    persists it on the parent BEFORE creating the child, so
    pod-crash-then-recovery of the parent doesn't generate a different
    pipeline_id and orphan the child."""
    parent = _make_job(job_id=100)
    parent.pipeline_id = None

    async def _create(child):
        child.id = 200
        return child

    repo = _make_repo_returning(parent)
    repo.create_ingestion_job = AsyncMock(side_effect=_create)

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with (
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.chain_job(parent, job_type="emission_recalc", session=session)

    # Parent's pipeline_id must now be set.
    assert isinstance(parent.pipeline_id, UUID)
    # And must equal the child's pipeline_id.
    created = repo.create_ingestion_job.await_args.args[0]
    assert created.pipeline_id == parent.pipeline_id
    # And the parent must have been re-added to the session before
    # commit (so the new pipeline_id actually persists).
    session.add.assert_any_call(parent)


@pytest.mark.asyncio
async def test_chain_job_overrides_apply():
    """Explicit kw args win over parent inheritance."""
    parent = _make_job(job_id=100)
    parent.pipeline_id = uuid4()

    async def _create(child):
        child.id = 200
        return child

    repo = _make_repo_returning(parent)
    repo.create_ingestion_job = AsyncMock(side_effect=_create)

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with (
        patch.object(runner_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            runner_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await runner_mod.chain_job(
            parent,
            job_type="aggregation",
            session=session,
            module_type_id=99,
            year=2030,
            target_type=TargetType.FACTORS,
            config={"foo": "bar"},
        )

    created = repo.create_ingestion_job.await_args.args[0]
    assert created.module_type_id == 99
    assert created.year == 2030
    assert created.target_type == TargetType.FACTORS
    assert created.meta["config"] == {"foo": "bar"}
