"""#2527: the kg_co2eq aggregate is scoped by the emission row's own keys.

``get_submodule_data`` used to restrict its emission aggregate with
``data_entry_id IN (SELECT id FROM data_entries WHERE module … AND type …)``.
It now filters on ``data_entry_emissions``' own denormalized
``carbon_report_module_id`` / ``data_entry_type_id`` so the aggregate rides
``ix_dee_module_type_entry`` instead of probing the emissions table row by
row.

The failure this guards is silent, not loud: a wrong predicate (or an
unstamped row) does not raise — it drops or adds rows and the page still
renders, with a total that merely looks plausible. So every case below seeds
**decoys**: another module holding the same entry type, and another type in
the same module. Neither may reach the totals.

All three ``kg_sort_expr`` branches are covered, because the rewrite touched
all three: the buildings COALESCE (leaf aggregate + rollup join), the
headcount rollup join, and the generic aggregate subquery. The headcount
response does not expose ``kg_co2eq``, so that branch is asserted through
the ordering its rollup join drives rather than through a total.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions.taxonomy import EmissionType
from app.repositories.data_entry_repo import DataEntryRepository
from tests.conftest import make_emission

pytestmark = pytest.mark.asyncio


async def _make_module(db_session: AsyncSession, module_type: ModuleTypeEnum) -> int:
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=module_type.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()
    if module.id is None:
        raise ValueError("module was not flushed")
    return module.id


async def _add_entry(
    db_session: AsyncSession,
    module_id: int,
    data_entry_type: DataEntryTypeEnum,
    data: dict,
    leaves: dict[EmissionType, float],
    rollup: tuple[EmissionType, float] | None = None,
) -> int:
    entry = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=data_entry_type.value,
        status=DataEntryStatusEnum.PENDING,
        data=data,
        year=2025,
    )
    db_session.add(entry)
    await db_session.flush()
    for emission_type, kg in leaves.items():
        db_session.add(
            make_emission(
                entry,
                emission_type_id=emission_type.value,
                kg_co2eq=kg,
                scope=3,
            )
        )
    if rollup is not None:
        rollup_type, rollup_kg = rollup
        db_session.add(
            make_emission(
                entry,
                emission_type_id=rollup_type.value,
                kg_co2eq=rollup_kg,
                scope=None,
                meta={"is_rollup": True},
            )
        )
    if entry.id is None:
        raise ValueError("entry was not flushed")
    return entry.id


async def _kg_sorted_page(
    db_session: AsyncSession, module_id: int, data_entry_type: DataEntryTypeEnum
) -> list:
    return (
        await DataEntryRepository(db_session).get_submodule_data(
            carbon_report_module_id=module_id,
            data_entry_type_id=data_entry_type.value,
            limit=50,
            offset=0,
            sort_by="kg_co2eq",
            sort_order="desc",
        )
    ).items


async def _kg_by_id(
    db_session: AsyncSession, module_id: int, data_entry_type: DataEntryTypeEnum
) -> dict[int, float | None]:
    """Totals keyed by entry id — the only key every entry type has."""
    items = await _kg_sorted_page(db_session, module_id, data_entry_type)
    return {item.id: item.kg_co2eq for item in items}


def _it_equipment_data(name: str) -> dict:
    return {
        "purchase_institutional_code": "A100",
        "name": name,
        "total_spent_amount": 100,
    }


async def test_generic_branch_totals_exclude_other_modules_and_types(
    db_session: AsyncSession,
):
    module_id = await _make_module(db_session, ModuleTypeEnum.purchase)
    decoy_module_id = await _make_module(db_session, ModuleTypeEnum.purchase)

    wanted_id = await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.it_equipment,
        _it_equipment_data("wanted"),
        {EmissionType.purchases__it_equipment: 300.0},
    )
    # Same module, different type — must not reach the it_equipment total.
    await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.services,
        {"name": "other-type"},
        {EmissionType.purchases__services: 999.0},
    )
    # Same type, different module.
    await _add_entry(
        db_session,
        decoy_module_id,
        DataEntryTypeEnum.it_equipment,
        _it_equipment_data("other-module"),
        {EmissionType.purchases__it_equipment: 777.0},
    )
    await db_session.commit()

    assert await _kg_by_id(db_session, module_id, DataEntryTypeEnum.it_equipment) == {
        wanted_id: 300.0
    }


async def test_headcount_branch_still_sorts_by_its_rollup_row(
    db_session: AsyncSession,
):
    """The rollup join gained the module/type predicates so it rides the
    covering index — the ``scope IS NULL`` test it already had is why
    ``scope`` is in the index's INCLUDE.

    ``HeadCountStudentResponse`` does not expose ``kg_co2eq``, so the join is
    only observable through the ordering it drives. The rollup values are
    therefore the reverse of insertion order: a predicate that stops matching
    turns the outer join into all-NULL and the sort collapses back to the
    seeded order, which this assertion rejects.
    """
    module_id = await _make_module(db_session, ModuleTypeEnum.headcount)
    decoy_module_id = await _make_module(db_session, ModuleTypeEnum.headcount)

    leaves = {EmissionType.food: 10.0, EmissionType.waste: 5.0}
    low_id = await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.student,
        {"sius_code": "51", "fte": 7.0},
        leaves,
        rollup=(EmissionType.headcount, 15.0),
    )
    high_id = await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.student,
        {"sius_code": "62", "fte": 3.0},
        leaves,
        rollup=(EmissionType.headcount, 500.0),
    )
    await _add_entry(
        db_session,
        decoy_module_id,
        DataEntryTypeEnum.student,
        {"sius_code": "51", "fte": 7.0},
        leaves,
        rollup=(EmissionType.headcount, 999.0),
    )
    await db_session.commit()

    items = await _kg_sorted_page(db_session, module_id, DataEntryTypeEnum.student)
    assert [item.id for item in items] == [high_id, low_id]


async def test_buildings_branch_prefers_the_rollup_and_falls_back_to_leaves(
    db_session: AsyncSession,
):
    """Both halves of the COALESCE in one call: the rollup join (rewritten
    ON clause) and the leaf aggregate subquery (rewritten WHERE). The rollup
    value is deliberately not the leaf sum, so a broken join shows up as the
    wrong number rather than the right one by accident.
    """
    module_id = await _make_module(db_session, ModuleTypeEnum.buildings)
    decoy_module_id = await _make_module(db_session, ModuleTypeEnum.buildings)

    with_rollup_id = await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.building,
        {
            "building_name": "BC",
            "name": "with-rollup",
            "room_type": "laboratories",
        },
        {EmissionType.buildings__rooms__lighting: 20.0},
        rollup=(EmissionType.buildings__rooms, 500.0),
    )
    leaves_only_id = await _add_entry(
        db_session,
        module_id,
        DataEntryTypeEnum.building,
        {
            "building_name": "BC",
            "name": "leaves-only",
            "room_type": "laboratories",
        },
        {
            EmissionType.buildings__rooms__lighting: 20.0,
            EmissionType.buildings__rooms__cooling: 5.0,
        },
    )
    await _add_entry(
        db_session,
        decoy_module_id,
        DataEntryTypeEnum.building,
        {
            "building_name": "BC",
            "name": "other-module",
            "room_type": "laboratories",
        },
        {EmissionType.buildings__rooms__lighting: 900.0},
        rollup=(EmissionType.buildings__rooms, 900.0),
    )
    await db_session.commit()

    assert await _kg_by_id(db_session, module_id, DataEntryTypeEnum.building) == {
        with_rollup_id: 500.0,
        leaves_only_id: 25.0,
    }
