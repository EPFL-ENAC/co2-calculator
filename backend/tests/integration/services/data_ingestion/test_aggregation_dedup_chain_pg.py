"""Real-Postgres tests for the Plan 310-D ``chain_job(dedup_active=True)`` path.

Pins the contract that N concurrent chain_job calls for the same
``(module_type_id, year, job_type='aggregation')`` scope collapse to
a single pending row via the ``uq_aggregation_active`` partial unique
index.  SQLite can't represent partial indexes the same way Postgres
does and the ``IngestionState`` enum types differ, so this is a
real-PG-only test.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.tasks._chain import chain_job

from .conftest import ensure_pipeline_for_job


async def _install_dedup_index(engine) -> None:
    """Create the ``uq_aggregation_active`` partial unique index that
    Plan 310-D's Alembic migration adds.

    ``pg_dsn`` builds the schema via ``SQLModel.metadata.create_all``,
    which doesn't run Alembic, so the partial index is missing.  Re-add
    it here so the dedup INSERT can bind via ``ON CONFLICT ON CONSTRAINT``.
    Mirrors the pattern used by ``pg_dsn_with_310b`` in conftest.py for
    the factor identity indexes.
    """
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


def _parent_job(module_type_id: int = 5, year: int = 2025) -> DataIngestionJob:
    """A minimal parent that ``chain_job`` will inherit from."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=11,
        year=year,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        is_current=True,
        job_type="emission_recalc",
        pipeline_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_dedup_active_creates_single_row_for_concurrent_chains(pg_dsn):
    """Two sequential ``chain_job(aggregation, dedup_active=True)``
    calls for the same (module, year) → only the first creates a row;
    the second sees the existing pending row and returns ``None``."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

    with patch(
        "app.tasks._chain.fire_and_forget",
        side_effect=lambda coro, *, name=None: (coro.close(), None)[1],
    ):
        async with Sf() as session1:
            parent1 = await session1.get(DataIngestionJob, parent.id)
            child_id_1 = await chain_job(
                parent1,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session1,
                dedup_active=True,
            )

        async with Sf() as session2:
            parent2 = await session2.get(DataIngestionJob, parent.id)
            child_id_2 = await chain_job(
                parent2,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session2,
                dedup_active=True,
            )

    # First chain wins; second is dedup'd.
    assert child_id_1 is not None
    assert child_id_2 is None

    # Exactly one aggregation row in the active state for this scope.
    async with Sf() as session:
        result = await session.execute(
            select(DataIngestionJob).where(
                DataIngestionJob.job_type == "aggregation",
                DataIngestionJob.module_type_id == parent.module_type_id,
                DataIngestionJob.year == parent.year,
            )
        )
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].id == child_id_1
        assert rows[0].state == IngestionState.NOT_STARTED

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_active_allows_new_row_after_first_finishes(pg_dsn):
    """Once the first aggregation transitions to FINISHED, the partial
    index releases the (module, year) slot and a follow-up chain creates
    a new row.  This is the eventual-consistency property: each fan-out
    batch gets one aggregation; subsequent batches are not blocked by
    historical jobs."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

    with patch(
        "app.tasks._chain.fire_and_forget",
        side_effect=lambda coro, *, name=None: (coro.close(), None)[1],
    ):
        async with Sf() as session:
            parent1 = await session.get(DataIngestionJob, parent.id)
            first_id = await chain_job(
                parent1,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session,
                dedup_active=True,
            )

        # Simulate the first aggregation finishing.
        async with Sf() as session:
            first = await session.get(DataIngestionJob, first_id)
            first.state = IngestionState.FINISHED
            first.result = IngestionResult.SUCCESS
            session.add(first)
            await session.commit()

        # A new fan-out batch chains again; partial index lets it through.
        async with Sf() as session:
            parent2 = await session.get(DataIngestionJob, parent.id)
            second_id = await chain_job(
                parent2,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session,
                dedup_active=True,
            )

    assert first_id is not None
    assert second_id is not None
    assert second_id != first_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_active_does_not_collide_across_modules_or_years(pg_dsn):
    """The partial index is keyed on ``(module_type_id, year)`` — two
    chains for different modules (or different years) both succeed.
    Without per-scope keying, dedup would freeze parallel module
    pipelines as a side-effect."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent_a = _parent_job(module_type_id=5, year=2025)
        parent_b = _parent_job(module_type_id=6, year=2025)  # diff module
        parent_c = _parent_job(module_type_id=5, year=2026)  # diff year
        for parent in (parent_a, parent_b, parent_c):
            await ensure_pipeline_for_job(session, parent)
        session.add_all([parent_a, parent_b, parent_c])
        await session.commit()
        await session.refresh(parent_a)
        await session.refresh(parent_b)
        await session.refresh(parent_c)

    chained_ids = []
    with patch(
        "app.tasks._chain.fire_and_forget",
        side_effect=lambda coro, *, name=None: (coro.close(), None)[1],
    ):
        for parent in (parent_a, parent_b, parent_c):
            async with Sf() as session:
                p = await session.get(DataIngestionJob, parent.id)
                cid = await chain_job(
                    p,
                    job_type="aggregation",
                    module_type_id=parent.module_type_id,
                    year=parent.year,
                    session=session,
                    dedup_active=True,
                )
                chained_ids.append(cid)

    # Three distinct rows, all created.
    assert all(cid is not None for cid in chained_ids)
    assert len(set(chained_ids)) == 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_active_skips_run_job_dispatch_on_collision(pg_dsn):
    """``fire_and_forget(run_job(...))`` must NOT be called on the
    dedup'd path — the existing pending row will run; a redundant
    dispatch would race-claim the same row."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

    fired_names = []

    def _record_fire(coro, *, name=None):
        coro.close()
        fired_names.append(name)
        return None

    with patch("app.tasks._chain.fire_and_forget", side_effect=_record_fire):
        async with Sf() as session:
            p1 = await session.get(DataIngestionJob, parent.id)
            await chain_job(
                p1,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session,
                dedup_active=True,
            )

        async with Sf() as session:
            p2 = await session.get(DataIngestionJob, parent.id)
            await chain_job(
                p2,
                job_type="aggregation",
                module_type_id=parent.module_type_id,
                year=parent.year,
                session=session,
                dedup_active=True,
            )

    # Only the first chain dispatched; the dedup'd second did not.
    assert len(fired_names) == 1

    await engine.dispose()


# Suppress unused asyncio import warning from CI envs.
_ = asyncio
