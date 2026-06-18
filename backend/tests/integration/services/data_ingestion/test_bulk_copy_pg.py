"""COPY-based bulk insert for data_entries (bulk ingest performance).

The repository's ``bulk_copy`` streams rows through PostgreSQL
``COPY … FROM STDIN`` on the session's own connection.  The COPY path
is psycopg3-specific, so these tests build a ``postgresql+psycopg``
engine from the same container DSN the asyncpg fixtures use.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="function")
async def psycopg_session(pg_dsn):
    """AsyncSession on the production driver (psycopg3) so COPY runs."""
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_module(
    session, make_unit, make_carbon_report, make_carbon_report_module
):
    unit = await make_unit(session)
    report = await make_carbon_report(session, unit_id=unit.id, year=2026)
    module = await make_carbon_report_module(
        session, carbon_report_id=report.id, module_type_id=1
    )
    await session.commit()
    return module


def _entries(module_id: int, n: int) -> list[DataEntry]:
    return [
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module_id,
            data={"name": f"row-{i}", "fte": 0.5, "note": 'tricky\t"chars"\n'},
            status=DataEntryStatusEnum.PENDING,
        )
        for i in range(n)
    ]


async def test_bulk_copy_inserts_rows_with_intact_payloads(
    psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    module = await _seed_module(
        psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
    )
    repo = DataEntryRepository(psycopg_session)

    count = await repo.bulk_copy(_entries(module.id, 250))
    await psycopg_session.commit()

    assert count == 250
    rows = (
        (
            await psycopg_session.execute(
                select(DataEntry).where(
                    col(DataEntry.carbon_report_module_id) == module.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 250
    sample = next(r for r in rows if r.data["name"] == "row-0")
    # JSON payload survives COPY encoding, including tabs/quotes/newlines.
    assert sample.data["note"] == 'tricky\t"chars"\n'
    assert sample.status == DataEntryStatusEnum.PENDING
    assert sample.id is not None  # sequence-assigned server-side
    assert sample.created_at is not None


async def test_bulk_copy_rolls_back_with_session_transaction(
    psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    """COPY runs on the session's connection — a rollback discards it."""
    module = await _seed_module(
        psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
    )
    repo = DataEntryRepository(psycopg_session)
    # Capture before rollback() — it expires ORM instances, and a lazy
    # attribute refresh outside the greenlet context raises MissingGreenlet.
    module_id = module.id

    await repo.bulk_copy(_entries(module_id, 10))
    await psycopg_session.rollback()

    remaining = (
        await psycopg_session.execute(
            select(func.count())
            .select_from(DataEntry)
            .where(col(DataEntry.carbon_report_module_id) == module_id)
        )
    ).scalar_one()
    assert remaining == 0


async def test_bulk_copy_empty_batch_is_noop(psycopg_session):
    repo = DataEntryRepository(psycopg_session)
    assert await repo.bulk_copy([]) == 0


async def test_year_delete_replaces_only_matching_source_and_year(
    psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    """Full-year replace contract: ``bulk_delete_by_source_year`` removes
    rows matching (year, type, source) via the denormalized ``year``
    column, leaving other sources and other years untouched."""
    from app.models.data_entry import DataEntrySourceEnum

    module = await _seed_module(
        psycopg_session, make_unit, make_carbon_report, make_carbon_report_module
    )
    module_id = module.id
    repo = DataEntryRepository(psycopg_session)

    def _entry(year, source):
        return DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module_id,
            data={"name": "x"},
            year=year,
            source=source,
        )

    await repo.bulk_copy(
        [
            _entry(2026, DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value),
            _entry(2026, DataEntrySourceEnum.USER_MANUAL.value),
            _entry(2025, DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value),
        ]
    )
    await psycopg_session.commit()

    deleted = await repo.bulk_delete_by_source_year(
        year=2026,
        data_entry_type_ids=[DataEntryTypeEnum.member.value],
        source=DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value,
    )
    await psycopg_session.commit()
    psycopg_session.expire_all()

    assert deleted == 1
    rows = (
        (
            await psycopg_session.execute(
                select(DataEntry).where(
                    col(DataEntry.carbon_report_module_id) == module_id
                )
            )
        )
        .scalars()
        .all()
    )
    survivors = {(r.year, r.source) for r in rows}
    assert survivors == {
        (2026, DataEntrySourceEnum.USER_MANUAL.value),
        (2025, DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value),
    }
