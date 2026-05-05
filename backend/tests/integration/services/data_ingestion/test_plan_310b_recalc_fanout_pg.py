"""Real-Postgres tests for Plan 310B Part 4 — recalc fan-out after a
multi-type factor ingest.

Reproduces the production failure observed for equipments factor uploads:
the CSV covers all three data-entry types under the equipment module
(scientific, it, other), so the parent factor job is created with
``data_entry_type_id = NULL``.  Without the multi-type branch in
``_enqueue_stale_recalculations``, the fan-out finds zero stale combos
because ``get_recalculation_status_by_year`` filters factor jobs with
``data_entry_type_id IS NULL`` out of its result set.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
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
from app.tasks.ingestion_tasks import _enqueue_stale_recalculations


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
    )


@pytest.mark.asyncio
async def test_enqueue_recalc_fans_out_when_factor_job_has_null_det(pg_dsn):
    """Multi-type factor upload (det=NULL on the parent) must fan out one
    recalc job per data_entry_type in the module.

    Failing today: ``get_recalculation_status_by_year`` filters factor jobs
    with ``data_entry_type_id IS NULL``, so the helper sees zero targets and
    silently returns without creating any recalc jobs — leaving emissions
    stale.  The expected behaviour is one ``emission_recalc`` job per det
    in ``MODULE_TYPE_TO_DATA_ENTRY_TYPES[equipment_electric_consumption]``.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _multi_type_factor_job()
        session.add(parent)
        await session.commit()
        assert parent.id is not None
        parent_id: int = parent.id
        module_type_id: int = parent.module_type_id  # type: ignore[assignment]

    # Run the helper against a real PG session.
    async with Sf() as session:
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=parent_id,
            module_type_id=module_type_id,
            data_entry_type_id=None,  # parent had no specific det
            year=2025,
            pipeline_id=uuid4(),
        )

    # Verify: one recalc job per det in the equipments module.
    expected_dets = {
        DataEntryTypeEnum.scientific.value,
        DataEntryTypeEnum.it.value,
        DataEntryTypeEnum.other.value,
    }
    async with Sf() as session:
        rows = (
            (
                await session.execute(
                    select(DataIngestionJob).where(
                        col(DataIngestionJob.target_type) == TargetType.DATA_ENTRIES,
                        col(DataIngestionJob.ingestion_method)
                        == IngestionMethod.computed,
                        col(DataIngestionJob.module_type_id) == module_type_id,
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
        # Each child references the parent in its meta config.
        for r in rows:
            assert r.job_type == "emission_recalc"
            assert r.meta is not None
            assert r.meta["config"]["parent_job_id"] == parent_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_enqueue_recalc_specific_det_unchanged(pg_dsn):
    """Parent factor job with a specific det still goes through the existing
    ``get_recalculation_status_by_year`` path and creates exactly one recalc
    job for that det."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _multi_type_factor_job()
        parent.data_entry_type_id = DataEntryTypeEnum.it.value
        session.add(parent)
        await session.commit()
        assert parent.id is not None
        parent_id: int = parent.id
        module_type_id: int = parent.module_type_id  # type: ignore[assignment]

    async with Sf() as session:
        await _enqueue_stale_recalculations(
            session,
            parent_job_id=parent_id,
            module_type_id=module_type_id,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            year=2025,
            pipeline_id=uuid4(),
        )

    async with Sf() as session:
        rows = (
            (
                await session.execute(
                    select(DataIngestionJob).where(
                        col(DataIngestionJob.target_type) == TargetType.DATA_ENTRIES,
                        col(DataIngestionJob.ingestion_method)
                        == IngestionMethod.computed,
                        col(DataIngestionJob.module_type_id) == module_type_id,
                        col(DataIngestionJob.year) == 2025,
                    )
                )
            )
            .scalars()
            .all()
        )
        # Exactly one recalc job for det=it (Strategy A path through
        # get_recalculation_status_by_year, which sees the parent job
        # because it has a specific data_entry_type_id).
        assert len(rows) == 1
        assert rows[0].data_entry_type_id == DataEntryTypeEnum.it.value
        assert rows[0].job_type == "emission_recalc"

    await engine.dispose()


# Silence the import-not-accessed warning for ``text`` (kept around in case
# fixture extensions need raw DDL).
_ = text
