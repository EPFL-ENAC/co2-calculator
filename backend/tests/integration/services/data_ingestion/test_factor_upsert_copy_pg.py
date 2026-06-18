"""COPY-based factor upsert (bulk ingest performance).

``FactorRepository.upsert_factors`` routes through a COPY → staging →
``INSERT … SELECT … ON CONFLICT`` path on the production psycopg3
driver.  These tests run that path against the Docker Postgres on a
``postgresql+psycopg`` engine and assert the upsert contract the
VALUES-based fallback already guarantees: insert, update-in-place
with preserved ``factor.id``, and ``last_seen_job_id`` stamping.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository

pytestmark = pytest.mark.asyncio

DET = DataEntryTypeEnum.other_purchases.value


@pytest_asyncio.fixture(scope="function")
async def psycopg_session(pg_dsn):
    """AsyncSession on the production driver (psycopg3) so COPY runs."""
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _make_job(session) -> int:
    """last_seen_job_id is a real FK — stamp against an actual job row."""
    job = DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        ingestion_method=IngestionMethod.csv,
        target_type=TargetType.FACTORS,
        state=IngestionState.RUNNING,
    )
    session.add(job)
    await session.flush()
    if job.id is None:
        raise ValueError("job id not assigned")
    return job.id


def _factor(kind: str, value: float, year: int | None = 2026) -> Factor:
    return Factor(
        emission_type_id=1,
        data_entry_type_id=DET,
        classification={"purchase_kind": kind},
        values={"kg_co2eq_per_chf": value},
        year=year,
    )


async def _all_factors(session) -> list[Factor]:
    return (
        (
            await session.execute(
                select(Factor).where(col(Factor.data_entry_type_id) == DET)
            )
        )
        .scalars()
        .all()
    )


async def test_copy_upsert_inserts_and_stamps_job(psycopg_session):
    repo = FactorRepository(psycopg_session)

    job_id = await _make_job(psycopg_session)
    affected = await repo.upsert_factors(
        [_factor("lab", 1.0), _factor("it", 2.0), _factor("no-year", 3.0, year=None)],
        current_job_id=job_id,
    )
    await psycopg_session.commit()

    assert affected == 3
    rows = await _all_factors(psycopg_session)
    assert len(rows) == 3
    assert all(r.last_seen_job_id == job_id for r in rows)
    assert {r.year for r in rows} == {2026, None}


async def test_copy_upsert_updates_in_place_preserving_id(psycopg_session):
    """Reupload contract: same identity key updates values, keeps id —
    DataEntry.primary_factor_id references stay valid."""
    repo = FactorRepository(psycopg_session)

    job_a = await _make_job(psycopg_session)
    await repo.upsert_factors([_factor("lab", 1.0)], current_job_id=job_a)
    await psycopg_session.commit()
    original = (await _all_factors(psycopg_session))[0]
    original_id = original.id

    job_b = await _make_job(psycopg_session)
    affected = await repo.upsert_factors([_factor("lab", 9.9)], current_job_id=job_b)
    await psycopg_session.commit()
    # The upsert is raw SQL — expire the identity map so the re-read
    # below reflects the DB row, not the cached pre-update instance.
    psycopg_session.expire_all()

    assert affected == 1
    rows = await _all_factors(psycopg_session)
    assert len(rows) == 1  # updated, not duplicated
    assert rows[0].id == original_id
    assert rows[0].values == {"kg_co2eq_per_chf": 9.9}
    assert rows[0].last_seen_job_id == job_b


async def test_copy_upsert_multiple_batches_same_transaction(psycopg_session):
    """One job upserts several batches before committing — the staging
    table is created once and truncated between batches."""
    repo = FactorRepository(psycopg_session)

    job_id = await _make_job(psycopg_session)
    await repo.upsert_factors([_factor("a", 1.0)], current_job_id=job_id)
    await repo.upsert_factors([_factor("b", 2.0)], current_job_id=job_id)
    await psycopg_session.commit()

    rows = await _all_factors(psycopg_session)
    assert {r.classification["purchase_kind"] for r in rows} == {"a", "b"}
