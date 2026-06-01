"""Real-Postgres test for the Plan 310-D full bulk pipeline DAG.

Pins the contract that ``csv_ingest`` chains to ``emission_recalc``
which chains to ``aggregation`` — the three-step DAG that owns
``data_entry_emissions`` and ``carbon_reports.stats`` writes for the
bulk path under ``BULK_PATH_PURE_ASYNC=True``.

Scope: this test exercises the **chain wiring** end-to-end (parent
→ child → grandchild rows persisted, scope inheritance, terminal
state on each step).  The handler bodies themselves are unit-tested
elsewhere; here we patch the heavy bits (provider class, workflow,
service) so the test runs in seconds rather than minutes.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider

from .conftest import ensure_pipeline_for_job


async def _install_dedup_index(engine) -> None:
    """Install ``uq_aggregation_active`` so the aggregation chain's
    dedup INSERT can pre-check + race-trip safely."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_active "
                "ON data_ingestion_jobs (module_type_id, year) "
                "WHERE job_type = 'aggregation' "
                "AND state IN ("
                "'NOT_STARTED'::ingestion_state_enum, "
                "'QUEUED'::ingestion_state_enum, "
                "'RUNNING'::ingestion_state_enum)"
            )
        )


def _csv_ingest_parent() -> DataIngestionJob:
    """Mirror the production case: a CSV ingest for one (module, det,
    year) combo.  ``state=RUNNING`` because the runner has already
    claimed it by the time the handler body runs."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=5,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        is_current=True,
        job_type="csv_ingest",
        pipeline_id=uuid4(),
        meta={"provider_name": "FakeCSV"},
    )


@pytest.mark.asyncio
async def test_full_dag_csv_ingest_chains_emission_recalc_chains_aggregation(pg_dsn):
    """csv_ingest → emission_recalc → aggregation: every link in the
    chain creates a child row with the parent's pipeline_id, the
    correct ``job_type``, and the inherited (module, det, year) scope.

    We dispatch ``run_job`` synchronously (instead of fire-and-forget)
    so the assertions can read the post-chain state in a deterministic
    order; the production flow is asynchronous but the rows it
    persists are the same.
    """
    from app.tasks import _chain as chain_mod
    from app.tasks import aggregation_tasks as aggregation_mod
    from app.tasks import emission_recalculation_tasks as recalc_mod
    from app.tasks import ingestion_tasks as ingest_mod

    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Persist the parent csv_ingest job.
    async with Sf() as session:
        parent = _csv_ingest_parent()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)
        parent_pipeline_id = parent.pipeline_id
        parent_id = parent.id

    # 2. Patch the heavy bits and the runner-dispatch so chain_job's
    #    fire_and_forget runs the child handler synchronously.

    # Provider stub (csv_ingest): returns SUCCESS so the fan-out fires.
    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS, "inserted": 3},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    # EmissionRecalculationWorkflow stub: SUCCESS, no entries (we
    # don't need to assert on data_entry_emissions in this test).
    workflow = MagicMock()
    workflow.recalculate_for_data_entry_type = AsyncMock(
        return_value={
            "recalculated": 0,
            "errors": 0,
            "modules_refreshed": 0,
            "affected_module_ids": [],
        }
    )

    # CarbonReportModuleService stub: returns no modules so the
    # aggregation handler's per-module loop is a no-op (the chain
    # wiring is what we're testing here, not the stats math).
    crm_svc = MagicMock()
    crm_svc.list_modules_for = AsyncMock(return_value=[])

    # The runner has its own session factory tied to the
    # production DB URL.  Replace ``fire_and_forget`` with a shim
    # that closes the (real) ``run_job`` coroutine — we don't want
    # it to actually execute against sqlite — and queues a
    # test-side stand-in that drives the next handler against the
    # PG session factory.
    pending: list = []

    def _sync_fire_and_forget(coro, *, name=None):
        # Close the original run_job coroutine so it doesn't run
        # against the real (sqlite) engine.  ``name`` carries
        # ``run_job-{child_id}`` — extract the child id and
        # dispatch via our PG-aware fake instead.
        coro.close()
        if name and name.startswith("run_job-"):
            child_id = int(name.split("-", 1)[1])
            pending.append(child_id)
        return MagicMock()

    async def _run_child(job_id: int) -> None:
        """Mirror run_job's claim → handler → FINISHED-state write
        but against the test's PG engine.  Heartbeat/preemption
        machinery is intentionally absent — the rows we assert on
        are the chain wiring, not the runner's locking shape."""
        from app.tasks.registry import get_handler

        async with Sf() as job_session:
            row = await job_session.get(DataIngestionJob, job_id)
            if row is None:
                return
            handler = get_handler(row.job_type)
            async with Sf() as data_session:
                meta = await handler(row, job_session, data_session)
            row.state = IngestionState.FINISHED
            row.result = meta.get("result", IngestionResult.SUCCESS)
            row.status_message = meta.get("status_message", "")
            existing_meta = dict(row.meta or {})
            existing_meta.update({k: v for k, v in meta.items() if k != "result"})
            row.meta = existing_meta
            job_session.add(row)
            await job_session.commit()

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
        patch.object(
            aggregation_mod, "CarbonReportModuleService", return_value=crm_svc
        ),
        patch.object(chain_mod, "fire_and_forget", side_effect=_sync_fire_and_forget),
        # emission_recalc opens its sibling-query + recalc_work_complete
        # stamp + aggregation-scope helpers via ``SessionLocal()``.  Point
        # them at the test PG so they don't crash on SQLite's missing
        # ``pipelines`` table.
        patch.object(recalc_mod, "SessionLocal", Sf),
    ):
        # 3. Run the parent handler.  It awaits chain_job, which our
        #    patched fire_and_forget queues; we then drain the queue
        #    so each child runs in turn.
        async with Sf() as session:
            row = await session.get(DataIngestionJob, parent_id)
            from app.tasks.registry import get_handler

            handler = get_handler("csv_ingest")
            async with Sf() as data_session:
                await handler(row, session, data_session)

        # Drain children breadth-first.  Each child handler may
        # enqueue its own child via the same ``_sync_fire_and_forget``;
        # the patches stay in scope while we drain.
        while pending:
            child_id = pending.pop(0)
            await _run_child(child_id)

    # 4. Inspect the persisted rows.
    async with Sf() as session:
        result = await session.execute(
            select(DataIngestionJob)
            .where(DataIngestionJob.pipeline_id == parent_pipeline_id)
            .order_by(DataIngestionJob.id.asc())
        )
        all_rows = list(result.scalars().all())

    # Three rows in the pipeline: parent + 1 emission_recalc + 1 aggregation.
    job_types = [r.job_type for r in all_rows]
    assert "csv_ingest" in job_types
    assert "emission_recalc" in job_types
    assert "aggregation" in job_types
    assert len(all_rows) == 3

    # Every row shares the parent's pipeline_id.
    assert all(r.pipeline_id == parent_pipeline_id for r in all_rows)

    # The emission_recalc child inherits scope from the parent.
    recalc = next(r for r in all_rows if r.job_type == "emission_recalc")
    assert recalc.module_type_id == 5
    assert recalc.data_entry_type_id == DataEntryTypeEnum.it.value
    assert recalc.year == 2025

    # The aggregation grandchild is module-scoped (no det, single per
    # (module, year)).
    aggregation = next(r for r in all_rows if r.job_type == "aggregation")
    assert aggregation.module_type_id == 5
    assert aggregation.data_entry_type_id is None
    assert aggregation.year == 2025

    await engine.dispose()


def _emission_recalc_parent() -> DataIngestionJob:
    """An ``emission_recalc`` parent already claimed by the runner —
    the handler body is what we drive directly in the WARNING test
    below.  Mirrors the rows endpoints+poller actually persist."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=5,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        is_current=True,
        job_type="emission_recalc",
        pipeline_id=uuid4(),
        meta={},
    )


@pytest.mark.asyncio
async def test_aggregation_chains_on_warning_with_partial_failure(pg_dsn):
    """Regression for B-C2: a per-entry failure during recalc must not
    skip the aggregation chain.

    Before the fix, ``emission_recalc`` only chained aggregation when
    ``result == SUCCESS``.  A 10k-row reupload that failed on a single
    entry flipped the result to WARNING, the chain was skipped, and
    ``carbon_reports.stats`` stayed stale forever even though 9999
    entries were correctly recomputed.

    This test stubs ``EmissionRecalculationWorkflow`` to surface a
    partial failure (``errors=1``) — equivalent to ``upsert_by_data_entry``
    raising once on a single row — and asserts the aggregation child
    is persisted with the parent's pipeline_id.
    """
    from app.tasks import _chain as chain_mod
    from app.tasks import emission_recalculation_tasks as recalc_mod

    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Persist the emission_recalc parent (state=RUNNING — the
    #    runner has claimed it and the handler body is what we run
    #    here).
    async with Sf() as session:
        parent = _emission_recalc_parent()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)
        parent_pipeline_id = parent.pipeline_id
        parent_id = parent.id

    # 2. Workflow stub: partial-failure shape — recalculated>0 with
    #    errors=1 makes the handler compute ``result=WARNING``, which
    #    is the exact branch the bug skipped.
    workflow = MagicMock()
    workflow.recalculate_for_data_entry_type = AsyncMock(
        return_value={
            "recalculated": 9999,
            "errors": 1,
            "modules_refreshed": 0,
            "affected_module_ids": [5],
            "error_details": [{"data_entry_id": 42, "error": "boom"}],
        }
    )

    # 3. ``fire_and_forget`` shim — we only care that the aggregation
    #    row was persisted by ``chain_job``; we don't need to drive
    #    the aggregation handler itself.  Closing the run_job coroutine
    #    keeps it from running against the runner's (sqlite) engine.
    def _drop_fire_and_forget(coro, *, name=None):
        coro.close()
        return MagicMock()

    with (
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
        patch.object(chain_mod, "fire_and_forget", side_effect=_drop_fire_and_forget),
        # emission_recalc helpers open ``SessionLocal()`` — point at PG.
        patch.object(recalc_mod, "SessionLocal", Sf),
    ):
        async with Sf() as session:
            row = await session.get(DataIngestionJob, parent_id)
            from app.tasks.registry import get_handler

            handler = get_handler("emission_recalc")
            async with Sf() as data_session:
                meta = await handler(row, session, data_session)

    # Sanity: the handler reported WARNING (the branch the bug skipped).
    assert meta["result"] == IngestionResult.WARNING
    # Phase 5B (#1236) — ``aggregation_job_id`` is no longer threaded
    # through meta; the aggregation row is the source of truth.  The
    # contract asserted here is "aggregation chained" — checked below
    # by the row count under the parent's pipeline_id.
    assert "aggregation_job_id" not in meta

    # The aggregation child exists in the DB, carries the parent's
    # pipeline_id, and is module-scoped to (module=5, year=2025).
    async with Sf() as session:
        result = await session.execute(
            select(DataIngestionJob)
            .where(DataIngestionJob.pipeline_id == parent_pipeline_id)
            .where(DataIngestionJob.job_type == "aggregation")
        )
        aggregation_rows = list(result.scalars().all())

    assert len(aggregation_rows) == 1
    aggregation = aggregation_rows[0]
    assert aggregation.module_type_id == 5
    assert aggregation.data_entry_type_id is None
    assert aggregation.year == 2025

    await engine.dispose()
