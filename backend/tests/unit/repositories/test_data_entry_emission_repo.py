"""Unit tests for DataEntryEmissionRepository."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository

# ======================================================================
# CRUD Operation Tests
# ======================================================================


@pytest.mark.asyncio
async def test_create_emission(db_session: AsyncSession):
    """Test creating a data entry emission."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    # Create emission
    emission = DataEntryEmission(
        data_entry_id=data_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=250.5,
        meta={"distance_km": 500},
    )

    result = await repo.create(emission)

    assert result.id is not None
    assert result.data_entry_id == data_entry.id
    assert result.kg_co2eq == 250.5
    assert result.meta["distance_km"] == 500


@pytest.mark.asyncio
async def test_update_emission(db_session: AsyncSession):
    """Test updating a data entry emission."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    emission = DataEntryEmission(
        data_entry_id=data_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=250.5,
    )
    await repo.create(emission)

    # Update emission
    emission.kg_co2eq = 300.0
    result = await repo.update(emission)

    assert result.kg_co2eq == 300.0


@pytest.mark.asyncio
async def test_get_by_data_entry_id(db_session: AsyncSession):
    """Test retrieving emission by data entry ID."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    emission = DataEntryEmission(
        data_entry_id=data_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=250.5,
    )
    await repo.create(emission)

    result = await repo.get_by_data_entry_id(data_entry.id)

    assert result is not None
    assert result.data_entry_id == data_entry.id
    assert result.kg_co2eq == 250.5


@pytest.mark.asyncio
async def test_get_by_data_entry_id_not_found(db_session: AsyncSession):
    """Test retrieving emission for non-existent data entry returns None."""
    repo = DataEntryEmissionRepository(db_session)

    result = await repo.get_by_data_entry_id(99999)

    assert result is None


@pytest.mark.asyncio
async def test_delete_by_data_entry_id(db_session: AsyncSession):
    """Test deleting emission by data entry ID."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    emission = DataEntryEmission(
        data_entry_id=data_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=250.5,
    )
    await repo.create(emission)

    await repo.delete_by_data_entry_id(data_entry.id)
    await db_session.flush()

    # Verify deletion
    result = await repo.get_by_data_entry_id(data_entry.id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_by_data_entry_id_not_found(db_session: AsyncSession):
    """Test deleting emission for non-existent data entry doesn't raise error."""
    repo = DataEntryEmissionRepository(db_session)

    # Should not raise any exception
    await repo.delete_by_data_entry_id(99999)


@pytest.mark.asyncio
async def test_bulk_create_emissions(db_session: AsyncSession):
    """Test bulk creating multiple emissions."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(3)
    ]
    db_session.add_all(entries)
    await db_session.flush()

    emissions = [
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionTypeEnum.plane,
            kg_co2eq=100.0 * (i + 1),
        )
        for i, entry in enumerate(entries)
    ]

    result = await repo.bulk_create(emissions)

    assert len(result) == 3
    assert all(e.id is not None for e in result)
    assert result[0].kg_co2eq == 100.0
    assert result[2].kg_co2eq == 300.0


# ======================================================================
# Aggregation and Statistics Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_stats_by_emission_type(db_session: AsyncSession):
    """Test aggregating emissions by emission_type_id."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with different transport modes
    plane_entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Plane {i}", "transport_mode": "plane"},
        )
        for i in range(2)
    ]

    train_entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Train {i}", "transport_mode": "train"},
        )
        for i in range(3)
    ]

    db_session.add_all(plane_entries + train_entries)
    await db_session.flush()

    # Create emissions
    plane_emissions = [
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionTypeEnum.plane,
            kg_co2eq=200.0,
        )
        for entry in plane_entries
    ]

    train_emissions = [
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionTypeEnum.train,
            kg_co2eq=50.0,
        )
        for entry in train_entries
    ]

    db_session.add_all(plane_emissions + train_emissions)
    await db_session.flush()

    result = await repo.get_stats(module.id, "emission_type_id", "kg_co2eq")

    assert str(EmissionTypeEnum.plane.value) in result
    assert str(EmissionTypeEnum.train.value) in result
    assert result[str(EmissionTypeEnum.plane.value)] == pytest.approx(
        400.0, rel=0.01
    )  # 2 * 200
    assert result[str(EmissionTypeEnum.train.value)] == pytest.approx(
        150.0, rel=0.01
    )  # 3 * 50


@pytest.mark.asyncio
async def test_get_stats_empty_result(db_session: AsyncSession):
    """Test get_stats returns empty dict when no data."""
    repo = DataEntryEmissionRepository(db_session)

    result = await repo.get_stats(99999, "emission_type_id", "kg_co2eq")

    assert result == {}


# ======================================================================
# Travel Stats by Class Tests (Treemap Data)
# ======================================================================


@pytest.mark.asyncio
async def test_get_travel_stats_by_class_basic(db_session: AsyncSession):
    """Test travel statistics aggregated by transport mode and cabin class."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create plane trips with different cabin classes
    eco_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane", "cabin_class": "eco"},
    )

    business_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane", "cabin_class": "business"},
    )

    db_session.add_all([eco_entry, business_entry])
    await db_session.flush()

    # Create emissions
    eco_emission = DataEntryEmission(
        data_entry_id=eco_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=200.0,
    )

    business_emission = DataEntryEmission(
        data_entry_id=business_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=600.0,
    )

    db_session.add_all([eco_emission, business_emission])
    await db_session.flush()

    result = await repo.get_travel_stats_by_class(module.id)

    # Should have one category (plane) with two classes
    assert len(result) == 1
    assert result[0]["name"] == "plane"
    assert result[0]["value"] == 800.0  # 200 + 600

    children = result[0]["children"]
    assert len(children) == 2

    # Find eco and business children
    eco_child = next(c for c in children if c["name"] == "eco")
    business_child = next(c for c in children if c["name"] == "business")

    assert eco_child["value"] == 200.0
    assert eco_child["percentage"] == pytest.approx(25.0, rel=0.01)  # 200/800 * 100
    assert business_child["value"] == 600.0
    assert business_child["percentage"] == pytest.approx(
        75.0, rel=0.01
    )  # 600/800 * 100


@pytest.mark.asyncio
async def test_get_travel_stats_by_class_null_cabin(db_session: AsyncSession):
    """Test that NULL cabin_class gets default value based on transport mode."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create plane trip with NULL cabin_class
    plane_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane"},  # No cabin_class
    )

    # Create train trip with NULL cabin_class
    train_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "train"},  # No cabin_class
    )

    db_session.add_all([plane_entry, train_entry])
    await db_session.flush()

    # Create emissions
    plane_emission = DataEntryEmission(
        data_entry_id=plane_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=300.0,
    )

    train_emission = DataEntryEmission(
        data_entry_id=train_entry.id,
        emission_type_id=EmissionTypeEnum.train,
        kg_co2eq=50.0,
    )

    db_session.add_all([plane_emission, train_emission])
    await db_session.flush()

    result = await repo.get_travel_stats_by_class(module.id)

    # Should have two categories
    assert len(result) == 2

    # Find plane and train categories
    plane_cat = next(c for c in result if c["name"] == "plane")
    train_cat = next(c for c in result if c["name"] == "train")

    # NULL cabin_class should default to "eco" for plane, "class_2" for train
    assert plane_cat["children"][0]["name"] == "eco"
    assert train_cat["children"][0]["name"] == "class_2"


@pytest.mark.asyncio
async def test_get_travel_stats_by_class_filters_zero_emissions(
    db_session: AsyncSession,
):
    """Test that zero or NULL emissions are filtered out."""
    repo = DataEntryEmissionRepository(db_session)

    # Create prerequisites
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries
    valid_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane", "cabin_class": "eco"},
    )

    zero_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane", "cabin_class": "business"},
    )

    db_session.add_all([valid_entry, zero_entry])
    await db_session.flush()

    # Create emissions - one valid, one zero
    valid_emission = DataEntryEmission(
        data_entry_id=valid_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=200.0,
    )

    zero_emission = DataEntryEmission(
        data_entry_id=zero_entry.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=0.0,  # Zero emission
    )

    db_session.add_all([valid_emission, zero_emission])
    await db_session.flush()

    result = await repo.get_travel_stats_by_class(module.id)

    # Should only include valid emission
    assert len(result) == 1
    assert result[0]["value"] == 200.0
    assert len(result[0]["children"]) == 1
    assert result[0]["children"][0]["name"] == "eco"


@pytest.mark.asyncio
async def test_get_travel_stats_by_class_empty_result(db_session: AsyncSession):
    """Test get_travel_stats_by_class returns empty list when no data."""
    repo = DataEntryEmissionRepository(db_session)

    result = await repo.get_travel_stats_by_class(99999)

    assert result == []


# ======================================================================
# Travel Evolution Over Time Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_travel_evolution_over_time(db_session: AsyncSession):
    """Test travel emissions aggregated by year and transport mode."""
    repo = DataEntryEmissionRepository(db_session)

    # Create unit
    unit = Unit(id=12345, provider_code="TEST-12345", name="Test Unit")
    db_session.add(unit)
    await db_session.flush()

    # Create carbon reports for multiple years
    report_2023 = CarbonReport(unit_id=unit.id, year=2023)
    report_2024 = CarbonReport(unit_id=unit.id, year=2024)
    db_session.add_all([report_2023, report_2024])
    await db_session.flush()

    # Create modules for both years
    module_2023 = CarbonReportModule(
        carbon_report_id=report_2023.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    module_2024 = CarbonReportModule(
        carbon_report_id=report_2024.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add_all([module_2023, module_2024])
    await db_session.flush()

    # Create entries for 2023
    plane_2023 = DataEntry(
        carbon_report_module_id=module_2023.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane"},
    )

    # Create entries for 2024
    plane_2024 = DataEntry(
        carbon_report_module_id=module_2024.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "plane"},
    )

    train_2024 = DataEntry(
        carbon_report_module_id=module_2024.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"transport_mode": "train"},
    )

    db_session.add_all([plane_2023, plane_2024, train_2024])
    await db_session.flush()

    # Create emissions
    emission_plane_2023 = DataEntryEmission(
        data_entry_id=plane_2023.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=500.0,
    )

    emission_plane_2024 = DataEntryEmission(
        data_entry_id=plane_2024.id,
        emission_type_id=EmissionTypeEnum.plane,
        kg_co2eq=600.0,
    )

    emission_train_2024 = DataEntryEmission(
        data_entry_id=train_2024.id,
        emission_type_id=EmissionTypeEnum.train,
        kg_co2eq=100.0,
    )

    db_session.add_all([emission_plane_2023, emission_plane_2024, emission_train_2024])
    await db_session.flush()

    result = await repo.get_travel_evolution_over_time(unit.id)

    # Should have 3 records: plane 2023, plane 2024, train 2024
    assert len(result) == 3

    # Find specific records
    plane_2023_record = next(
        r for r in result if r["year"] == 2023 and r["transport_mode"] == "plane"
    )
    plane_2024_record = next(
        r for r in result if r["year"] == 2024 and r["transport_mode"] == "plane"
    )
    train_2024_record = next(
        r for r in result if r["year"] == 2024 and r["transport_mode"] == "train"
    )

    assert plane_2023_record["kg_co2eq"] == pytest.approx(500.0, rel=0.01)
    assert plane_2024_record["kg_co2eq"] == pytest.approx(600.0, rel=0.01)
    assert train_2024_record["kg_co2eq"] == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_get_travel_evolution_over_time_empty_result(db_session: AsyncSession):
    """Test get_travel_evolution_over_time returns empty list when no data."""
    repo = DataEntryEmissionRepository(db_session)

    result = await repo.get_travel_evolution_over_time(99999)

    assert result == []
