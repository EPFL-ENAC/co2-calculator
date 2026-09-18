"""#2527 B1 — the factor gate's two modes, against a real Postgres.

Before B1 every ingest and every recalc of a ``(module_type, year)`` took
the gate exclusively, so a unit's 200-row upload waited head-to-tail
behind every other unit's upload of the same module and year — the 63 s
@5 / 184 s @20 tail measured in #2529.

B1 keeps the invariant that actually mattered (factor writes exclude
factor reads) and drops the rest: a unit-scoped writer takes the gate
SHARED and holds an exclusive lock on the one carbon report module whose
rows it rewrites. The conflict matrix this file pins:

| holder                       | waiter                       | blocks |
| ---------------------------- | ---------------------------- | ------ |
| factor_ingest (exclusive)    | scoped recalc                | yes    |
| per-year ingest (exclusive)  | scoped ingest                | yes    |
| scoped ingest, module 101    | scoped recalc, module 101    | yes    |
| scoped ingest, module 101    | scoped recalc, module 102    | no     |

Advisory locks are re-entrant per session, so every test drives two
independent engines — one connection each — or it would prove nothing.
The waiter sets ``lock_timeout`` so a genuine block surfaces as 55P03
instead of hanging the suite; ``pg_advisory_xact_lock`` honours it.

The handlers' ingest bodies are not run here: what is under test is the
lock, and each side takes it through the same resolver its handler uses
(``_pinned_module_id`` / ``_module_scope`` + ``_lock_module_id``), so a
resolver that misclassifies a job fails these tests too.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import DataIngestionJob
from app.tasks._locks import (
    _FACTOR_RECALC_LOCK_CATEGORY,
    _MODULE_WRITE_LOCK_CATEGORY,
    _encode_module_year_key,
    acquire_factor_recalc_lock,
)
from app.tasks.emission_recalculation_tasks import _lock_module_id, _module_scope
from app.tasks.ingestion_tasks import _pinned_module_id

MODULE_TYPE_ID = 4
YEAR = 2026
DET_ID = 22
LOCK_TIMEOUT = "400ms"
LOCK_NOT_AVAILABLE = "55P03"


@asynccontextmanager
async def _connection(dsn: str) -> AsyncIterator[AsyncSession]:
    """A session on its own engine — one backend, one advisory-lock owner."""
    engine = create_async_engine(dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


def _ingest_job(carbon_report_module_id: int | None) -> DataIngestionJob:
    config = {}
    if carbon_report_module_id is not None:
        config["carbon_report_module_id"] = carbon_report_module_id
    return DataIngestionJob(
        job_type="csv_ingest",
        module_type_id=MODULE_TYPE_ID,
        data_entry_type_id=DET_ID,
        year=YEAR,
        meta={"config": config},
    )


def _recalc_job(carbon_report_module_id: int | None) -> DataIngestionJob:
    config = {}
    if carbon_report_module_id is not None:
        config["carbon_report_module_ids"] = [carbon_report_module_id]
    return DataIngestionJob(
        job_type="emission_recalc",
        module_type_id=MODULE_TYPE_ID,
        data_entry_type_id=DET_ID,
        year=YEAR,
        meta={"config": config},
    )


async def _take_as_ingest(session: AsyncSession, job: DataIngestionJob) -> None:
    """Exactly what ``csv_ingest_handler`` / ``api_ingest_handler`` do."""
    await acquire_factor_recalc_lock(
        session,
        module_type_id=job.module_type_id,
        year=job.year,
        handler_label="csv_ingest",
        carbon_report_module_id=_pinned_module_id(job),
    )


async def _take_as_recalc(session: AsyncSession, job: DataIngestionJob) -> None:
    """Exactly what ``emission_recalc_handler`` does."""
    await acquire_factor_recalc_lock(
        session,
        module_type_id=job.module_type_id,
        year=job.year,
        handler_label="emission_recalc",
        carbon_report_module_id=_lock_module_id(0, _module_scope(job)),
    )


async def _take_as_factor_ingest(session: AsyncSession) -> None:
    """``factor_ingest_handler`` — the writer, always exclusive."""
    await acquire_factor_recalc_lock(
        session,
        module_type_id=MODULE_TYPE_ID,
        year=YEAR,
        handler_label="factor_ingest",
    )


async def _arm_lock_timeout(session: AsyncSession) -> None:
    """Turn "waits forever" into a 55P03 the test can assert on."""
    await session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))


async def _granted_advisory_modes(session: AsyncSession) -> dict[tuple[int, int], str]:
    """Granted advisory locks in this plan's two categories, by (cat, key)."""
    rows = await session.execute(
        text(
            "SELECT classid, objid, mode FROM pg_locks "
            "WHERE locktype = 'advisory' AND granted "
            "AND classid IN (:factor_cat, :module_cat)"
        ),
        {
            "factor_cat": _FACTOR_RECALC_LOCK_CATEGORY,
            "module_cat": _MODULE_WRITE_LOCK_CATEGORY,
        },
    )
    return {(row.classid, row.objid): row.mode for row in rows}


def _assert_blocked(excinfo: pytest.ExceptionInfo[DBAPIError]) -> None:
    sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
    assert sqlstate == LOCK_NOT_AVAILABLE, excinfo.value


@pytest.mark.asyncio
async def test_scoped_ingest_shares_the_gate_and_locks_its_own_module(pg_dsn):
    """The mode split, read straight out of ``pg_locks``.

    Asserting the modes rather than only the timings makes the change
    legible: whoever reads this next sees which lock is shared and which
    is exclusive without reconstructing it from a race.
    """
    async with _connection(pg_dsn) as holder, _connection(pg_dsn) as observer:
        await _take_as_ingest(holder, _ingest_job(101))
        modes = await _granted_advisory_modes(observer)

    gate_key = (
        _FACTOR_RECALC_LOCK_CATEGORY,
        _encode_module_year_key(MODULE_TYPE_ID, YEAR),
    )
    assert modes.get(gate_key) == "ShareLock", modes
    assert modes.get((_MODULE_WRITE_LOCK_CATEGORY, 101)) == "ExclusiveLock", modes


@pytest.mark.asyncio
async def test_unscoped_recalc_keeps_the_exclusive_gate(pg_dsn):
    """A whole-slice recalc has no single module bounding its writes."""
    async with _connection(pg_dsn) as holder, _connection(pg_dsn) as observer:
        await _take_as_recalc(holder, _recalc_job(None))
        modes = await _granted_advisory_modes(observer)

    gate_key = (
        _FACTOR_RECALC_LOCK_CATEGORY,
        _encode_module_year_key(MODULE_TYPE_ID, YEAR),
    )
    assert modes.get(gate_key) == "ExclusiveLock", modes
    assert not [key for key in modes if key[0] == _MODULE_WRITE_LOCK_CATEGORY], modes


@pytest.mark.asyncio
async def test_factor_ingest_still_excludes_a_scoped_recalc(pg_dsn):
    """The invariant B1 must not break: no recalc reads factors mid-write."""
    async with _connection(pg_dsn) as writer, _connection(pg_dsn) as reader:
        await _take_as_factor_ingest(writer)
        await _arm_lock_timeout(reader)
        with pytest.raises(DBAPIError) as excinfo:
            await _take_as_recalc(reader, _recalc_job(101))
        _assert_blocked(excinfo)


@pytest.mark.asyncio
async def test_per_year_ingest_still_excludes_a_scoped_ingest(pg_dsn):
    """A ``MODULE_PER_YEAR`` upload resolves a module per unit from the CSV
    and deletes across all of them, so it has no pin and stays exclusive —
    a unit-scoped upload of the same module and year must still wait.
    """
    async with _connection(pg_dsn) as per_year, _connection(pg_dsn) as scoped:
        await _take_as_ingest(per_year, _ingest_job(None))
        await _arm_lock_timeout(scoped)
        with pytest.raises(DBAPIError) as excinfo:
            await _take_as_ingest(scoped, _ingest_job(101))
        _assert_blocked(excinfo)


@pytest.mark.asyncio
async def test_same_module_ingest_and_recalc_still_serialize(pg_dsn):
    """The pre-import DELETE cascade and the emission rewrite hit the same
    rows when they share a carbon report module — the 0.3 s vs 3 min
    row-lock queue #1236 fixed. That protection survives B1 intact.
    """
    async with _connection(pg_dsn) as ingest, _connection(pg_dsn) as recalc:
        await _take_as_ingest(ingest, _ingest_job(101))
        await _arm_lock_timeout(recalc)
        with pytest.raises(DBAPIError) as excinfo:
            await _take_as_recalc(recalc, _recalc_job(101))
        _assert_blocked(excinfo)


@pytest.mark.asyncio
async def test_different_modules_run_concurrently(pg_dsn):
    """The whole point of B1 — and it is what did not hold before it.

    Two units uploading the same module and year touch disjoint rows;
    with the old exclusive gate the second waited for the first to
    commit, which is the head-to-tail serialization behind the tail.
    ``lock_timeout`` is armed here too: if this ever starts blocking
    again it fails as 55P03 rather than hanging.
    """
    async with (
        _connection(pg_dsn) as unit_a,
        _connection(pg_dsn) as unit_b,
        _connection(pg_dsn) as observer,
    ):
        await _take_as_ingest(unit_a, _ingest_job(101))
        await _arm_lock_timeout(unit_b)
        await _take_as_recalc(unit_b, _recalc_job(102))
        modes = await _granted_advisory_modes(observer)

    assert modes.get((_MODULE_WRITE_LOCK_CATEGORY, 101)) == "ExclusiveLock", modes
    assert modes.get((_MODULE_WRITE_LOCK_CATEGORY, 102)) == "ExclusiveLock", modes
