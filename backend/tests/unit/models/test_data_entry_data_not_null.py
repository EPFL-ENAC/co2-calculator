"""#2527 C1: a data entry may not carry a NULL ``data`` blob.

The prefill's server-side copy (``copy_module_entries``) builds the target
``data`` in SQL. The Python shape it replaced raised on a NULL source blob —
``{**None}`` is a ``TypeError`` — so the job failed loudly and nothing was
written. SQL propagates instead: ``NULL || jsonb_build_object(...)`` is NULL.
The copy would then succeed, the row would land with ``data = NULL``, and the
only complaint would come later from ``_recalculate_report_emissions``, which
catches per-entry exceptions and continues. The job reports success while
those entries price nothing — the same silent shape as #2546.

The fix is the constraint rather than a guard in the copy, because the copy is
not the only raw-SQL writer: ``_DATA_ENTRY_COPY_SQL`` and the seeds also
bypass ``default_factory=default_dict``. A guard in one caller leaves the
others. A constraint cannot be forgotten by a caller that does not exist yet.

Only raw SQL can reach the state being forbidden, and that is not a gap in
the tests — it is the shape of the bug. SQLAlchemy's ``JSON`` type defaults to
``none_as_null=False``, so an ORM write of ``data=None`` stores the *JSON*
value ``null``, which is not SQL NULL and never was the problem (the copy's
``'null'::jsonb || …`` raises on its own). SQL NULL arrives only from a writer
that bypasses the ORM — the copy above, ``_DATA_ENTRY_COPY_SQL``, the seeds —
which is exactly why a guard in one caller would not have been enough.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import text

from app.models.data_entry import DataEntry, DataEntryTypeEnum

pytestmark = pytest.mark.asyncio

CONSTRAINT_NAME = "ck_data_entries_data_not_null"

_RAW_INSERT = text(
    "INSERT INTO data_entries "
    "(data_entry_type_id, carbon_report_module_id, data, created_at, updated_at) "
    "VALUES (:det, :module, :data, :now, :now)"
)


async def test_a_raw_sql_null_data_blob_is_rejected(
    db_session, make_unit, make_carbon_report, make_carbon_report_module
):
    """The regression: before the constraint this INSERT succeeded silently.

    Raw SQL, because that is the only writer that can produce a SQL NULL
    here — and it is the shape ``copy_module_entries`` emits when a source
    blob is NULL.
    """
    unit = await make_unit(db_session)
    report = await make_carbon_report(db_session, unit_id=unit.id, year=2026)
    module = await make_carbon_report_module(
        db_session, carbon_report_id=report.id, module_type_id=1
    )
    params = {
        "det": DataEntryTypeEnum.process_emissions.value,
        "module": module.id,
        "data": None,
        "now": datetime.now(UTC).replace(tzinfo=None),
    }

    with pytest.raises(IntegrityError):
        await db_session.execute(_RAW_INSERT, params)
        await db_session.flush()


async def test_an_empty_dict_is_still_allowed(
    db_session, make_unit, make_carbon_report, make_carbon_report_module
):
    """``{}`` is not NULL.

    The constraint must not be read as "data must be non-empty" — an entry
    can legitimately carry no keys yet, and tightening that would break the
    create-then-fill flow. Only the NULL is forbidden.
    """
    unit = await make_unit(db_session)
    report = await make_carbon_report(db_session, unit_id=unit.id, year=2026)
    module = await make_carbon_report_module(
        db_session, carbon_report_id=report.id, module_type_id=1
    )

    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        carbon_report_module_id=module.id,
        data={},
    )
    db_session.add(entry)
    await db_session.flush()

    assert entry.id is not None


async def test_the_constraint_is_declared_on_the_model(db_session):
    """Pins the name, so the migration and the model cannot drift apart.

    The migration adds this constraint by hand (``NOT VALID``, to avoid the
    full-table validation scan a plain ``CREATE ... CHECK`` performs under
    ACCESS EXCLUSIVE). Autogenerate matches an existing constraint *by name*;
    if the model's name ever stops matching the migration's, the next
    autogenerate silently proposes creating it a second time — as a
    validating one, on a table with millions of rows.
    """
    names = {c.name for c in DataEntry.__table__.constraints}
    assert CONSTRAINT_NAME in names

    rows = await db_session.execute(
        text("SELECT sql FROM sqlite_master WHERE name = 'data_entries'")
    )
    ddl = rows.scalar_one()
    assert CONSTRAINT_NAME in ddl, "constraint declared but not emitted in DDL"
