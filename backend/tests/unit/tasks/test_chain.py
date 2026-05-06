"""Unit tests for ``app.tasks._chain.chain_job`` (Plan 310-C parent → child handoff).

Extracted from ``test_runner.py`` when ``chain_job`` moved out of
``runner`` to break the static import cycle CodeQL flagged on PR #1050
(alerts #644/#645/#646).  Coverage is unchanged: pipeline_id
inheritance, pipeline_id generation when parent has none, and explicit
keyword overrides winning over parent inheritance.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.tasks import _chain as chain_mod


def _make_parent(job_id: int = 100) -> MagicMock:
    """A parent DataIngestionJob shaped for chain_job."""
    job = MagicMock()
    job.id = job_id
    job.module_type_id = 11
    job.year = 2025
    job.pipeline_id = None
    return job


def _make_repo_for_chain(parent: MagicMock) -> MagicMock:
    """A DataIngestionRepository mock that records the created child."""
    repo = MagicMock()
    repo.get_job_by_id = AsyncMock(return_value=parent)
    repo.create_ingestion_job = AsyncMock(side_effect=lambda j: j)
    return repo


@pytest.mark.asyncio
async def test_chain_job_inherits_pipeline_id_and_fires_run_job():
    """Child created NOT_STARTED, inherits parent's pipeline_id,
    parent_job_id stamped in meta, run_job scheduled via
    fire_and_forget."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()

    repo = _make_repo_for_chain(parent)

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
        patch.object(chain_mod, "DataIngestionRepository", return_value=repo),
        patch.object(chain_mod, "fire_and_forget", side_effect=_fake_fire_and_forget),
    ):
        child_id = await chain_mod.chain_job(
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
    parent = _make_parent(job_id=100)
    parent.pipeline_id = None

    async def _create(child):
        child.id = 200
        return child

    repo = _make_repo_for_chain(parent)
    repo.create_ingestion_job = AsyncMock(side_effect=_create)

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with (
        patch.object(chain_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            chain_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await chain_mod.chain_job(parent, job_type="emission_recalc", session=session)

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
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()

    async def _create(child):
        child.id = 200
        return child

    repo = _make_repo_for_chain(parent)
    repo.create_ingestion_job = AsyncMock(side_effect=_create)

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with (
        patch.object(chain_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            chain_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        await chain_mod.chain_job(
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
    # Defaults still applied for kwargs we didn't override.
    assert created.entity_type == EntityType.MODULE_PER_YEAR
