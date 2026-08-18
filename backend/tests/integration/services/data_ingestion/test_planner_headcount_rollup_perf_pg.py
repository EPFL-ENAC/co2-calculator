"""Performance regression test for #2050 Track H.

``GET /v1/carbon-reports/{carbon_report_id}/modules/{module_id}/{submodule_id}``
for ``planner_headcount`` must not scale with the size of the whole
``data_entry_emissions`` table. Before the fix, ``is_headcount_entry``
excluded ``planner_headcount``, so ``get_submodule_data`` fell through to
an unfiltered ``GROUP BY data_entry_emissions.data_entry_id`` over every
row in the table — 825ms in a real production trace. Real production
volume is 250k-1M ``data_entry_emissions`` rows (the lead, 2026-08-18) —
this test reproduces that order of magnitude locally.

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
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import emission_type_scope
from app.repositories.data_entry_repo import DataEntryRepository

pytestmark = pytest.mark.asyncio

# Two seeding rounds, 20x apart: 50k then 1,000,000 unrelated
# data_entry_emissions rows — the top of the real-world range (the lead,
# 2026-08-18), cheap enough to COPY-insert in a few seconds.
EMISSIONS_PER_BACKGROUND_ENTRY = 200
SMALL_BACKGROUND_ENTRIES = 250
LARGE_BACKGROUND_ENTRIES = 4_750  # seeded on top of the small round

# The assertion is *scaling invariance*, not a wall-clock budget: this
# query reads one pre-computed rollup row, so growing the rest of the
# table 20x must not grow its cost. An absolute budget cannot catch this
# bug locally — measured here, 1M rows costs 12.8ms fixed vs 73.6ms
# unfixed, both under any sane local budget. Dev's own round trip is
# 9-17x worse than local (2050 Track F0), which turns that 73.6ms into
# the ~825ms the production trace actually showed.
MAX_SCALING_FACTOR = 3.0

# The org-wide GET budget (2161-ceiling-scale-perf-fixtures.md). Kept as a
# secondary assertion so the number stays documented and enforced, but it
# is the ratio above that discriminates fixed from unfixed.
BUDGET_MS = 200


@pytest_asyncio.fixture
async def psycopg_session(pg_dsn):
    """AsyncSession on the production driver (psycopg3) — mirrors
    ``test_bulk_copy_pg.py``'s fixture of the same name.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_background_load(pg_dsn: str, module_id: int, entries: int) -> None:
    """Bulk-COPY ``entries * EMISSIONS_PER_BACKGROUND_ENTRY`` rows into
    ``data_entry_emissions``, attached to *their own* entries in
    ``module_id`` (not the module under test) — models the real,
    already-existing ~250k-1M row table the buggy aggregation scanned in
    full regardless of which module the request actually asked for.

    Raw asyncpg COPY, not the ORM — 300k individual ``session.add()``s
    would dominate this test's own runtime and defeat the point (see
    2050's own C2/C3 findings on why bulk paths never do that).
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
            entry_rows = [
                (DataEntryTypeEnum.member.value, module_id, "{}", 1)
                for _ in range(entries)
            ]
            await conn.copy_records_to_table("tmp_bg_entries", records=entry_rows)
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
            emission_rows = [
                (entry_id, EmissionType.food.value, 1.0)
                for entry_id in entry_ids
                for _ in range(EMISSIONS_PER_BACKGROUND_ENTRY)
            ]
            await conn.copy_records_to_table("tmp_bg_emissions", records=emission_rows)
            await conn.execute(
                "INSERT INTO data_entry_emissions (data_entry_id, "
                "emission_type_id, kg_co2eq, computed_at) "
                "SELECT data_entry_id, emission_type_id, kg_co2eq, NOW() "
                "FROM tmp_bg_emissions"
            )
    finally:
        await conn.close()


async def test_planner_headcount_submodule_get_ignores_table_wide_emission_volume(
    pg_dsn,
    psycopg_session,
    make_unit,
    make_carbon_report,
    make_carbon_report_module,
):
    unit = await make_unit(psycopg_session)
    report = await make_carbon_report(psycopg_session, unit_id=unit.id, year=2026)
    # Distinct module_type_id: one module per (carbon_report_id,
    # module_type_id) is a real unique constraint (uq_carbon_report_module).
    background_module = await make_carbon_report_module(
        psycopg_session, carbon_report_id=report.id, module_type_id=2
    )
    target_module = await make_carbon_report_module(
        psycopg_session, carbon_report_id=report.id, module_type_id=1
    )
    await psycopg_session.commit()

    await _seed_background_load(pg_dsn, background_module.id, SMALL_BACKGROUND_ENTRIES)

    # One real planner_headcount entry in the module actually under test.
    entry = DataEntry(
        carbon_report_module_id=target_module.id,
        data_entry_type_id=DataEntryTypeEnum.planner_headcount,
        status=DataEntryStatusEnum.VALIDATED,
        data={"sius_code": "51", "fte": 2.0},
    )
    psycopg_session.add(entry)
    await psycopg_session.flush()
    # Real shape: prepare_create writes the individual leaves *and* the
    # scope=None rollup row (see registry.py's DATA_ENTRY_TYPE_TO_ROLLUP_
    # EMISSION) — a rollup-only entry, as an earlier draft of this test had,
    # isn't what production data looks like and let the old buggy path's
    # "NOT IN rollup types" filter mask the bug as a NULL total instead of
    # a slow-but-plausible one.
    psycopg_session.add_all(
        [
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.food.value,
                kg_co2eq=10.0,
                scope=emission_type_scope(EmissionType.food),
            ),
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.waste.value,
                kg_co2eq=5.0,
                scope=emission_type_scope(EmissionType.waste),
            ),
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.commuting.value,
                kg_co2eq=3.0,
                scope=emission_type_scope(EmissionType.commuting),
            ),
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.headcount.value,
                kg_co2eq=18.0,
                scope=None,
            ),
        ]
    )
    await psycopg_session.commit()

    repo = DataEntryRepository(psycopg_session)

    async def timed_get() -> tuple[float, object]:
        start = time.perf_counter()
        result = await repo.get_submodule_data(
            carbon_report_module_id=target_module.id,
            data_entry_type_id=DataEntryTypeEnum.planner_headcount.value,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )
        return (time.perf_counter() - start) * 1000, result

    # Warm-up: the first call pays SQLAlchemy statement compilation and
    # connection setup, which would otherwise land entirely in the small
    # baseline and hide the very scaling this test measures.
    await timed_get()
    small_ms, response = await timed_get()

    assert len(response.items) == 1
    assert response.items[0].kg_co2eq == pytest.approx(18.0)

    await _seed_background_load(pg_dsn, background_module.id, LARGE_BACKGROUND_ENTRIES)
    large_ms, response = await timed_get()

    small_rows = SMALL_BACKGROUND_ENTRIES * EMISSIONS_PER_BACKGROUND_ENTRY
    large_rows = (
        SMALL_BACKGROUND_ENTRIES + LARGE_BACKGROUND_ENTRIES
    ) * EMISSIONS_PER_BACKGROUND_ENTRY
    print(
        f"\n>>> {small_rows} rows: {small_ms:.1f}ms | "
        f"{large_rows} rows: {large_ms:.1f}ms "
        f"(x{large_ms / small_ms:.1f})\n"
    )

    assert response.items[0].kg_co2eq == pytest.approx(18.0)
    assert large_ms < small_ms * MAX_SCALING_FACTOR, (
        f"{small_ms:.1f}ms at {small_rows} rows -> {large_ms:.1f}ms at "
        f"{large_rows} rows (x{large_ms / small_ms:.1f}): this query reads "
        f"one pre-computed rollup row, so it must not scale with the size "
        f"of the whole data_entry_emissions table. It is falling through to "
        f"the unfiltered GROUP BY aggregation (#2050 Track H)."
    )
    assert large_ms < BUDGET_MS, (
        f"{large_ms:.1f}ms exceeds the {BUDGET_MS}ms budget with "
        f"{large_rows} data_entry_emissions rows in the table."
    )
