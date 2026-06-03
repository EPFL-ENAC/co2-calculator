"""Real-Postgres tests for #1064 ``chain_job(dedup_config=EMISSION_RECALC_DEDUP)``.

Pins the contract that two ``chain_job`` calls for the same
``(module_type_id, data_entry_type_id, year, job_type='emission_recalc')``
scope collapse to a single pending row via the
``uq_emission_recalc_active`` partial unique index.  Mirrors the
shape of ``test_aggregation_dedup_chain_pg.py`` with the three-column
scope substitution.

SQLite can't represent partial indexes the same way Postgres does and
the ``IngestionState`` enum types differ, so this is a real-PG-only
test.  Requires Docker — see ``conftest.py``'s ``postgres_container``
fixture.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.tasks._chain import EMISSION_RECALC_DEDUP, chain_job

from .conftest import ensure_pipeline_for_job


def _parent_factor_job(
    module_type_id: int = 5,
    data_entry_type_id: int = 11,
    year: int = 2025,
) -> DataIngestionJob:
    """A minimal ``factor_ingest`` parent that ``chain_job`` inherits from."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        is_current=True,
        job_type="factor_ingest",
        pipeline_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_back_to_back_factor_reuploads_collapse_to_one_recalc(pg_dsn):
    """Two sequential ``chain_job(emission_recalc, dedup_config=EMISSION_RECALC_DEDUP)``
    calls for the same ``(module, det, year)`` → only the first creates
    a row; the second sees the existing pending row and returns ``None``.

    Models the user-visible scenario in #1064 / B-M1: a user uploads a
    corrected factors CSV seconds after the first upload — the second
    fan-out must not queue a redundant recalc on top of the pending one.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_factor_job()
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
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session1,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

        async with Sf() as session2:
            parent2 = await session2.get(DataIngestionJob, parent.id)
            child_id_2 = await chain_job(
                parent2,
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session2,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

    # First chain wins; second is dedup'd.
    assert child_id_1 is not None
    assert child_id_2 is None

    # Exactly one emission_recalc child row in the active state for
    # this scope (the first parent factor row stays in its own
    # job_type='factor_ingest' bucket and is not counted).
    async with Sf() as session:
        result = await session.execute(
            select(DataIngestionJob).where(
                DataIngestionJob.job_type == "emission_recalc",
                DataIngestionJob.module_type_id == parent.module_type_id,
                DataIngestionJob.data_entry_type_id == parent.data_entry_type_id,
                DataIngestionJob.year == parent.year,
            )
        )
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].id == child_id_1
        assert rows[0].state == IngestionState.NOT_STARTED

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_releases_after_first_recalc_finishes(pg_dsn):
    """Once the first emission_recalc transitions to FINISHED, the
    partial index releases the (module, det, year) slot and a follow-up
    chain creates a new row.  Each fan-out batch gets one recalc;
    subsequent batches are not blocked by historical jobs."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_factor_job()
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
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

        # Simulate the first recalc finishing.
        async with Sf() as session:
            first = await session.get(DataIngestionJob, first_id)
            first.state = IngestionState.FINISHED
            session.add(first)
            await session.commit()

        # A new fan-out batch chains again; partial index lets it through.
        async with Sf() as session:
            parent2 = await session.get(DataIngestionJob, parent.id)
            second_id = await chain_job(
                parent2,
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

    assert first_id is not None
    assert second_id is not None
    assert second_id != first_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_does_not_collide_across_dets_or_years(pg_dsn):
    """The partial index is keyed on ``(module_type_id,
    data_entry_type_id, year)`` — three chains differing in det,
    year, or both all succeed.  Without per-det keying, a multi-det
    factor reupload would serialize into one recalc instead of one
    per det."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent_a = _parent_factor_job(
            module_type_id=5, data_entry_type_id=11, year=2025
        )
        parent_b = _parent_factor_job(
            module_type_id=5, data_entry_type_id=12, year=2025
        )  # different det
        parent_c = _parent_factor_job(
            module_type_id=5, data_entry_type_id=11, year=2026
        )  # different year
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
                    job_type="emission_recalc",
                    module_type_id=parent.module_type_id,
                    data_entry_type_id=parent.data_entry_type_id,
                    year=parent.year,
                    session=session,
                    dedup_config=EMISSION_RECALC_DEDUP,
                )
                chained_ids.append(cid)

    assert all(cid is not None for cid in chained_ids)
    assert len(set(chained_ids)) == 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_dedup_skips_run_job_dispatch_on_collision(pg_dsn):
    """``fire_and_forget(run_job(...))`` must NOT be called on the
    dedup'd path — the existing pending row will run; a redundant
    dispatch would race-claim the same row."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_factor_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

    fired_names: list[str | None] = []

    def _record_fire(coro, *, name=None):
        coro.close()
        fired_names.append(name)
        return None

    with patch("app.tasks._chain.fire_and_forget", side_effect=_record_fire):
        async with Sf() as session:
            p1 = await session.get(DataIngestionJob, parent.id)
            await chain_job(
                p1,
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

        async with Sf() as session:
            p2 = await session.get(DataIngestionJob, parent.id)
            await chain_job(
                p2,
                job_type="emission_recalc",
                module_type_id=parent.module_type_id,
                data_entry_type_id=parent.data_entry_type_id,
                year=parent.year,
                session=session,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

    # Only the first chain dispatched; the dedup'd second did not.
    assert len(fired_names) == 1


@pytest.mark.asyncio
async def test_dedup_config_rejects_null_scope_keys(pg_dsn):
    """``chain_job`` must refuse to use EMISSION_RECALC_DEDUP when any
    scope column would be NULL on the child row.  PG treats NULLs as
    distinct in unique indexes, so a NULL would silently bypass dedup
    at the index level — we'd rather raise than create a half-broken
    row."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        parent = _parent_factor_job()
        await ensure_pipeline_for_job(session, parent)
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

    with patch(
        "app.tasks._chain.fire_and_forget",
        side_effect=lambda coro, *, name=None: (coro.close(), None)[1],
    ):
        async with Sf() as session:
            p = await session.get(DataIngestionJob, parent.id)
            with pytest.raises(ValueError, match="scope keys must be set"):
                # data_entry_type_id is one of EMISSION_RECALC_DEDUP's
                # scope columns and does NOT inherit from the parent;
                # passing None must trip the entry guard.
                await chain_job(
                    p,
                    job_type="emission_recalc",
                    module_type_id=parent.module_type_id,
                    data_entry_type_id=None,
                    year=parent.year,
                    session=session,
                    dedup_config=EMISSION_RECALC_DEDUP,
                )

    await engine.dispose()
