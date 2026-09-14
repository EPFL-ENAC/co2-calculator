"""The kg_co2eq sort must not re-acquire its per-row probe (#2527).

Sorting a submodule table by CO2 was the table's headline interaction and
its worst one: 5-7 s on the dev DB *regardless of page size*, because the
emission aggregate reached `carbon_report_module_id` only through
`data_entries` and Postgres resolved that by probing the emissions table
entry by entry -- ~37,400 buffer pages for 6,000 rows.

The fix denormalized the two immutable join keys onto
`data_entry_emissions` and added `ix_dee_module_type_entry` over
`(carbon_report_module_id, data_entry_type_id, data_entry_id)`
INCLUDE `(kg_co2eq, ...)`, so the aggregate reads one contiguous
index-only range instead.

Asserted in **buffer pages, not milliseconds**, for the reason
`test_submodule_get_scaling_pg.py` records at length: local hardware is
fast enough that a wall-clock budget passes on the broken query too.
Buffers are what actually changed, they are what the original measurement
was stated in, and they are identical on a laptop and in CI -- so this
needs no repeats, no minimum-of-N, and cannot flake on a loaded machine.

The plan is captured from the repository's own emitted SQL rather than a
reconstruction, so the test cannot drift into asserting on a query the
application no longer runs.

Requires Docker -- see ``conftest.py``'s ``postgres_container`` fixture.
"""

import json

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import emission_type_scope
from app.repositories.data_entry_repo import DataEntryRepository

pytestmark = pytest.mark.asyncio

# Enough rows that a per-row probe and an index range differ by an order of
# magnitude, small enough that seeding stays a couple of seconds.
TARGET_ENTRIES = 600
EMISSIONS_PER_ENTRY = 4

# Unrelated volume in another module. The point of the denormalized keys is
# that this is never touched; if the aggregate ever widens again, this is
# what makes the page count jump.
BACKGROUND_ENTRIES = 4_000
EMISSIONS_PER_BACKGROUND_ENTRY = 4

# Measured on this fixture, both shapes, same machine and same data:
#
#   before #2543 (aggregate reached the module through data_entries)
#       16,567 pages -- plan carried a Seq Scan, a Nested Loop and a
#       Subquery Scan
#   after  #2543 (aggregate reads ix_dee_module_type_entry directly)
#          461 pages -- no Seq Scan
#
# 36x. The budget sits ~2x above the good number and ~18x below the bad
# one, so it discriminates without being brittle: ordinary plan drift
# cannot reach it, and the regression cannot hide under it.
MAX_SHARED_BLOCKS = 900


@pytest_asyncio.fixture(scope="function")
async def seeded(pg_dsn, make_unit, make_carbon_report, make_carbon_report_module):
    """One target module worth sorting, plus unrelated background volume."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        unit = await make_unit(session)
        report = await make_carbon_report(session, unit_id=unit.id, year=2026)
        target = await make_carbon_report_module(
            session,
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.process_emissions.value,
        )
        other = await make_carbon_report_module(
            session,
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.headcount.value,
        )
        await session.commit()

    await _bulk_seed(
        pg_dsn,
        target.id,
        TARGET_ENTRIES,
        EMISSIONS_PER_ENTRY,
        det=DataEntryTypeEnum.process_emissions.value,
        emission_type=EmissionType.process_emissions.value,
        scope=emission_type_scope(EmissionType.process_emissions),
        data='{"category": "refrigerant", "quantity_kg": 10.0}',
    )
    await _bulk_seed(
        pg_dsn,
        other.id,
        BACKGROUND_ENTRIES,
        EMISSIONS_PER_BACKGROUND_ENTRY,
        det=DataEntryTypeEnum.member.value,
        emission_type=EmissionType.food.value,
        scope=None,
        # A plausible member payload, not `{}`: since #2527 C1 the database
        # rejects an empty object, because an entry carrying no data prices
        # nothing. These rows exist only as volume, but they still have to
        # look like rows the application could have written.
        data='{"fte": 1.0, "sius_code": "BG"}',
    )
    yield engine, factory, target
    await engine.dispose()


async def _bulk_seed(
    pg_dsn: str,
    module_id: int,
    entries: int,
    per_entry: int,
    *,
    det: int,
    emission_type: int,
    scope: int | None,
    data: str,
) -> None:
    """Raw asyncpg: this is volume, not the thing under test."""
    conn = await asyncpg.connect(pg_dsn.replace("postgresql+asyncpg", "postgresql"))
    try:
        async with conn.transaction():
            entry_ids = [
                r["id"]
                for r in await conn.fetch(
                    "INSERT INTO data_entries (data_entry_type_id, "
                    "carbon_report_module_id, data, status, created_at, updated_at) "
                    "SELECT $1, $2, $4::jsonb, "
                    "'VALIDATED'::dataentrystatusenum, NOW(), NOW() "
                    "FROM generate_series(1, $3) RETURNING id",
                    det,
                    module_id,
                    entries,
                    data,
                )
            ]
            await conn.executemany(
                "INSERT INTO data_entry_emissions (data_entry_id, emission_type_id, "
                "kg_co2eq, scope, computed_at, carbon_report_module_id, "
                "data_entry_type_id) "
                "SELECT $1, $2, random()*100, $3, NOW(), $4, $5 "
                "FROM generate_series(1, $6)",
                [
                    (eid, emission_type, scope, module_id, det, per_entry)
                    for eid in entry_ids
                ],
            )
            await conn.execute("ANALYZE data_entries")
            await conn.execute("ANALYZE data_entry_emissions")
    finally:
        await conn.close()


def _capture_statements(engine) -> list[tuple[str, tuple]]:
    """Record every statement the repository actually emits."""
    seen: list[tuple[str, tuple]] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append((statement, parameters))

    return seen


async def _explain(pg_dsn: str, statement: str, params: tuple) -> dict:
    """Run the captured statement under EXPLAIN and return its plan."""
    conn = await asyncpg.connect(pg_dsn.replace("postgresql+asyncpg", "postgresql"))
    try:
        rows = await conn.fetch(
            f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement}", *params
        )
        return json.loads(rows[0][0])[0]["Plan"]
    finally:
        await conn.close()


def _shared_blocks(plan: dict) -> int:
    """Total shared buffer pages hit or read across the whole plan tree."""
    total = plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0)
    for child in plan.get("Plans", []):
        total += _shared_blocks(child)
    return total


def _node_types(plan: dict) -> list[str]:
    out = [plan.get("Node Type", "")]
    for child in plan.get("Plans", []):
        out.extend(_node_types(child))
    return out


async def test_kg_co2eq_sort_reads_an_index_range_not_a_per_row_probe(seeded, pg_dsn):
    """Pins #2527: the emission aggregate stays off ``data_entries``.

    Fails if the aggregate goes back to reaching the module through
    ``data_entries`` -- the page count is the signal, and it moves by an
    order of magnitude, not a few percent.
    """
    engine, factory, target = seeded
    seen = _capture_statements(engine)

    async with factory() as session:
        rows = await DataEntryRepository(session).get_submodule_data(
            carbon_report_module_id=target.id,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            limit=100,
            offset=0,
            sort_by="kg_co2eq",
            sort_order="desc",
        )
    assert rows is not None

    emission_reads = [
        (s, p)
        for s, p in seen
        if "data_entry_emissions" in s and s.lstrip().upper().startswith("SELECT")
    ]
    assert emission_reads, "the sort never touched data_entry_emissions"

    worst = 0
    for statement, params in emission_reads:
        plan = await _explain(pg_dsn, statement, tuple(params or ()))
        blocks = _shared_blocks(plan)
        worst = max(worst, blocks)
        # The denormalized keys exist so this aggregate never needs the
        # entries table; a join back to it is the regression itself.
        assert "Seq Scan" not in _node_types(plan) or blocks <= MAX_SHARED_BLOCKS, (
            f"kg_co2eq sort fell back to a sequential scan: {_node_types(plan)}"
        )

    assert worst <= MAX_SHARED_BLOCKS, (
        f"kg_co2eq sort read {worst} shared buffer pages for {TARGET_ENTRIES} "
        f"entries (budget {MAX_SHARED_BLOCKS}). The aggregate is probing "
        f"row-by-row again instead of reading ix_dee_module_type_entry as a "
        f"range -- see #2527."
    )
