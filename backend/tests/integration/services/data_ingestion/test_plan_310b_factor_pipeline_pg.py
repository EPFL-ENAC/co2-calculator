"""Real-Postgres tests for Plan 310B.

These tests exercise behavior that SQLite cannot:

- ``INSERT ... ON CONFLICT DO UPDATE`` against a partial unique index on
  ``(data_entry_type_id, year, emission_type_id, classification::text)``
  — keyed via JSONB so dict insertion order in Python is irrelevant.
- ``last_seen_job_id`` cross-table query for stale-factor detection.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.

The shared ``pg_dsn`` fixture builds the schema via
``SQLModel.metadata.create_all`` and does **not** run Alembic migrations,
so the Plan 310B partial unique indexes don't exist by default.  These
tests create them inline to mirror the production schema.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.user import UserProvider
from app.repositories.factor_repo import FactorRepository


async def _install_plan_310b_indexes(engine) -> None:
    """Create the partial unique indexes that Plan 310B's migration adds.

    ``pg_dsn`` builds tables via ``SQLModel.metadata.create_all``, which
    doesn't know about the migration's bare DDL.  Mirror it here so
    ``ON CONFLICT`` inference can find the index it needs to bind to.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity "
                "ON factors (data_entry_type_id, year, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NOT NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity_no_year "
                "ON factors (data_entry_type_id, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NULL"
            )
        )


def _seed_factor_job() -> DataIngestionJob:
    """A finished, current FACTORS job — referenced by ``last_seen_job_id``."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=1,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
    )


def _make_factor(
    classification: dict,
    *,
    data_entry_type_id: int = 1,
    year: int | None = 2025,
    values: dict | None = None,
    emission_type_id: int = 10000,
) -> Factor:
    return Factor(
        emission_type_id=emission_type_id,
        data_entry_type_id=data_entry_type_id,
        classification=classification,
        values=values or {"kg_co2eq": 1.0},
        year=year,
    )


@pytest.mark.asyncio
async def test_upsert_factors_inserts_new_row_with_last_seen_job_id(pg_dsn):
    """First upsert: row gets a fresh id and last_seen_job_id stamped."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_plan_310b_indexes(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        job = _seed_factor_job()
        session.add(job)
        await session.commit()
        assert job.id is not None
        job_id: int = job.id

        repo = FactorRepository(session)
        affected = await repo.upsert_factors(
            [_make_factor({"kind": "food", "subkind": None})],
            current_job_id=job_id,
        )
        await session.commit()

        assert affected == 1

        # Verify the row landed and is stamped with the job id.
        from sqlmodel import col, select

        rows = (
            (
                await session.execute(
                    select(Factor).where(col(Factor.data_entry_type_id) == 1)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].last_seen_job_id == job_id
        assert rows[0].id is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_factors_updates_existing_row_preserving_id(pg_dsn):
    """Second upsert with same identity key: same id, values updated,
    last_seen_job_id refreshed."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_plan_310b_indexes(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # Two jobs for the same combo — only one can be is_current=True
        # (existing partial unique index on the jobs table).
        job1 = _seed_factor_job()
        job1.is_current = False
        job2 = _seed_factor_job()
        session.add_all([job1, job2])
        await session.commit()
        assert job1.id is not None and job2.id is not None
        job1_id: int = job1.id
        job2_id: int = job2.id

        repo = FactorRepository(session)
        await repo.upsert_factors(
            [
                _make_factor(
                    {"kind": "food", "subkind": None},
                    values={"kg_co2eq": 100.0},
                )
            ],
            current_job_id=job1_id,
        )
        await session.commit()

        from sqlmodel import col, select

        first = (
            await session.execute(
                select(Factor).where(col(Factor.data_entry_type_id) == 1)
            )
        ).scalar_one()
        original_id = first.id

        # Second upsert: same identity, new values.
        await repo.upsert_factors(
            [
                _make_factor(
                    {"kind": "food", "subkind": None},
                    values={"kg_co2eq": 200.0},
                )
            ],
            current_job_id=job2_id,
        )
        await session.commit()
        # Drop the identity map so the verification select re-reads from DB
        # rather than returning the cached row from the first select.
        session.expire_all()

        rows = (
            (
                await session.execute(
                    select(Factor).where(col(Factor.data_entry_type_id) == 1)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, "upsert must not insert a duplicate row"
        assert rows[0].id == original_id, "factor id must be preserved"
        assert rows[0].values == {"kg_co2eq": 200.0}
        assert rows[0].last_seen_job_id == job2_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_factors_jsonb_key_order_resilience(pg_dsn):
    """Two upserts with the same classification keys in different
    insertion order resolve to one row (JSONB normalises key order).

    This is the silent-duplicate-row footgun the JSON → JSONB migration
    closes; without it, ``classification::text`` would differ between
    ``{"a":1,"b":2}`` and ``{"b":2,"a":1}`` and the partial unique index
    wouldn't trip.
    """
    engine = create_async_engine(pg_dsn, future=True)
    await _install_plan_310b_indexes(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        job = _seed_factor_job()
        session.add(job)
        await session.commit()
        assert job.id is not None
        job_id: int = job.id

        repo = FactorRepository(session)
        await repo.upsert_factors(
            [_make_factor({"kind": "plane", "subkind": "long_haul"})],
            current_job_id=job_id,
        )
        await session.commit()

        # Same logical classification, different dict insertion order.
        await repo.upsert_factors(
            [_make_factor({"subkind": "long_haul", "kind": "plane"})],
            current_job_id=job_id,
        )
        await session.commit()

        from sqlmodel import col, select

        rows = (
            (
                await session.execute(
                    select(Factor).where(col(Factor.data_entry_type_id) == 1)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, (
            "JSONB normalisation should treat the two dicts as identical"
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_stale_for_year_returns_outdated_factors(pg_dsn):
    """Factors whose ``last_seen_job_id`` predates the latest is_current
    successful FACTORS job for their (det, year) combo are returned;
    factors stamped with the latest job id are not."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_plan_310b_indexes(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # Older finished factor job — not is_current.
        old_job = _seed_factor_job()
        old_job.is_current = False
        # Newer is_current factor job — the "latest" reference.
        latest_job = _seed_factor_job()
        session.add_all([old_job, latest_job])
        await session.commit()
        assert old_job.id is not None and latest_job.id is not None
        old_id: int = old_job.id
        latest_id: int = latest_job.id

        # Two factors: one stamped with old_id (stale), one with latest_id (fresh).
        repo = FactorRepository(session)
        await repo.upsert_factors(
            [_make_factor({"kind": "food", "subkind": None})],
            current_job_id=old_id,
        )
        await repo.upsert_factors(
            [_make_factor({"kind": "waste", "subkind": None})],
            current_job_id=latest_id,
        )
        await session.commit()

        stale = await repo.list_stale_for_year(2025)
        # Only the food factor is stale: its last_seen_job_id < latest_id.
        # The waste factor was stamped with latest_id and is up to date.
        assert len(stale) == 1
        assert stale[0].classification == {"kind": "food", "subkind": None}
        assert stale[0].last_seen_job_id == old_id

    await engine.dispose()
