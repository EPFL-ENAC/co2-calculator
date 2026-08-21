"""Integration tests: equipment new vs the previous year (issue #259).

An equipment entry is "new" when its ``equipment_id`` did not exist in the
unit's most recent prior year with equipment data. New entries are flagged
(``is_new``), floated to the top of the listing, and — while still missing
usage data — block module validation.

Behaviours pinned here (all at the repository layer, like ``test_sort.py``):

1. ``test_new_equipment_flagged_and_sorted_first`` — an equipment_id absent
   from the prior year is flagged ``is_new`` and sorts ahead of an existing
   one, overriding the user's secondary sort.
2. ``test_first_year_flags_nothing`` — a unit with no earlier equipment data
   flags nothing new and reports a zero incomplete count.
3. ``test_count_incomplete_new_equipment`` — the count reflects only new
   equipment still missing active/standby usage, and drops to zero once the
   usage is filled.
4. ``test_prior_year_usage_map_partial_fields`` — the carry-forward lookup
   returns only the usage fields the prior year actually set.
5. ``test_apply_equipment_carry_forward`` — per-field merge: prior-year values
   win over ingested ones, unset prior fields and unmatched equipment are left
   untouched. (The factor → 12/156 formula fallback is pinned in
   ``tests/unit/modules/test_equipment_schemas.py``.)
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository
from app.services.data_entry_service import DataEntryService

UNIT_ID = 1


async def _seed_module(session: AsyncSession, year: int) -> CarbonReportModule:
    """Seed a CarbonReport + equipment CarbonReportModule for ``year``."""
    report = CarbonReport(year=year, unit_id=UNIT_ID, overall_status=0)
    session.add(report)
    await session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
        status=ModuleStatus.NOT_STARTED,
    )
    session.add(module)
    await session.flush()
    return module


async def _seed_entry(
    session: AsyncSession,
    module: CarbonReportModule,
    *,
    year: int,
    equipment_id: str,
    with_usage: bool = True,
    active_usage: int | None = None,
    standby_usage: int | None = None,
    stamp_ingest: bool = False,
) -> DataEntry:
    """Seed one scientific equipment entry with its denormalized unit/year.

    ``get_prior_year_equipment_ids`` and ``_equipment_module_scope`` read the
    denormalized ``unit_id``/``year`` off the entry, so both must be set.
    ``active_usage``/``standby_usage`` override the ``with_usage`` pair to
    seed a single field.
    """
    data: dict = {
        "name": f"eq-{equipment_id}",
        "equipment_id": equipment_id,
        "equipment_class": "microscope",
    }
    if with_usage:
        data["active_usage_hours_per_week"] = 12
        data["standby_usage_hours_per_week"] = 150
    if active_usage is not None:
        data["active_usage_hours_per_week"] = active_usage
    if standby_usage is not None:
        data["standby_usage_hours_per_week"] = standby_usage
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        status=DataEntryStatusEnum.PENDING,
        data=data,
        unit_id=UNIT_ID,
        year=year,
    )
    if stamp_ingest:
        # #2050 J10: is_new is decided when a CSV lands, not on every read, so
        # a test that wants a flagged row has to arrive the way a CSV does.
        await DataEntryService(session).apply_equipment_carry_forward([entry])
    session.add(entry)
    await session.flush()
    return entry


@pytest.mark.asyncio
async def test_new_equipment_flagged_and_sorted_first(db_session: AsyncSession):
    """The equipment_id absent from the prior year is flagged and floats up.

    Prior year (2024) has {E1, E2}. Current year (2025) has E1 (existing) and
    E3 (new, still missing usage). Sorting by name ascending would place
    ``eq-E1`` before ``eq-E3``; the new-and-incomplete primary sort must
    override that so E3 comes back first.
    """
    repo = DataEntryRepository(db_session)

    prev_module = await _seed_module(db_session, 2024)
    for eid in ("E1", "E2"):
        await _seed_entry(db_session, prev_module, year=2024, equipment_id=eid)

    cur_module = await _seed_module(db_session, 2025)
    await _seed_entry(
        db_session, cur_module, year=2025, equipment_id="E1", stamp_ingest=True
    )
    await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E3",
        with_usage=False,
        stamp_ingest=True,
    )
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=cur_module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="name",
        sort_order="asc",
    )

    by_name = {item.name: item.is_new for item in result.items}  # type: ignore[attr-defined]
    assert by_name == {"eq-E1": False, "eq-E3": True}
    assert result.items[0].name == "eq-E3", (  # type: ignore[attr-defined]
        "new equipment still missing its usage hours must float to the top, "
        "above the user's name sort"
    )


@pytest.mark.asyncio
async def test_first_year_flags_nothing(db_session: AsyncSession):
    """A unit with no earlier equipment data flags nothing new."""
    repo = DataEntryRepository(db_session)

    cur_module = await _seed_module(db_session, 2025)
    await _seed_entry(db_session, cur_module, year=2025, equipment_id="E1")
    await _seed_entry(db_session, cur_module, year=2025, equipment_id="E2")
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=cur_module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="name",
        sort_order="asc",
    )

    assert all(item.is_new is False for item in result.items)  # type: ignore[attr-defined]
    assert await repo.count_incomplete_new_equipment(cur_module.id) == 0


@pytest.mark.asyncio
async def test_count_incomplete_new_equipment(db_session: AsyncSession):
    """Only new equipment missing usage is counted; filling usage clears it."""
    repo = DataEntryRepository(db_session)

    prev_module = await _seed_module(db_session, 2024)
    await _seed_entry(db_session, prev_module, year=2024, equipment_id="E1")

    cur_module = await _seed_module(db_session, 2025)
    # Existing equipment missing usage must NOT count (only new equipment does).
    await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E1",
        with_usage=False,
        stamp_ingest=True,
    )
    # New equipment missing usage → counts.
    new_incomplete = await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E3",
        with_usage=False,
        stamp_ingest=True,
    )
    await db_session.commit()

    assert await repo.count_incomplete_new_equipment(cur_module.id) == 1

    new_incomplete.data = {
        **new_incomplete.data,
        "active_usage_hours_per_week": 8,
        "standby_usage_hours_per_week": 40,
    }
    db_session.add(new_incomplete)
    await db_session.commit()

    assert await repo.count_incomplete_new_equipment(cur_module.id) == 0


@pytest.mark.asyncio
async def test_prior_year_usage_map_partial_fields(db_session: AsyncSession):
    """The lookup returns only the usage fields each prior row actually set."""
    repo = DataEntryRepository(db_session)

    prev_module = await _seed_module(db_session, 2024)
    await _seed_entry(
        db_session,
        prev_module,
        year=2024,
        equipment_id="E1",
        with_usage=False,
        active_usage=10,
        standby_usage=100,
    )
    await _seed_entry(
        db_session,
        prev_module,
        year=2024,
        equipment_id="E2",
        with_usage=False,
        active_usage=8,
    )
    await _seed_entry(
        db_session, prev_module, year=2024, equipment_id="E3", with_usage=False
    )
    await db_session.commit()

    assert await repo.get_prior_year_equipment_usage(UNIT_ID, 2025) == {
        "E1": {
            "active_usage_hours_per_week": 10,
            "standby_usage_hours_per_week": 100,
        },
        "E2": {"active_usage_hours_per_week": 8},
    }
    assert await repo.get_prior_year_equipment_usage(UNIT_ID, 2024) == {}


@pytest.mark.asyncio
async def test_apply_equipment_carry_forward(db_session: AsyncSession):
    """Per-field merge: prior-year values win over the ingested file's ones,
    fields the prior year left unset stay as ingested, unmatched equipment is
    untouched. Entries arrive like the ingest batch: no unit/year stamped.
    """
    prev_module = await _seed_module(db_session, 2024)
    await _seed_entry(
        db_session,
        prev_module,
        year=2024,
        equipment_id="E1",
        with_usage=False,
        active_usage=10,
        standby_usage=100,
    )
    await _seed_entry(
        db_session,
        prev_module,
        year=2024,
        equipment_id="E2",
        with_usage=False,
        active_usage=8,
    )
    cur_module = await _seed_module(db_session, 2025)
    await db_session.commit()

    def _batch_entry(equipment_id: str, **usage: int) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=cur_module.id,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            data={
                "name": f"eq-{equipment_id}",
                "equipment_id": equipment_id,
                "equipment_class": "microscope",
                **usage,
            },
        )

    matched = _batch_entry(
        "E1", active_usage_hours_per_week=1, standby_usage_hours_per_week=2
    )
    partial = _batch_entry("E2", standby_usage_hours_per_week=40)
    unmatched = _batch_entry("E9", active_usage_hours_per_week=3)

    service = DataEntryService(db_session)
    await service.apply_equipment_carry_forward([matched, partial, unmatched])

    assert matched.data["active_usage_hours_per_week"] == 10
    assert matched.data["standby_usage_hours_per_week"] == 100
    assert partial.data["active_usage_hours_per_week"] == 8
    assert partial.data["standby_usage_hours_per_week"] == 40
    assert unmatched.data["active_usage_hours_per_week"] == 3
    assert "standby_usage_hours_per_week" not in unmatched.data
    assert (matched.unit_id, matched.year) == (UNIT_ID, 2025)


# ---------------------------------------------------------------------------
# #2050 J10 — is_new is stamped at CSV ingest, not derived on every read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carry_forward_stamps_is_new_at_ingest(db_session: AsyncSession):
    """``is_new`` is decided once, when the CSV lands, and stored on the row.

    It used to be recomputed on every page load, which meant loading every
    equipment_id in the unit's prior year to answer it for 20 rows — 1711ms on
    dev for one page. The prior-year lookup this needs is already cached per
    (unit, year) by the carry-forward, so stamping costs nothing extra.
    """
    prior_module = await _seed_module(db_session, 2024)
    module = await _seed_module(db_session, 2025)

    db_session.add_all(
        [
            # Present last year *with* usage — carried forward and not new.
            DataEntry(
                carbon_report_module_id=prior_module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.VALIDATED,
                unit_id=UNIT_ID,
                year=2024,
                data={
                    "name": "Kept",
                    "equipment_id": "EQ-KEPT",
                    "equipment_class": "laptop",
                    "active_usage_hours_per_week": 30,
                },
            ),
            # Present last year with *no* usage fields at all. The carry-forward
            # usage map drops these rows, so it cannot double as the id set —
            # this entry must still count as not-new.
            DataEntry(
                carbon_report_module_id=prior_module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.VALIDATED,
                unit_id=UNIT_ID,
                year=2024,
                data={
                    "name": "Bare",
                    "equipment_id": "EQ-BARE",
                    "equipment_class": "laptop",
                },
            ),
        ]
    )
    await db_session.flush()

    incoming = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it,
            status=DataEntryStatusEnum.VALIDATED,
            unit_id=UNIT_ID,
            year=2025,
            data={
                "name": name,
                "equipment_id": equipment_id,
                "equipment_class": "laptop",
            },
        )
        for name, equipment_id in (
            ("Kept", "EQ-KEPT"),
            ("Bare", "EQ-BARE"),
            ("Brand new", "EQ-NEW"),
        )
    ]

    await DataEntryService(db_session).apply_equipment_carry_forward(incoming)

    stamped = {e.data["equipment_id"]: e.data.get("is_new") for e in incoming}
    assert stamped == {"EQ-KEPT": False, "EQ-BARE": False, "EQ-NEW": True}


@pytest.mark.asyncio
async def test_first_year_ingest_stamps_nothing_new(db_session: AsyncSession):
    """A unit's first campaign year has no prior data, so nothing is new —
    the same rule the read-time version applied.
    """
    module = await _seed_module(db_session, 2025)
    incoming = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it,
            status=DataEntryStatusEnum.VALIDATED,
            unit_id=UNIT_ID,
            year=2025,
            data={
                "name": "First",
                "equipment_id": "EQ-FIRST",
                "equipment_class": "laptop",
            },
        )
    ]

    await DataEntryService(db_session).apply_equipment_carry_forward(incoming)

    assert incoming[0].data.get("is_new") is False


@pytest.mark.asyncio
async def test_incomplete_new_count_reads_the_stored_flag(db_session: AsyncSession):
    """#2050 J11: the incomplete-new count reads ``is_new`` off the row.

    It used to re-derive it the same way the page did — load every
    ``equipment_id`` in the unit's prior year, then inline the set as
    ``NOT IN (...)`` — and it runs on *every* module GET, not just the
    equipment page.
    """
    repo = DataEntryRepository(db_session)
    prev_module = await _seed_module(db_session, 2024)
    await _seed_entry(db_session, prev_module, year=2024, equipment_id="E1")

    cur_module = await _seed_module(db_session, 2025)
    # New and missing usage — counted.
    await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E9",
        with_usage=False,
        stamp_ingest=True,
    )
    # New but complete — not counted.
    await _seed_entry(
        db_session, cur_module, year=2025, equipment_id="E8", stamp_ingest=True
    )
    # Existing and missing usage — not counted, it is not new.
    await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E1",
        with_usage=False,
        stamp_ingest=True,
    )
    await db_session.commit()

    assert await repo.count_incomplete_new_equipment(cur_module.id) == 1


@pytest.mark.asyncio
async def test_incomplete_new_count_issues_no_prior_year_query(
    db_session: AsyncSession,
):
    """The absence is the contract: counting must not touch the unit's history."""
    from sqlalchemy import event

    repo = DataEntryRepository(db_session)
    prev_module = await _seed_module(db_session, 2024)
    await _seed_entry(db_session, prev_module, year=2024, equipment_id="E1")
    cur_module = await _seed_module(db_session, 2025)
    await _seed_entry(
        db_session,
        cur_module,
        year=2025,
        equipment_id="E9",
        with_usage=False,
        stamp_ingest=True,
    )
    await db_session.commit()

    statements: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", listener)
    try:
        await repo.count_incomplete_new_equipment(cur_module.id)
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    prior_reads = [s for s in statements if "max(data_entries.year)" in s]
    assert not prior_reads, (
        f"the count queried the unit's prior year (#2050 J11):\n{prior_reads}"
    )
