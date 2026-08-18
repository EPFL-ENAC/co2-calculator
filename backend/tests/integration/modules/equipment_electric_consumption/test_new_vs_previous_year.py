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
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository

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
) -> DataEntry:
    """Seed one scientific equipment entry with its denormalized unit/year.

    ``get_prior_year_equipment_ids`` and ``_equipment_module_scope`` read the
    denormalized ``unit_id``/``year`` off the entry, so both must be set.
    """
    data: dict = {
        "name": f"eq-{equipment_id}",
        "equipment_id": equipment_id,
        "equipment_class": "microscope",
    }
    if with_usage:
        data["active_usage_hours_per_week"] = 12
        data["standby_usage_hours_per_week"] = 150
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        status=DataEntryStatusEnum.PENDING,
        data=data,
        unit_id=UNIT_ID,
        year=year,
    )
    session.add(entry)
    await session.flush()
    return entry


@pytest.mark.asyncio
async def test_new_equipment_flagged_and_sorted_first(db_session: AsyncSession):
    """The equipment_id absent from the prior year is flagged and floats up.

    Prior year (2024) has {E1, E2}. Current year (2025) has E1 (existing) and
    E3 (new). Sorting by name ascending would place ``eq-E1`` before ``eq-E3``;
    the new-first primary sort must override that so E3 comes back first.
    """
    repo = DataEntryRepository(db_session)

    prev_module = await _seed_module(db_session, 2024)
    for eid in ("E1", "E2"):
        await _seed_entry(db_session, prev_module, year=2024, equipment_id=eid)

    cur_module = await _seed_module(db_session, 2025)
    await _seed_entry(db_session, cur_module, year=2025, equipment_id="E1")
    # New *and* missing usage hours: the float-to-top rule is
    # ``desc(and_(is_new, missing_usage))`` (#259 surfaces rows that need the
    # user's attention), not "new" on its own — a new row already filled in
    # sorts normally.
    await _seed_entry(
        db_session, cur_module, year=2025, equipment_id="E3", with_usage=False
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
        db_session, cur_module, year=2025, equipment_id="E1", with_usage=False
    )
    # New equipment missing usage → counts.
    new_incomplete = await _seed_entry(
        db_session, cur_module, year=2025, equipment_id="E3", with_usage=False
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
