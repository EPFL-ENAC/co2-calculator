"""Real-Postgres tests for Plan 310A.

These tests exercise behavior that SQLite cannot:

- The partial unique index on ``(combo, is_current=TRUE)`` raising
  ``IntegrityError`` when two pods race to claim sibling jobs for the
  same combo.
- True transactional concurrency (separate engines = separate connections,
  separate PG transactions).
- ``claim_job`` refusing to demote a sibling that is already RUNNING.

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


@pytest.mark.asyncio
async def test_claim_blocked_by_running_sibling(pg_dsn):
    """A new pod cannot claim a sibling job while another sibling for the
    same combo is RUNNING.  Without the ``state != RUNNING`` guard in
    step 1, claim_job would demote the running sibling's ``is_current``
    and slip past the unique index — producing two concurrent runs for
    the same combo."""
    seed_engine = create_async_engine(pg_dsn, future=True)
    Sseed = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)
    async with Sseed() as s:
        # Sibling already in flight — pod-A claimed it earlier.
        running = _make_pending_job()
        running.state = IngestionState.RUNNING
        running.is_current = True
        running.locked_by = "pod-A"
        running.attempts = 1
        # New job for the same combo, freshly enqueued.
        candidate = _make_pending_job()
        s.add_all([running, candidate])
        await s.commit()
        assert running.id is not None and candidate.id is not None
        running_id: int = running.id
        candidate_id: int = candidate.id
    await seed_engine.dispose()

    # Pod-B tries to claim the new sibling.  The partial unique index
    # should reject step 2 because step 1 no longer demotes RUNNING
    # siblings.
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Sf() as session:
        claimed = await DataIngestionRepository(session).claim_job(
            candidate_id, "pod-B"
        )
    await engine.dispose()

    assert claimed is False, "claim_job should refuse when a sibling is RUNNING"

    # Verify the running sibling was untouched and the candidate stayed pending.
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    async with Vf() as session:
        repo = DataIngestionRepository(session)
        running_after = await repo.get_job_by_id(running_id)
        candidate_after = await repo.get_job_by_id(candidate_id)
        assert running_after is not None and candidate_after is not None

        # Running sibling unchanged.
        assert running_after.is_current is True
        assert running_after.state == IngestionState.RUNNING
        assert running_after.locked_by == "pod-A"
        assert running_after.attempts == 1
        # Candidate stayed pending; nothing leaked through.
        assert candidate_after.is_current is False
        assert candidate_after.state == IngestionState.NOT_STARTED
        assert candidate_after.locked_by is None
        assert candidate_after.attempts == 0
    await verify_engine.dispose()


@pytest.mark.asyncio
async def test_claim_demotes_finished_sibling(pg_dsn):
    """``claim_job`` must still demote a FINISHED sibling so the new run
    becomes the current one — fixing the RUNNING-protection guard must
    not break the normal previous-run-then-new-run path."""
    seed_engine = create_async_engine(pg_dsn, future=True)
    Sseed = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)
    async with Sseed() as s:
        finished = _make_pending_job()
        finished.state = IngestionState.FINISHED
        finished.is_current = True
        finished.locked_by = "pod-A"
        finished.attempts = 1
        candidate = _make_pending_job()
        s.add_all([finished, candidate])
        await s.commit()
        assert finished.id is not None and candidate.id is not None
        finished_id: int = finished.id
        candidate_id: int = candidate.id
    await seed_engine.dispose()

    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Sf() as session:
        claimed = await DataIngestionRepository(session).claim_job(
            candidate_id, "pod-B"
        )
    await engine.dispose()

    assert claimed is True

    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    async with Vf() as session:
        repo = DataIngestionRepository(session)
        finished_after = await repo.get_job_by_id(finished_id)
        candidate_after = await repo.get_job_by_id(candidate_id)
        assert finished_after is not None and candidate_after is not None

        # Previous FINISHED run was demoted.
        assert finished_after.is_current is False
        assert finished_after.state == IngestionState.FINISHED
        # New run took over.
        assert candidate_after.is_current is True
        assert candidate_after.state == IngestionState.RUNNING
        assert candidate_after.locked_by == "pod-B"
        assert candidate_after.attempts == 1
    await verify_engine.dispose()
