"""Real-Postgres tests for Plan 310B.

These tests exercise behavior that SQLite cannot:

- ``INSERT ... ON CONFLICT DO UPDATE`` against a partial unique index on
  ``(data_entry_type_id, year, emission_type_id, classification::text)``
  — keyed via JSONB so dict insertion order in Python is irrelevant.
- ``last_seen_job_id`` cross-table query for stale-factor detection.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.

The shared ``pg_dsn`` fixture (in ``conftest.py``) layers the
Plan 310B migration's partial unique indexes on top of the
``SQLModel.metadata.create_all`` schema produced by ``pg_dsn``, so the
upsert path's ``ON CONFLICT`` inference has a target index to bind to.
"""

import pytest
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


@pytest.mark.asyncio
async def test_list_stale_for_year_handles_multi_type_factors_job(pg_dsn):
    """Regression: multi-type FACTORS jobs (``data_entry_type_id`` NULL,
    ``module_type_id`` set — e.g. ``equipments_factors.csv`` covering
    ``it`` + ``scientific`` under ``equipment``) must
    be expanded to the dets they cover when computing the stale-threshold.

    Earlier shape: ``list_stale_for_year`` joined ``Factor.det = Job.det``,
    so a multi-type job (``Job.det = NULL``) failed the equality and the
    factor row was dropped from the result entirely.  Effect: any stale
    factor written by a multi-type CSV ingest was silently invisible to
    operators.
    """
    from app.models.data_entry import DataEntryTypeEnum
    from app.models.module_type import ModuleTypeEnum

    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    module_id = ModuleTypeEnum.equipment.value
    det_it = DataEntryTypeEnum.it.value
    det_scientific = DataEntryTypeEnum.scientific.value

    def _multi_type_job() -> DataIngestionJob:
        """Job with det=NULL, module set — the shape produced by uploading
        a multi-type CSV like ``equipments_factors.csv``."""
        return DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=module_id,
            data_entry_type_id=None,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=False,
        )

    async with Sf() as session:
        old_job = _multi_type_job()
        latest_job = _multi_type_job()
        latest_job.is_current = True
        session.add_all([old_job, latest_job])
        await session.commit()
        assert old_job.id is not None and latest_job.id is not None
        old_id: int = old_job.id
        latest_id: int = latest_job.id

        repo = FactorRepository(session)

        # One stale factor (stamped by the old job) under det=it.
        await repo.upsert_factors(
            [
                _make_factor(
                    {"kind": "Laptop", "subkind": "Standard"},
                    data_entry_type_id=det_it,
                )
            ],
            current_job_id=old_id,
        )
        # One fresh factor (stamped by the latest job) under det=scientific.
        # Different det proves the multi-type expansion covers the whole
        # module, not just one of its dets.
        await repo.upsert_factors(
            [
                _make_factor(
                    {"kind": "Centrifugation", "subkind": "Ultra"},
                    data_entry_type_id=det_scientific,
                )
            ],
            current_job_id=latest_id,
        )
        await session.commit()

        stale = await repo.list_stale_for_year(2025)
        assert len(stale) == 1, (
            "multi-type FACTORS jobs must expand to their covered dets "
            "when resolving the stale-threshold"
        )
        assert stale[0].data_entry_type_id == det_it
        assert stale[0].last_seen_job_id == old_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_stale_for_year_returns_empty_when_no_factor_job(pg_dsn):
    """No is_current FACTORS job for the requested year → return [] rather
    than treat every factor as stale.  Without this short-circuit, the
    endpoint would noisily flag every existing factor on a year that never
    had a CSV uploaded.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # Seed a finished FACTORS job for 2024 (different year than the query)
        # plus a factor row stamped against it.
        other_year_job = _seed_factor_job()
        other_year_job.year = 2024
        session.add(other_year_job)
        await session.commit()
        assert other_year_job.id is not None

        repo = FactorRepository(session)
        await repo.upsert_factors(
            [_make_factor({"kind": "food", "subkind": None}, year=2024)],
            current_job_id=other_year_job.id,
        )
        await session.commit()

        # Query for 2025 — no is_current FACTORS job exists for that year.
        stale = await repo.list_stale_for_year(2025)
        assert stale == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_latest_factor_job_per_det_skips_unknown_module(pg_dsn):
    """A multi-type FACTORS job with a ``module_type_id`` that no longer
    maps to a ``ModuleTypeEnum`` value (legacy enum cleanup, hand-edited
    row, etc.) must be skipped silently rather than crash the stale
    detection.  Defensive: lets operators view stale factors even when
    one rogue job row would otherwise raise ValueError.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # One job with a bogus module_type_id, marked is_current — used to
        # exercise the ValueError branch in _latest_factor_job_per_det.
        rogue = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=99999,  # not a valid ModuleTypeEnum
            data_entry_type_id=None,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
        session.add(rogue)
        await session.commit()

        repo = FactorRepository(session)
        # Should not raise.  No factors → returns empty map, list_stale
        # returns [].
        latest = await repo._latest_factor_job_per_det(2025)
        assert latest == {}

        stale = await repo.list_stale_for_year(2025)
        assert stale == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_latest_factor_job_per_det_skips_both_nulls(pg_dsn):
    """A FACTORS job with both ``module_type_id`` and ``data_entry_type_id``
    NULL has no meaningful scope — it covers no factors, so it shouldn't
    contribute to the stale-threshold map.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # Both NULLs — degenerate but possible if someone POSTs a
        # malformed sync request that bypasses validation.
        unscoped = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=None,
            data_entry_type_id=None,
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
        session.add(unscoped)
        await session.commit()

        repo = FactorRepository(session)
        latest = await repo._latest_factor_job_per_det(2025)
        assert latest == {}

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_stale_filters_to_csv_ingestion_method(pg_dsn):
    """Plan 310B fix (Copilot follow-up): ``list_stale_for_year`` must
    only consider FACTORS jobs whose ``ingestion_method == csv``.

    The bug it guards against: ``last_seen_job_id`` is ONLY stamped by
    the CSV upsert path.  If a ``computed`` FACTORS job (factor recompute,
    distinct from a CSV upload) becomes is_current later, its higher id
    would shadow the latest CSV upload's id and make every CSV-stamped
    factor look stale on ``/factors/stale``.

    This test seeds a CSV factor job (id=N) plus a later computed factor
    job (id=N+1) for the same (det, year) and verifies a factor stamped
    by the CSV job is NOT reported as stale (because the computed job
    is filtered out of the threshold map).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        # CSV factor job — stamps last_seen_job_id on factors it writes.
        csv_job = _seed_factor_job()
        csv_job.is_current = False  # to allow second is_current row
        # Later computed factor job — different ingestion_method, NOT a
        # CSV upload, so it never stamps last_seen_job_id.
        computed_job = _seed_factor_job()
        computed_job.ingestion_method = IngestionMethod.computed
        # Plan A's partial unique index on is_current allows only one
        # is_current per (module, det, target, ingestion_method, year),
        # so distinct ingestion_methods can both be is_current — that's
        # exactly the production scenario this test guards.
        session.add_all([csv_job, computed_job])
        await session.commit()
        assert csv_job.id is not None and computed_job.id is not None
        csv_id: int = csv_job.id
        computed_id: int = computed_job.id

        # Sanity: computed job has a strictly greater id (would shadow
        # the CSV job under a naive max(id) join).
        assert computed_id > csv_id

        repo = FactorRepository(session)
        # Stamp the factor with the CSV job's id — production path.
        await repo.upsert_factors(
            [_make_factor({"kind": "food", "subkind": None})],
            current_job_id=csv_id,
        )
        await session.commit()

        # Without the ingestion_method filter, the latest threshold
        # would be max(csv_id, computed_id) = computed_id, and the
        # factor (last_seen=csv_id < computed_id) would appear stale.
        # WITH the filter, only csv_id is considered → factor NOT stale.
        stale = await repo.list_stale_for_year(2025)
        assert stale == [], (
            "computed FACTORS jobs must be excluded from the stale-"
            "threshold; only csv jobs stamp last_seen_job_id"
        )

    await engine.dispose()
