"""``data_entries.data`` must be a non-empty JSON object (#2527 C1).

The unit suite pins the portable half of this on SQLite
(``tests/unit/models/test_data_entry_data_not_null.py``). The other two holes
need Postgres, because closing them needs ``json_typeof`` and a ``jsonb``
comparison:

* **JSON ``null``.** SQLAlchemy's ``JSON`` type defaults to
  ``none_as_null=False``, so an ORM write of ``data=None`` stores the JSON
  scalar ``null``, not SQL NULL. It reads back as Python ``None``, prices
  nothing, and sails past ``data IS NOT NULL``.
* **``{}``.** No handler can produce it — all 26 ``validate_create`` DTOs
  reject an empty payload, and every ``DataEntry(...)`` in the app passes real
  keys — so a row carrying it came from somewhere that skipped validation, and
  it prices nothing just like a NULL.

Both are the shape #2546 was: entries that exist, look fine in a listing, and
contribute zero to a published total. The constraints are ``NOT VALID``, so
they bind new writes without validating millions of existing rows under
ACCESS EXCLUSIVE — see the migration for the ``VALIDATE CONSTRAINT``
follow-up.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def seeded(pg_dsn, make_unit, make_carbon_report, make_carbon_report_module):
    """One module to hang entries off, plus a session factory."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        unit = await make_unit(session)
        report = await make_carbon_report(session, unit_id=unit.id, year=2026)
        module = await make_carbon_report_module(
            session,
            carbon_report_id=report.id,
            module_type_id=1,
        )
        await session.commit()
    yield factory, module.id, pg_dsn
    await engine.dispose()


async def _raw_insert(pg_dsn: str, module_id: int, data_literal: str) -> None:
    """INSERT one row with ``data`` set to a raw SQL literal.

    Raw asyncpg, because the point is to bypass every Python-side guard and
    hit the constraint itself — which is what an unvalidated writer does.
    """
    conn = await asyncpg.connect(pg_dsn.replace("postgresql+asyncpg", "postgresql"))
    try:
        await conn.execute(
            "INSERT INTO data_entries (data_entry_type_id, carbon_report_module_id, "
            f"data, created_at, updated_at) VALUES ($1, $2, {data_literal}, "
            "NOW(), NOW())",
            DataEntryTypeEnum.process_emissions.value,
            module_id,
        )
    finally:
        await conn.close()


@pytest.mark.parametrize(
    ("label", "literal"),
    [
        ("sql null", "NULL"),
        ("json null", "'null'::json"),
        ("empty object", "'{}'::json"),
        ("json array", "'[]'::json"),
        ("json scalar", "'42'::json"),
    ],
)
async def test_unreadable_data_blobs_are_rejected(seeded, label, literal):
    """Every shape that would price nothing must fail at the database."""
    _factory, module_id, pg_dsn = seeded

    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _raw_insert(pg_dsn, module_id, literal)


async def test_a_real_object_is_accepted(seeded):
    """The constraint must not be over-tight: one key is enough."""
    _factory, module_id, pg_dsn = seeded

    await _raw_insert(pg_dsn, module_id, '\'{"category": "co2"}\'::json')

    conn = await asyncpg.connect(pg_dsn.replace("postgresql+asyncpg", "postgresql"))
    try:
        n = await conn.fetchval(
            "SELECT count(*) FROM data_entries WHERE carbon_report_module_id = $1",
            module_id,
        )
    finally:
        await conn.close()
    assert n == 1


async def test_the_orm_none_write_is_rejected_too(seeded):
    """``DataEntry(data=None)`` is the reachable-from-Python version.

    Table models skip pydantic validation, so this reaches the database as the
    JSON scalar ``null`` rather than raising in Python — which is precisely
    why the constraint, not a Python guard, is the fix.
    """
    factory, module_id, _pg_dsn = seeded

    async with factory() as session:
        session.add(
            DataEntry(
                data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                carbon_report_module_id=module_id,
                data=None,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
