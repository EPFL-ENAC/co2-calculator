"""The equipment submodule GET at realistic prior-year scale (#2050 J10).

Observed on dev, 2026-08-19, trace ``42a83f``:
``GET /carbon-reports/11604/modules/equipment/it?limit=20`` took **1711.6ms**
to return 20 rows. Its shape:

```
   25.6 +612.4ms  SELECT DISTINCT data->>'equipment_id'   (prior-year id set)
  638.0 +575.1ms  <no span at all>
 1213.1 +472.8ms  the page query
 1687.4 +  3.1ms  count(*)
```

The 575ms of silence is the tell. ``get_prior_year_equipment_ids`` returns a
Python ``set`` of every equipment id in the unit's prior year — up to 3,000 by
the #2161 ceilings — and that set is inlined into the page query as
``NOT IN (:p1, :p2, ... :p3000)``. Compiling a statement with thousands of
bind parameters is pure Python, so no DB span covers it; executing it then
costs again on the server.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import time
from datetime import UTC, datetime

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository

pytestmark = pytest.mark.asyncio

YEAR = 2025
PRIOR_YEAR = 2024
# The #2161 ceiling for equipment is 3,000 per unit-year. This is the size of
# the set that ends up inlined as bind parameters.
PRIOR_YEAR_EQUIPMENT = 50_000
PAGE_LIMIT = 20
_NOW = datetime.now(UTC).replace(tzinfo=None)

# One page of 20 rows. Everything here is indexed or bounded, so this is
# generous rather than tight — the broken shape lands far above it.
BUDGET_MS = 250.0


@pytest_asyncio.fixture
async def psycopg_session(pg_dsn):
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_prior_year_equipment(
    pg_dsn: str, module_id: int, unit_id: int, count: int
) -> None:
    """COPY ``count`` prior-year equipment entries for this unit."""
    dsn = pg_dsn.replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.copy_records_to_table(
            "data_entries",
            columns=[
                "data_entry_type_id",
                "carbon_report_module_id",
                "data",
                "status",
                "year",
                "unit_id",
                "created_at",
                "updated_at",
            ],
            records=[
                (
                    DataEntryTypeEnum.it.value,
                    module_id,
                    f'{{"name": "Laptop {i}", "equipment_id": "EQ-{i:05d}", '
                    f'"equipment_class": "laptop"}}',
                    "VALIDATED",
                    PRIOR_YEAR,
                    unit_id,
                    _NOW,
                    _NOW,
                )
                for i in range(count)
            ],
        )
    finally:
        await conn.close()


async def test_equipment_page_does_not_pay_for_the_prior_year_set(
    pg_dsn,
    psycopg_session,
    make_unit,
    make_carbon_report,
    make_carbon_report_module,
):
    unit = await make_unit(psycopg_session)
    prior_report = await make_carbon_report(
        psycopg_session, unit_id=unit.id, year=PRIOR_YEAR
    )
    prior_module = await make_carbon_report_module(
        psycopg_session,
        carbon_report_id=prior_report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
    )
    report = await make_carbon_report(
        psycopg_session,
        unit_id=unit.id,
        year=YEAR,
        carbon_project_id=prior_report.carbon_project_id,
    )
    module = await make_carbon_report_module(
        psycopg_session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
    )
    await psycopg_session.commit()

    await _seed_prior_year_equipment(
        pg_dsn, prior_module.id, unit.id, PRIOR_YEAR_EQUIPMENT
    )

    # This year's page: a normal 20-row page.
    for i in range(PAGE_LIMIT):
        psycopg_session.add(
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.VALIDATED,
                year=YEAR,
                unit_id=unit.id,
                data={
                    "name": f"Laptop {i}",
                    "equipment_id": f"EQ-{i:05d}",
                    "equipment_class": "laptop",
                },
            )
        )
    await psycopg_session.commit()

    repo = DataEntryRepository(psycopg_session)

    async def timed() -> tuple[float, object]:
        start = time.perf_counter()
        result = await repo.get_submodule_data(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            limit=PAGE_LIMIT,
            offset=0,
            sort_by="id",
            sort_order="desc",
        )
        return (time.perf_counter() - start) * 1000, result

    await timed()  # warm-up: statement compilation is the thing under test
    elapsed_ms, response = await timed()
    print(
        f"\n>>> equipment page with {PRIOR_YEAR_EQUIPMENT} prior-year ids: "
        f"{elapsed_ms:.1f}ms\n"
    )

    assert len(response.items) == PAGE_LIMIT
    # Behaviour must not change: these ids all exist in the prior year.
    assert all(item.is_new is False for item in response.items)

    assert elapsed_ms < BUDGET_MS, (
        f"{elapsed_ms:.1f}ms to return {PAGE_LIMIT} rows, budget {BUDGET_MS}ms. "
        f"The prior-year equipment id set ({PRIOR_YEAR_EQUIPMENT} values) is "
        f"being inlined into the page query as bind parameters (#2050 J10)."
    )


async def test_the_page_never_reads_prior_year_data(
    pg_dsn,
    psycopg_session,
    make_unit,
    make_carbon_report,
    make_carbon_report_module,
):
    """The read path returns the stored flag and issues no prior-year query.

    #2050 J10 moved ``is_new`` to ingest. The contract this pins is not the
    timing but the absence: rendering a page must not look at the unit's
    history at all, which is what made the endpoint scale with it. The
    ingest-time stamping itself is pinned in
    ``tests/integration/modules/equipment_electric_consumption/``.
    """
    unit = await make_unit(psycopg_session)
    report = await make_carbon_report(psycopg_session, unit_id=unit.id, year=YEAR)
    module = await make_carbon_report_module(
        psycopg_session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
    )
    await psycopg_session.commit()

    for name, stored_is_new in (("Kept", False), ("Fresh", True)):
        psycopg_session.add(
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.VALIDATED,
                year=YEAR,
                unit_id=unit.id,
                data={
                    "name": name,
                    "equipment_id": f"EQ-{name}",
                    "equipment_class": "laptop",
                    "is_new": stored_is_new,
                },
            )
        )
    await psycopg_session.commit()

    statements: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = psycopg_session.get_bind()
    event.listen(engine, "before_cursor_execute", listener)
    try:
        result = await DataEntryRepository(psycopg_session).get_submodule_data(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            limit=PAGE_LIMIT,
            offset=0,
            sort_by="name",
            sort_order="asc",
        )
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    assert {item.name: item.is_new for item in result.items} == {
        "Kept": False,
        "Fresh": True,
    }
    # New-and-incomplete still sorts first, now off the stored flag.
    assert result.items[0].name == "Fresh"

    prior_year_reads = [
        statement
        for statement in statements
        if "max(data_entries.year)" in statement
        or ("equipment_id" in statement and "DISTINCT" in statement.upper())
    ]
    assert not prior_year_reads, (
        "the page queried the unit's prior year; is_new is stored at ingest "
        f"and must be read off the row (#2050 J10):\n{prior_year_reads}"
    )
