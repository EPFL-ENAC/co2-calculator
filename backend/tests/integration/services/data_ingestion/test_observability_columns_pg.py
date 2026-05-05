"""Postgres tests for Plan 310C observability columns.

Exercises the ``set_started_at`` + ``finished_at`` repo helpers against a
real Postgres so we cover ``func.now()`` resolving server-side and the
TIMESTAMPTZ column type.  SQLite covers the WHERE-guard semantics; this
covers production-shape SQL.
"""

import pytest
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
from app.repositories.data_ingestion import DataIngestionRepository


def _make_pending_job() -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=10,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=False,
        meta={},
    )


@pytest.mark.asyncio
async def test_started_at_idempotent_then_finished_at_set(pg_dsn):
    """End-to-end on PG: set_started_at + finished_at auto-stamp on FINISHED.

    Mirrors the runner's lifecycle: claim → set_started_at; retry → claim
    again → set_started_at again (no-op); on completion →
    update_ingestion_job(state=FINISHED) auto-stamps finished_at.  Both
    observability columns end populated and ``started_at`` is unchanged
    across the retry call.
    """
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            repo = DataIngestionRepository(session)

            job = _make_pending_job()
            session.add(job)
            await session.commit()
            assert job.id is not None
            job_id: int = job.id

            # First "claim" — stamps started_at.
            await repo.set_started_at(job_id)
            await session.commit()

            after_first = (
                await session.execute(
                    select(DataIngestionJob).where(DataIngestionJob.id == job_id)
                )
            ).scalar_one()
            await session.refresh(after_first)
            first_started_at = after_first.started_at
            assert first_started_at is not None
            assert after_first.finished_at is None

            # Retry — set_started_at must no-op via the IS NULL guard.
            await repo.set_started_at(job_id)
            await session.commit()

            after_retry = (
                await session.execute(
                    select(DataIngestionJob).where(DataIngestionJob.id == job_id)
                )
            ).scalar_one()
            await session.refresh(after_retry)
            assert after_retry.started_at == first_started_at, (
                "started_at must stay byte-equal across retries — the IS NULL "
                "guard is what makes finished_at - started_at a valid "
                "total-duration metric."
            )

            # Completion — finished_at column auto-stamps on the FINISHED
            # transition (no opt-in flag; the timestamp is derived from
            # the lifecycle state itself).
            await repo.update_ingestion_job(
                job_id,
                status_message="ok",
                metadata={},
                state=IngestionState.FINISHED,
                result=IngestionResult.SUCCESS,
            )
            await session.commit()

            final = (
                await session.execute(
                    select(DataIngestionJob).where(DataIngestionJob.id == job_id)
                )
            ).scalar_one()
            await session.refresh(final)

            assert final.started_at == first_started_at
            assert final.finished_at is not None
            assert final.finished_at >= final.started_at
            assert final.state == IngestionState.FINISHED
            assert final.result == IngestionResult.SUCCESS
    finally:
        await engine.dispose()
