"""Unit tests for ``app.tasks._chain.chain_job`` (Plan 310-C parent → child handoff).

Extracted from ``test_runner.py`` when ``chain_job`` moved out of
``runner`` to break the static import cycle CodeQL flagged on PR #1050
(alerts #644/#645/#646).  Coverage is unchanged: pipeline_id
inheritance, pipeline_id generation when parent has none, and explicit
keyword overrides winning over parent inheritance.

Plan 310-D extends ``chain_job`` with ``dedup_active=True``: the
helper pre-checks for an active aggregation row in the
``(module_type_id, year)`` scope and INSERTs only when none exists,
falling back to catching ``IntegrityError`` from the partial unique
index ``uq_aggregation_active`` if a concurrent writer wins the race.
Returns ``None`` on dedup so the caller skips its own follow-up
fan-out.  Tests in the ``dedup_active`` section pin: (1) the success
path returns the new id, (2) the pre-check dedup path returns None
without firing run_job, (3) NULL scope keys raise ``ValueError``
(silent-bypass guard), and (4) the legacy non-dedup path still
tolerates NULL keys.
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
    # #1236 — chain_job's lazy-mint path now creates the pipeline
    # aggregate row via this idempotent helper; stub it on the mock.
    repo.ensure_pipeline_exists = AsyncMock()
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


# ---------------------------------------------------------------------------
# Plan 310-D — dedup_active=True path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_job_dedup_active_returns_new_id_on_success():
    """``dedup_active=True`` and the partial unique index does not
    block: ``_insert_child_with_dedup`` returns the new id, chain_job
    fires run_job, and the function returns the same id."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    fired = []

    def _fake_fire_and_forget(coro, *, name=None):
        coro.close()
        fired.append(name)
        return MagicMock()

    with (
        patch.object(
            chain_mod,
            "_insert_child_with_dedup",
            new_callable=AsyncMock,
            return_value=777,
        ) as mock_insert,
        patch.object(chain_mod, "fire_and_forget", side_effect=_fake_fire_and_forget),
    ):
        child_id = await chain_mod.chain_job(
            parent,
            job_type="aggregation",
            session=session,
            module_type_id=11,
            year=2025,
            dedup_active=True,
        )

    assert child_id == 777
    mock_insert.assert_awaited_once()
    assert fired == ["run_job-777"]


@pytest.mark.asyncio
async def test_chain_job_dedup_active_returns_none_on_collision():
    """``dedup_active=True`` and the index already covers an active
    row: ``_insert_child_with_dedup`` returns None.  chain_job must
    return None too AND must NOT fire run_job (no new work to dispatch)."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    fired = []

    def _fake_fire_and_forget(coro, *, name=None):
        coro.close()
        fired.append(name)
        return MagicMock()

    with (
        patch.object(
            chain_mod,
            "_insert_child_with_dedup",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_insert,
        patch.object(chain_mod, "fire_and_forget", side_effect=_fake_fire_and_forget),
    ):
        child_id = await chain_mod.chain_job(
            parent,
            job_type="aggregation",
            session=session,
            module_type_id=11,
            year=2025,
            dedup_active=True,
        )

    assert child_id is None
    mock_insert.assert_awaited_once()
    # No run_job dispatched — the existing pending row will run.
    assert fired == []


@pytest.mark.asyncio
async def test_chain_job_dedup_active_false_uses_orm_path():
    """The default ``dedup_active=False`` path is unchanged: it goes
    through ``DataIngestionRepository.create_ingestion_job``, not the
    raw INSERT helper.  Pinned so a future refactor of the dedup path
    can't silently swap the legacy callers onto it."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()

    repo = _make_repo_for_chain(parent)

    async def _create(child):
        child.id = 200
        return child

    repo.create_ingestion_job = AsyncMock(side_effect=_create)
    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with (
        patch.object(chain_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            chain_mod,
            "_insert_child_with_dedup",
            new_callable=AsyncMock,
        ) as mock_insert,
        patch.object(
            chain_mod,
            "fire_and_forget",
            side_effect=lambda coro, *, name=None: (coro.close(), MagicMock())[1],
        ),
    ):
        child_id = await chain_mod.chain_job(
            parent, job_type="emission_recalc", session=session
        )

    assert child_id == 200
    mock_insert.assert_not_awaited()
    repo.create_ingestion_job.assert_awaited_once()


@pytest.mark.asyncio
async def test_chain_job_dedup_active_raises_when_module_type_id_none():
    """Plan 310-D — ``dedup_active=True`` with no resolvable
    ``module_type_id`` (parent has None and caller doesn't pass one)
    must raise instead of creating a duplicate dedup-bypass row.

    The pre-check SQL handles ``year IS NULL`` explicitly but
    ``module_type_id`` uses straight equality, so a NULL there
    silently bypasses dedup; the partial unique index can't catch
    the duplicate either (PG treats NULLs as distinct).  Fail fast
    instead of letting bad rows accumulate until the aggregation
    handler raises at execution time.
    """
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()
    parent.module_type_id = None  # the silent-bypass setup
    parent.year = 2025

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with pytest.raises(ValueError, match="scope keys must be set"):
        await chain_mod.chain_job(
            parent,
            job_type="aggregation",
            session=session,
            dedup_active=True,
        )


@pytest.mark.asyncio
async def test_chain_job_dedup_active_raises_when_year_none():
    """Same contract as the module_type_id case but the NULL is on
    ``year`` — the explicit ``IS NULL`` pre-check handling covers the
    SQL side, but the partial unique index won't catch the duplicate
    either.  Refuse at chain_job entry."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()
    parent.module_type_id = 11
    parent.year = None  # the silent-bypass setup

    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with pytest.raises(ValueError, match="scope keys must be set"):
        await chain_mod.chain_job(
            parent,
            job_type="aggregation",
            session=session,
            dedup_active=True,
        )


@pytest.mark.asyncio
async def test_chain_job_no_dedup_does_not_require_scope_keys():
    """The scope-keys guard only fires when ``dedup_active=True`` —
    the legacy non-dedup path has always tolerated NULL keys (single-
    step jobs, manual recalcs).  Pin that contract so the new guard
    doesn't accidentally tighten the legacy API."""
    parent = _make_parent(job_id=100)
    parent.pipeline_id = uuid4()
    parent.module_type_id = None
    parent.year = None

    repo = _make_repo_for_chain(parent)

    async def _create(child):
        child.id = 200
        return child

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
        child_id = await chain_mod.chain_job(
            parent,
            job_type="emission_recalc",
            session=session,
            # dedup_active defaults to False — no guard fires
        )

    assert child_id == 200
