"""Integration tests: train sort fields use Location JOIN and COALESCE.

Verifies two behaviours introduced by the sort-map fix:

1. ``origin_name`` / ``destination_name`` sort order is driven by the
   Location table JOIN, not by DataEntry.data spread alone.

2. ``distance_km`` sort order uses COALESCE(DataEntryEmission.additional_value,
   DataEntry.data["distance_km"]) — so ``additional_value`` wins when set,
   even if DataEntry.data["distance_km"] differs.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository


async def _seed_base(session: AsyncSession):
    """Seed a CarbonReport + travel CarbonReportModule and return both."""
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    session.add(report)
    await session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    session.add(module)
    await session.flush()
    return report, module


async def _seed_train_factor(session: AsyncSession) -> Factor:
    factor = Factor(
        emission_type_id=EmissionType.professional_travel__train.value,
        data_entry_type_id=DataEntryTypeEnum.train.value,
        classification={"country_code": "CH", "year": 2025},
        values={"ef_kg_co2eq_per_km": 0.006},
        year=2025,
    )
    session.add(factor)
    await session.flush()
    return factor


@pytest.mark.asyncio
async def test_origin_destination_name_come_from_location_join(
    db_session: AsyncSession,
):
    """Sorting by origin_name uses Location.name via JOIN — entries come back
    sorted A→Z even when the Location rows are inserted in reverse order.
    """
    repo = DataEntryRepository(db_session)
    _, module = await _seed_base(db_session)
    factor = await _seed_train_factor(db_session)

    # Seed Location rows — note Zurich inserted first, Aachen second.
    loc_zurich = Location(
        transport_mode=TransportModeEnum.train,
        name="Zurich",
        latitude=47.3769,
        longitude=8.5417,
        country_code="CH",
        natural_key=Location.compute_natural_key(
            transport_mode=TransportModeEnum.train,
            name="Zurich",
            latitude=47.3769,
            longitude=8.5417,
            country_code="CH",
        ),
    )
    loc_aachen = Location(
        transport_mode=TransportModeEnum.train,
        name="Aachen",
        latitude=50.7753,
        longitude=6.0839,
        country_code="DE",
        natural_key=Location.compute_natural_key(
            transport_mode=TransportModeEnum.train,
            name="Aachen",
            latitude=50.7753,
            longitude=6.0839,
            country_code="DE",
        ),
    )
    db_session.add(loc_zurich)
    db_session.add(loc_aachen)
    await db_session.flush()

    # DataEntry A — Zurich as origin
    entry_a = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_name": "Zurich",
            "destination_name": "Aachen",
            "user_institutional_id": "u1",
            "number_of_trips": 1,
            "cabin_class": "second",
        },
    )
    # DataEntry B — Aachen as origin
    entry_b = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_name": "Aachen",
            "destination_name": "Zurich",
            "user_institutional_id": "u2",
            "number_of_trips": 1,
            "cabin_class": "second",
        },
    )
    db_session.add(entry_a)
    db_session.add(entry_b)
    await db_session.flush()

    emission_a = DataEntryEmission(
        data_entry_id=entry_a.id,
        emission_type_id=EmissionType.professional_travel__train.value,
        primary_factor_id=factor.id,
        kg_co2eq=5.0,
        additional_value=800.0,
        scope=None,
        meta={},
    )
    emission_b = DataEntryEmission(
        data_entry_id=entry_b.id,
        emission_type_id=EmissionType.professional_travel__train.value,
        primary_factor_id=factor.id,
        kg_co2eq=5.0,
        additional_value=800.0,
        scope=None,
        meta={},
    )
    db_session.add(emission_a)
    db_session.add(emission_b)
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train.value,
        limit=10,
        offset=0,
        sort_by="origin_name",
        sort_order="asc",
    )

    assert result.count == 2, f"expected 2 items, got {result.count}"

    origin_names = [item.origin_name for item in result.items]  # type: ignore[attr-defined]
    assert origin_names == ["Aachen", "Zurich"], (
        f"expected ['Aachen', 'Zurich'] but got {origin_names}"
    )


@pytest.mark.asyncio
async def test_distance_km_sort_uses_coalesce_additional_value_over_data(
    db_session: AsyncSession,
):
    """COALESCE(additional_value, data["distance_km"]) is used for sort, so
    DataEntryEmission.additional_value takes precedence over DataEntry.data.

    Entry A: data["distance_km"]=500, additional_value=300  → effective sort key 300
    Entry B: data has no distance_km,  additional_value=100  → effective sort key 100

    Ascending sort must return B first (100) then A (300), NOT A first because
    its raw data["distance_km"]=500 would appear higher with the old broken sort.
    """
    repo = DataEntryRepository(db_session)
    _, module = await _seed_base(db_session)
    factor = await _seed_train_factor(db_session)

    loc_gen = Location(
        transport_mode=TransportModeEnum.train,
        name="Geneva",
        latitude=46.2044,
        longitude=6.1432,
        country_code="CH",
        natural_key=Location.compute_natural_key(
            transport_mode=TransportModeEnum.train,
            name="Geneva",
            latitude=46.2044,
            longitude=6.1432,
            country_code="CH",
        ),
    )
    loc_lau = Location(
        transport_mode=TransportModeEnum.train,
        name="Lausanne",
        latitude=46.5197,
        longitude=6.6323,
        country_code="CH",
        natural_key=Location.compute_natural_key(
            transport_mode=TransportModeEnum.train,
            name="Lausanne",
            latitude=46.5197,
            longitude=6.6323,
            country_code="CH",
        ),
    )
    db_session.add(loc_gen)
    db_session.add(loc_lau)
    await db_session.flush()

    # Entry A: data has distance_km=500, but emission.additional_value=300
    entry_a = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_name": "Geneva",
            "destination_name": "Lausanne",
            "distance_km": 500,
            "user_institutional_id": "ua",
            "number_of_trips": 1,
            "cabin_class": "second",
        },
    )
    # Entry B: data has NO distance_km, emission.additional_value=100
    entry_b = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_name": "Lausanne",
            "destination_name": "Geneva",
            "user_institutional_id": "ub",
            "number_of_trips": 1,
            "cabin_class": "second",
        },
    )
    db_session.add(entry_a)
    db_session.add(entry_b)
    await db_session.flush()

    emission_a = DataEntryEmission(
        data_entry_id=entry_a.id,
        emission_type_id=EmissionType.professional_travel__train.value,
        primary_factor_id=factor.id,
        kg_co2eq=1.8,
        additional_value=300.0,
        scope=None,
        meta={},
    )
    emission_b = DataEntryEmission(
        data_entry_id=entry_b.id,
        emission_type_id=EmissionType.professional_travel__train.value,
        primary_factor_id=factor.id,
        kg_co2eq=0.6,
        additional_value=100.0,
        scope=None,
        meta={},
    )
    db_session.add(emission_a)
    db_session.add(emission_b)
    await db_session.commit()

    result = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.train.value,
        limit=10,
        offset=0,
        sort_by="distance_km",
        sort_order="asc",
    )

    assert result.count == 2, f"expected 2 items, got {result.count}"

    items = result.items
    assert items[0].distance_km == 100.0, (  # type: ignore[attr-defined]
        f"first item distance_km should be 100.0 (entry B), got {items[0].distance_km}"  # type: ignore[attr-defined]
    )
    assert items[1].distance_km == 300.0, (  # type: ignore[attr-defined]
        f"second item distance_km should be 300.0 (entry A), got {items[1].distance_km}"  # type: ignore[attr-defined]
    )
