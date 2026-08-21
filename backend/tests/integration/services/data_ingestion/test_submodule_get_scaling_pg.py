"""The submodule GET must not scale with the whole emissions table (#2050 J8).

Observed on dev, 2026-08-19:
``GET /carbon-reports/11604/modules/process-emissions/process_emissions`` took
**648ms** returning 947 bytes for a submodule holding one entry — while the
`POST` that created it took 85.7ms on the same page.

The cause is in ``get_submodule_data``'s generic branch: its aggregation
subquery has no module filter, so it groups **every row** in
``data_entry_emissions`` and then throws almost all of it away in the join.
The outer ``WHERE`` cannot help — Postgres cannot push a predicate through a
``GROUP BY``. Same shape Track H fixed for headcount, still live for every
type that resolves through the generic branch (process emissions, equipment,
purchases, research facilities, …), and the same shape
``get_professional_travel_trip_legs`` already restricts by ``data_entry_id``
with a comment about 700k rows dominating the query.

Asserted as scaling invariance rather than a wall-clock budget, for the reason
Track H's own perf test records: local hardware is fast enough that an
absolute millisecond budget passes on the broken query too. The slope is what
discriminates, and the slope is hardware-independent.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import time

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import emission_type_scope
from app.repositories.data_entry_repo import DataEntryRepository

pytestmark = pytest.mark.asyncio

# Two rounds, 20x apart: 50k then 1,000,000 unrelated data_entry_emissions
# rows — the top of the real range (the lead: 250k-1M).
EMISSIONS_PER_BACKGROUND_ENTRY = 200
SMALL_BACKGROUND_ENTRIES = 250
LARGE_BACKGROUND_ENTRIES = 4_750  # seeded on top of the small round

# This page reads one module's entries. Growing the rest of the table 20x must
# not grow its cost. Measured on the broken query: x6+.
MAX_SCALING_FACTOR = 3.0
# Floor, so noise on a fast path cannot manufacture a ratio failure in CI —
# the broken query clears it comfortably.
RATIO_FLOOR_MS = 25.0


@pytest_asyncio.fixture
async def psycopg_session(pg_dsn):
    """AsyncSession on the production driver (psycopg3)."""
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_background_load(pg_dsn: str, module_id: int, entries: int) -> None:
    """Bulk-COPY unrelated emission rows into their own module.

    Raw asyncpg COPY, not the ORM: this is background volume, not the thing
    under test, and per-row inserts would dominate the test's own runtime.
    """
    dsn = pg_dsn.replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "CREATE TEMP TABLE tmp_bg_entries ("
                "data_entry_type_id INT, carbon_report_module_id INT, "
                "data JSONB, status INT) ON COMMIT DROP"
            )
            await conn.copy_records_to_table(
                "tmp_bg_entries",
                records=[
                    (DataEntryTypeEnum.member.value, module_id, "{}", 1)
                    for _ in range(entries)
                ],
            )
            entry_ids = [
                r["id"]
                for r in await conn.fetch(
                    "INSERT INTO data_entries (data_entry_type_id, "
                    "carbon_report_module_id, data, status, created_at, "
                    "updated_at) "
                    "SELECT data_entry_type_id, carbon_report_module_id, "
                    "data, 'VALIDATED'::dataentrystatusenum, NOW(), NOW() "
                    "FROM tmp_bg_entries RETURNING id"
                )
            ]

            await conn.execute(
                "CREATE TEMP TABLE tmp_bg_emissions ("
                "data_entry_id INT, emission_type_id INT, kg_co2eq FLOAT) "
                "ON COMMIT DROP"
            )
            await conn.copy_records_to_table(
                "tmp_bg_emissions",
                records=[
                    (entry_id, EmissionType.food.value, 1.0)
                    for entry_id in entry_ids
                    for _ in range(EMISSIONS_PER_BACKGROUND_ENTRY)
                ],
            )
            await conn.execute(
                "INSERT INTO data_entry_emissions (data_entry_id, "
                "emission_type_id, kg_co2eq, computed_at) "
                "SELECT data_entry_id, emission_type_id, kg_co2eq, NOW() "
                "FROM tmp_bg_emissions"
            )
    finally:
        await conn.close()


async def test_process_emissions_submodule_get_ignores_table_wide_volume(
    pg_dsn,
    psycopg_session,
    make_unit,
    make_carbon_report,
    make_carbon_report_module,
):
    unit = await make_unit(psycopg_session)
    report = await make_carbon_report(psycopg_session, unit_id=unit.id, year=2025)
    # Distinct module_type_id per module: (carbon_report_id, module_type_id) is
    # a real unique constraint.
    background_module = await make_carbon_report_module(
        psycopg_session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
    )
    target_module = await make_carbon_report_module(
        psycopg_session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.process_emissions.value,
    )
    await psycopg_session.commit()

    entry = DataEntry(
        carbon_report_module_id=target_module.id,
        data_entry_type_id=DataEntryTypeEnum.process_emissions,
        status=DataEntryStatusEnum.VALIDATED,
        data={"category": "refrigerant", "quantity_kg": 10.0},
    )
    psycopg_session.add(entry)
    await psycopg_session.flush()
    psycopg_session.add(
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.process_emissions.value,
            kg_co2eq=42.0,
            scope=emission_type_scope(EmissionType.process_emissions),
        )
    )
    await psycopg_session.commit()

    await _seed_background_load(pg_dsn, background_module.id, SMALL_BACKGROUND_ENTRIES)

    repo = DataEntryRepository(psycopg_session)

    async def timed_get() -> tuple[float, object]:
        start = time.perf_counter()
        result = await repo.get_submodule_data(
            carbon_report_module_id=target_module.id,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )
        return (time.perf_counter() - start) * 1000, result

    # Warm-up: the first call pays statement compilation, which would otherwise
    # land entirely in the small baseline and hide the scaling being measured.
    await timed_get()
    small_ms, response = await timed_get()

    assert len(response.items) == 1
    assert response.items[0].kg_co2eq == pytest.approx(42.0)

    await _seed_background_load(pg_dsn, background_module.id, LARGE_BACKGROUND_ENTRIES)
    large_ms, response = await timed_get()

    small_rows = SMALL_BACKGROUND_ENTRIES * EMISSIONS_PER_BACKGROUND_ENTRY
    large_rows = (
        SMALL_BACKGROUND_ENTRIES + LARGE_BACKGROUND_ENTRIES
    ) * EMISSIONS_PER_BACKGROUND_ENTRY
    print(
        f"\n>>> {small_rows} rows: {small_ms:.1f}ms | "
        f"{large_rows} rows: {large_ms:.1f}ms (x{large_ms / small_ms:.1f})\n"
    )

    assert response.items[0].kg_co2eq == pytest.approx(42.0)
    assert large_ms < max(small_ms * MAX_SCALING_FACTOR, RATIO_FLOOR_MS), (
        f"{small_ms:.1f}ms at {small_rows} rows -> {large_ms:.1f}ms at "
        f"{large_rows} rows (x{large_ms / small_ms:.1f}): this page reads one "
        f"module's entries, so its cost must not grow with the size of the "
        f"whole data_entry_emissions table. The aggregation subquery is "
        f"missing its module restriction (#2050 J8)."
    )
