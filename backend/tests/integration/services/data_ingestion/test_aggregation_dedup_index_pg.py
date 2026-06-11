"""Postgres tests for the Plan 310-D ``uq_aggregation_active`` partial
unique index.

The migration creates a partial unique index on ``(module_type_id, year)``
restricted to ``job_type = 'aggregation' AND state IN
(NOT_STARTED, QUEUED, RUNNING)``.  The index is declared on the
``DataIngestionJob`` model, so the shared ``pg_dsn`` fixture builds it via
``SQLModel.metadata.create_all`` — no inline DDL needed.

What we cover:

- Two NOT_STARTED ``aggregation`` rows with the same ``(module_type_id,
  year)`` → second insert raises ``IntegrityError`` (the dedup window
  catches duplicates).
- One NOT_STARTED + one FINISHED for the same scope → both succeed
  (FINISHED rows are excluded from the partial index, so historical
  jobs don't block new ones).
- Two NOT_STARTED rows with DIFFERENT ``(module_type_id, year)`` →
  both succeed (dedup is per-scope, not global).
- Non-``aggregation`` job_types are unaffected (the index is
  job_type-scoped).
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
)
from app.models.user import UserProvider


def _make_aggregation_job(
    *,
    module_type_id: int,
    year: int,
    state: IngestionState = IngestionState.NOT_STARTED,
    job_type: str = "aggregation",
) -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        year=year,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=state,
        job_type=job_type,
        is_current=False,
        meta={},
    )


@pytest.mark.asyncio
async def test_two_active_aggregation_jobs_same_scope_raises(
    pg_dsn,
):
    """Two NOT_STARTED aggregation rows for the same (module_type_id,
    year) violate the partial unique index → second insert raises."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(_make_aggregation_job(module_type_id=11, year=2025))
            await session.commit()

        async with factory() as session:
            session.add(_make_aggregation_job(module_type_id=11, year=2025))
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_finished_does_not_block_new_active(
    pg_dsn,
):
    """FINISHED rows are outside the dedup window — a NOT_STARTED
    aggregation can be inserted alongside an already-FINISHED one for
    the same scope.  Otherwise historical jobs would permanently block
    new aggregations."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(
                _make_aggregation_job(
                    module_type_id=11,
                    year=2025,
                    state=IngestionState.FINISHED,
                )
            )
            await session.commit()

        async with factory() as session:
            session.add(
                _make_aggregation_job(
                    module_type_id=11,
                    year=2025,
                    state=IngestionState.NOT_STARTED,
                )
            )
            # Must succeed — partial index excludes FINISHED.
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_different_scopes_both_succeed(pg_dsn):
    """Dedup is per-(module_type_id, year) scope.  Different module
    types or different years run in parallel — covering all three
    cross-product cases (different module, different year, different
    both)."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(_make_aggregation_job(module_type_id=11, year=2025))
            session.add(_make_aggregation_job(module_type_id=12, year=2025))
            session.add(_make_aggregation_job(module_type_id=11, year=2026))
            session.add(_make_aggregation_job(module_type_id=12, year=2026))
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_non_aggregation_job_type_unaffected(
    pg_dsn,
):
    """The partial index is scoped to ``job_type = 'aggregation'``;
    other job types share the table without dedup interference."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(
                _make_aggregation_job(
                    module_type_id=11, year=2025, job_type="emission_recalc"
                )
            )
            session.add(
                _make_aggregation_job(
                    module_type_id=11, year=2025, job_type="emission_recalc"
                )
            )
            # Same scope, same non-aggregation job_type — both must
            # succeed because the index excludes them.
            await session.commit()
    finally:
        await engine.dispose()
