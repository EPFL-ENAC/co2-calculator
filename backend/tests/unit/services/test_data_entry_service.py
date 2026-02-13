"""Unit tests for DataEntryService."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User, UserProvider
from app.schemas.data_entry import DataEntryCreate, DataEntryUpdate
from app.services.data_entry_service import DataEntryService

# ======================================================================
# Create Tests
# ======================================================================


@pytest.mark.asyncio
async def test_create_data_entry_success(db_session: AsyncSession):
    """Test creating a data entry successfully."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    # Create data
    data = DataEntryCreate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=module.id,
        data={"name": "Test Trip", "transport_mode": "plane"},
    )

    result = await service.create(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        user=user,
        data=data,
    )

    assert result.id is not None
    assert result.carbon_report_module_id == module.id
    assert result.data_entry_type_id == DataEntryTypeEnum.trips
    assert result.data["name"] == "Test Trip"
    assert result.data["transport_mode"] == "plane"


# ======================================================================
# Update Tests
# ======================================================================


@pytest.mark.asyncio
async def test_update_data_entry_success(db_session: AsyncSession):
    """Test updating a data entry successfully."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create existing entry
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Original Trip", "transport_mode": "plane"},
    )
    db_session.add(entry)
    await db_session.flush()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    # Update data
    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=module.id,
        data={"transport_mode": "train"},
    )

    result = await service.update(id=entry.id, data=update_data, user=user)

    assert result.id == entry.id
    assert result.data["name"] == "Original Trip"  # Preserved
    assert result.data["transport_mode"] == "train"  # Updated


@pytest.mark.asyncio
async def test_update_data_entry_without_user_raises_error(db_session: AsyncSession):
    """Test that updating without user context raises PermissionError."""
    service = DataEntryService(db_session)

    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=1,
        data={"name": "Updated"},
    )

    # No user or user without ID
    with pytest.raises(PermissionError, match="User context is required"):
        await service.update(id=1, data=update_data, user=None)

    with pytest.raises(PermissionError, match="User context is required"):
        await service.update(id=1, data=update_data, user=User(id=None, email=""))


@pytest.mark.asyncio
async def test_update_data_entry_not_found_raises_error(db_session: AsyncSession):
    """Test that updating non-existent entry raises ValueError."""
    service = DataEntryService(db_session)

    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )
    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=1,
        data={"name": "Updated"},
    )

    with pytest.raises(ValueError, match="not found"):
        await service.update(id=99999, data=update_data, user=user)


# ======================================================================
# Delete Tests
# ======================================================================


@pytest.mark.asyncio
async def test_delete_data_entry_success(db_session: AsyncSession):
    """Test deleting a data entry successfully."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entry
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(entry)
    await db_session.flush()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    result = await service.delete(id=entry.id, current_user=user)

    assert result is True

    # Verify deletion
    with pytest.raises(ValueError, match="not found"):
        await service.get(entry.id)


@pytest.mark.asyncio
async def test_delete_data_entry_not_found_raises_error(db_session: AsyncSession):
    """Test that deleting non-existent entry raises ValueError."""
    service = DataEntryService(db_session)

    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    with pytest.raises(ValueError, match="not found"):
        await service.delete(id=99999, current_user=user)


# ======================================================================
# Get Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_data_entry_success(db_session: AsyncSession):
    """Test retrieving a data entry by ID."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entry
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(entry)
    await db_session.flush()

    result = await service.get(entry.id)

    assert result.id == entry.id
    assert result.data["name"] == "Test Trip"


@pytest.mark.asyncio
async def test_get_data_entry_not_found_raises_error(db_session: AsyncSession):
    """Test that retrieving non-existent entry raises ValueError."""
    service = DataEntryService(db_session)

    with pytest.raises(ValueError, match="not found"):
        await service.get(99999)


# ======================================================================
# Bulk Operations Tests
# ======================================================================


@pytest.mark.asyncio
async def test_bulk_create_data_entries(db_session: AsyncSession):
    """Test bulk creating multiple data entries."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    # Create multiple entries
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(5)
    ]

    result = await service.bulk_create(entries, user)

    assert len(result) == 5
    assert all(r.id is not None for r in result)
    assert result[0].data["name"] == "Trip 0"
    assert result[4].data["name"] == "Trip 4"


@pytest.mark.asyncio
async def test_bulk_delete_data_entries(db_session: AsyncSession):
    """Test bulk deleting data entries by module and type."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create user
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        provider_code="default-1441",
    )

    # Create entries of different types
    trips = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(3)
    ]

    other_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.external_clouds,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Cloud"},
    )

    db_session.add_all(trips + [other_entry])
    await db_session.flush()

    # Bulk delete only trips
    await service.bulk_delete(module.id, DataEntryTypeEnum.trips, user)

    # Verify trips are deleted
    from sqlmodel import select

    stmt = select(DataEntry).where(
        DataEntry.carbon_report_module_id == module.id,
        DataEntry.data_entry_type_id == DataEntryTypeEnum.trips.value,
    )
    result = await db_session.exec(stmt)
    remaining_trips = list(result.all())
    assert len(remaining_trips) == 0

    # Verify other entry still exists
    stmt = select(DataEntry).where(
        DataEntry.carbon_report_module_id == module.id,
        DataEntry.data_entry_type_id == DataEntryTypeEnum.external_clouds.value,
    )
    result = await db_session.exec(stmt)
    remaining_other = list(result.all())
    assert len(remaining_other) == 1


# ======================================================================
# List and Query Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_list_data_entries(db_session: AsyncSession):
    """Test listing data entries with pagination."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create multiple entries
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(10)
    ]
    db_session.add_all(entries)
    await db_session.flush()

    # Get first page
    result = await service.get_list(
        carbon_report_module_id=module.id,
        limit=5,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(result) == 5
    assert result[0].data["name"] == "Trip 0"


# ======================================================================
# Module Data Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_module_data(db_session: AsyncSession):
    """Test retrieving module-level aggregated data."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(5)
    ]
    db_session.add_all(entries)
    await db_session.flush()

    result = await service.get_module_data(module.id)

    assert result.carbon_report_module_id == module.id
    assert result.data_entry_types_total_items is not None
    assert DataEntryTypeEnum.trips.value in result.data_entry_types_total_items
    assert result.data_entry_types_total_items[DataEntryTypeEnum.trips.value] == 5
    assert result.retrieved_at is not None


# ======================================================================
# Submodule Data Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_submodule_data(db_session: AsyncSession):
    """Test retrieving submodule-level data."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={
                "traveler_name": f"Traveler {i}",
                "origin_location_id": 1,
                "destination_location_id": 2,
                "transport_mode": "plane",
                "number_of_trips": 1,
                "unit_id": 1,
            },
        )
        for i in range(3)
    ]
    db_session.add_all(entries)
    await db_session.flush()

    result = await service.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert result.id == DataEntryTypeEnum.trips.value
    assert result.count == 3
    assert result.summary.total_items == 3


# ======================================================================
# Statistics Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_stats(db_session: AsyncSession):
    """Test retrieving module statistics."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with FTE
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"function": "Researcher", "fte": 1.0},
        ),
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"function": "Researcher", "fte": 0.5},
        ),
    ]
    db_session.add_all(entries)
    await db_session.flush()

    result = await service.get_stats(
        carbon_report_module_id=module.id,
        aggregate_by="function",
        aggregate_field="fte",
    )

    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_total_per_field(db_session: AsyncSession):
    """Test getting total sum for a specific field."""
    service = DataEntryService(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with FTE
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Person {i}", "fte": 1.0},
        )
        for i in range(5)
    ]
    db_session.add_all(entries)
    await db_session.flush()

    result = await service.get_total_per_field(
        field_name="fte",
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.member.value,
    )

    assert result == pytest.approx(5.0, rel=0.01)
