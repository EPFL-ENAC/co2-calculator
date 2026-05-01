"""Real-Postgres tests for Plan 310A.

These tests exercise behavior that SQLite cannot:

- The partial unique index on ``(combo, is_current=TRUE)`` raising
  ``IntegrityError`` when two pods race to claim sibling jobs for the
  same combo.
- True transactional concurrency (separate engines = separate connections,
  separate PG transactions).

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.repositories.data_ingestion import DataIngestionRepository


def _make_pending_job() -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=1,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=False,
    )


@pytest.mark.asyncio
async def test_concurrent_claim_same_combo_only_one_wins(pg_dsn):
    """Two pods racing to claim sibling jobs for the same combo —
    exactly one ``claim_job`` returns True; the other rolls back via
    ``IntegrityError`` from the partial unique index."""
    # Seed two pending jobs in the same combo.
    seed_engine = create_async_engine(pg_dsn, future=True)
    Sseed = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)
    async with Sseed() as s:
        j1, j2 = _make_pending_job(), _make_pending_job()
        s.add_all([j1, j2])
        await s.commit()
        assert j1.id is not None and j2.id is not None
        j1_id: int = j1.id
        j2_id: int = j2.id
    await seed_engine.dispose()

    # Each "pod" gets its own engine → its own connection pool → its own
    # PG transaction.  Without this, both claims would share one
    # connection and serialize trivially.
    engine_a = create_async_engine(pg_dsn, future=True)
    engine_b = create_async_engine(pg_dsn, future=True)
    Sa = async_sessionmaker(engine_a, class_=AsyncSession, expire_on_commit=False)
    Sb = async_sessionmaker(engine_b, class_=AsyncSession, expire_on_commit=False)

    async def claim(factory, job_id: int, pod_id: str) -> bool:
        async with factory() as session:
            return await DataIngestionRepository(session).claim_job(job_id, pod_id)

    try:
        results = await asyncio.gather(
            claim(Sa, j1_id, "pod-A"),
            claim(Sb, j2_id, "pod-B"),
        )
    finally:
        await engine_a.dispose()
        await engine_b.dispose()

    assert sorted(results) == [False, True], (
        f"Expected exactly one winner, got {results}"
    )

    # Verify final DB state: exactly one row is_current=TRUE for this combo.
    verify_engine = create_async_engine(pg_dsn, future=True)
    Sv = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    async with Sv() as s:
        repo = DataIngestionRepository(s)
        winner_id = j1_id if results[0] is True else j2_id
        loser_id = j2_id if results[0] is True else j1_id

        winner = await repo.get_job_by_id(winner_id)
        loser = await repo.get_job_by_id(loser_id)
        assert winner is not None and loser is not None
        assert winner.is_current is True
        assert winner.state == IngestionState.RUNNING
        assert winner.locked_by in ("pod-A", "pod-B")
        assert winner.attempts == 1
        # Loser stayed pending; its lock was never set.
        assert loser.is_current is False
        assert loser.state == IngestionState.NOT_STARTED
        assert loser.locked_by is None
        assert loser.attempts == 0
    await verify_engine.dispose()
