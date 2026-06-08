"""Integration tests: equipment-electric-consumption sort by ``equipment_class``.

Reproduces the bug reported against the ``scientific`` submodule list endpoint
(e.g. ``/api/v1/modules/610/2025/equipment-electric-consumption/scientific
?sort_by=equipment_class&sort_order=asc``).

Two behaviours are pinned:

1. ``test_equipment_class_sort_isolated`` — when every entry has a matching
   Factor AND ``DataEntry.data["equipment_class"]`` equals
   ``Factor.classification["equipment_class"]``, ORDER BY applies and asc/desc
   reorder the rows. This proves the sort machinery itself works.

2. ``test_equipment_class_sort_handles_entries_without_factor`` — regression
   guard for the reported bug. CSV ingestion can leave an entry with
   ``primary_factor_id = NULL`` (no factor matched). The sort key must read from
   the same source the row displays (``DataEntry.data["equipment_class"]``), not
   from ``Factor.classification`` — otherwise the factorless row gets a NULL
   sort key and scatters to whichever end the DB places NULLs, even though it
   shows a real ``equipment_class``. Pre-fix this asserted order failed.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository


async def _seed_base(session: AsyncSession) -> CarbonReportModule:
    """Seed a CarbonReport + equipment CarbonReportModule and return the module."""
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    session.add(report)
    await session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        status=ModuleStatus.NOT_STARTED,
    )
    session.add(module)
    await session.flush()
    return module


async def _seed_factor(session: AsyncSession, equipment_class: str) -> Factor:
    factor = Factor(
        emission_type_id=EmissionType.equipment.value,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": equipment_class, "sub_class": None},
        values={
            "active_power_w": 40.0,
            "standby_power_w": 40.0,
            "ef_kg_co2eq_per_kwh": 0.1,
        },
        year=2025,
    )
    session.add(factor)
    await session.flush()
    return factor


async def _seed_entry(
    session: AsyncSession,
    module: CarbonReportModule,
    *,
    name: str,
    equipment_class: str,
    factor: Factor | None,
) -> DataEntry:
    """Seed one scientific equipment entry.

    When ``factor`` is None the entry has no matching Factor and no emission row
    (the CSV-import-with-missing-factor case): ``primary_factor_id`` stays NULL.
    """
    data = {
        "name": name,
        "equipment_class": equipment_class,
        "active_usage_hours_per_week": 12,
        "standby_usage_hours_per_week": 150,
    }
    if factor is not None:
        data["primary_factor_id"] = factor.id
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        status=DataEntryStatusEnum.PENDING,
        data=data,
    )
    session.add(entry)
    await session.flush()

    if factor is not None:
        session.add(
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.equipment.value,
                primary_factor_id=factor.id,
                kg_co2eq=1.0,
                scope=None,
                meta={},
            )
        )
        await session.flush()
    return entry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort_order, expected",
    [
        ("asc", ["alpha", "beta", "gamma"]),
        ("desc", ["gamma", "beta", "alpha"]),
    ],
)
async def test_equipment_class_sort_isolated(
    db_session: AsyncSession, sort_order: str, expected: list[str]
):
    """ORDER BY equipment_class works when data == factor classification.

    Entries are inserted scrambled (gamma, alpha, beta); the result must come
    back sorted by ``equipment_class`` in the requested direction.
    """
    repo = DataEntryRepository(db_session)
    module = await _seed_base(db_session)

    for cls in ("gamma", "alpha", "beta"):  # scrambled insert order
        factor = await _seed_factor(db_session, cls)
        await _seed_entry(
            db_session, module, name=f"eq-{cls}", equipment_class=cls, factor=factor
        )
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=5,
        offset=0,
        sort_by="equipment_class",
        sort_order=sort_order,
    )

    classes = [item.equipment_class for item in result.items]  # type: ignore[attr-defined]
    assert result.count == 3, f"expected 3 items, got {result.count}"
    assert classes == expected, (
        f"sort_order={sort_order!r}: expected {expected}, got {classes}"
    )


@pytest.mark.asyncio
async def test_equipment_class_sort_handles_entries_without_factor(
    db_session: AsyncSession,
):
    """Regression: an entry with primary_factor_id=NULL still sorts correctly.

    Three entries, each displaying a distinct ``equipment_class``:
      - ``alpha`` — has a matching factor
      - ``middle`` — NO factor (primary_factor_id NULL)
      - ``zzz``   — has a matching factor

    Sorting ascending, the user expects the displayed column ordered
    ``[alpha, middle, zzz]``. Because the sort key now reads from the same
    source as the display (``DataEntry.data["equipment_class"]``), the factorless
    ``middle`` row keeps its place. Pre-fix the sort key was
    ``Factor.classification["equipment_class"]`` (NULL for ``middle``), which
    scattered it to whichever end the DB places NULLs.
    """
    repo = DataEntryRepository(db_session)
    module = await _seed_base(db_session)

    factor_alpha = await _seed_factor(db_session, "alpha")
    factor_zzz = await _seed_factor(db_session, "zzz")

    await _seed_entry(
        db_session,
        module,
        name="eq-alpha",
        equipment_class="alpha",
        factor=factor_alpha,
    )
    # No factor matched on import → primary_factor_id stays NULL.
    await _seed_entry(
        db_session, module, name="eq-middle", equipment_class="middle", factor=None
    )
    await _seed_entry(
        db_session, module, name="eq-zzz", equipment_class="zzz", factor=factor_zzz
    )
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=5,
        offset=0,
        sort_by="equipment_class",
        sort_order="asc",
    )

    classes = [item.equipment_class for item in result.items]  # type: ignore[attr-defined]
    assert result.count == 3, f"expected 3 items, got {result.count}"
    assert classes == ["alpha", "middle", "zzz"], (
        "displayed equipment_class is not sorted because the factorless entry's "
        f"NULL sort key ignores its real class; got {classes}"
    )
