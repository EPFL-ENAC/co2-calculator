"""Real-Postgres tests for Plan 310-C ``factor_ingest`` fan-out.

Plan 310-B's ``_enqueue_stale_recalculations`` was folded into the
``factor_ingest_handler``'s post-success block (Plan 310-C runner
cutover); the helper is now ``_chain_recalc_for_stale``, which calls
``_chain.chain_job`` once per stale ``(module, det)``.  These tests
exercise that helper directly against a real Postgres engine —
mirroring the original 310-B fan-out tests but against the new
shape.

Reproduces the production failure observed for equipments factor
uploads: the CSV covers all three data-entry types under the
equipment module (scientific, it, other), so the parent factor job
is created with ``data_entry_type_id = NULL``.  Without the
multi-type branch in the handler, the fan-out finds zero stale
combos because ``get_recalculation_status_by_year`` filters factor
jobs with ``data_entry_type_id IS NULL`` out of its result set.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
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
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.tasks.ingestion_tasks import _chain_recalc_for_stale

from .conftest import ensure_pipeline_for_job


def _multi_type_factor_job() -> DataIngestionJob:
    """Mirrors the production case: a finished, current FACTORS job for
    the equipments module with no specific data_entry_type set."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        data_entry_type_id=None,  # multi-type CSV — det resolved per row
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
        job_type="factor_ingest",
        pipeline_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_fanout_creates_one_child_per_det_for_multitype_parent(pg_dsn):
    """Multi-type factor upload (det=NULL on the parent) fans out one
    ``emission_recalc`` child per data_entry_type in the module.

    Patches ``runner.fire_and_forget`` to a no-op so the test only
    asserts on the rows ``chain_job`` persisted; the dispatch path is
    covered separately by the runner unit tests.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _multi_type_factor_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()

    # ``chain_job`` lives in ``app.tasks._chain`` (extracted from runner
    # to break the static import cycle CodeQL flagged on PR #1050).
    # Patch ``fire_and_forget`` there to suppress the post-create
    # ``run_job(child_id)`` dispatch — we only assert that the child
    # rows landed correctly.
    def _noop_fire(coro, *, name=None):
        coro.close()
        return AsyncMock()

    async with Sf() as session:
        # Re-fetch the parent on this session so chain_job's
        # ``session.add(parent)`` line (when it generates a fresh
        # pipeline_id) targets a row attached to the live session.
        from sqlmodel import col, select

        parent_row = (
            await session.execute(
                select(DataIngestionJob).where(
                    col(DataIngestionJob.module_type_id)
                    == ModuleTypeEnum.equipment_electric_consumption.value,
                    col(DataIngestionJob.target_type) == TargetType.FACTORS,
                )
            )
        ).scalar_one()

        with patch("app.tasks._chain.fire_and_forget", side_effect=_noop_fire):
            chained = await _chain_recalc_for_stale(parent_row, session)

    expected_dets = {
        DataEntryTypeEnum.scientific.value,
        DataEntryTypeEnum.it.value,
        DataEntryTypeEnum.other.value,
    }
    assert chained == len(expected_dets)

    async with Sf() as session:
        from sqlmodel import col, select

        rows = (
            (
                await session.execute(
                    select(DataIngestionJob).where(
                        col(DataIngestionJob.job_type) == "emission_recalc",
                        col(DataIngestionJob.year) == 2025,
                    )
                )
            )
            .scalars()
            .all()
        )
        landed_dets = {r.data_entry_type_id for r in rows}
        assert landed_dets == expected_dets, (
            f"Expected one recalc per det {expected_dets}, got {landed_dets}"
        )
        # Phase 5B (#1236) — ``meta.parent_job_id`` was retired in
        # favour of pipeline-scoped traversal (parent = lowest-id job
        # in the pipeline; see ``compute_pipeline_progress._find_root``).
        # Pin the new contract: every fan-out child inherits the
        # parent's pipeline_id.
        for r in rows:
            assert r.pipeline_id == parent.pipeline_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_fanout_creates_single_child_for_single_type_parent(pg_dsn):
    """Parent factor job with a specific (module, det) → exactly one
    recalc child for that pair.  Bypasses the recalc-status query
    entirely (parent is still the canonical source of truth here)."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _multi_type_factor_job()
        parent.data_entry_type_id = DataEntryTypeEnum.it.value
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()

    def _noop_fire(coro, *, name=None):
        coro.close()
        return AsyncMock()

    async with Sf() as session:
        from sqlmodel import col, select

        parent_row = (
            await session.execute(
                select(DataIngestionJob).where(
                    col(DataIngestionJob.data_entry_type_id)
                    == DataEntryTypeEnum.it.value,
                    col(DataIngestionJob.target_type) == TargetType.FACTORS,
                )
            )
        ).scalar_one()

        with patch("app.tasks._chain.fire_and_forget", side_effect=_noop_fire):
            chained = await _chain_recalc_for_stale(parent_row, session)

    assert chained == 1

    async with Sf() as session:
        from sqlmodel import col, select

        rows = (
            (
                await session.execute(
                    select(DataIngestionJob).where(
                        col(DataIngestionJob.job_type) == "emission_recalc",
                        col(DataIngestionJob.year) == 2025,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].data_entry_type_id == DataEntryTypeEnum.it.value
        assert rows[0].module_type_id == parent.module_type_id

    await engine.dispose()
