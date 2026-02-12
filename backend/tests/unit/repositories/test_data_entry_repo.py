"""Unit tests for DataEntryRepository."""

from unittest.mock import MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DEFAULT_FILTER_MAP, DataEntryRepository
from app.schemas.data_entry import DataEntryUpdate

# ======================================================================
# CRUD Operation Tests
# ======================================================================


@pytest.mark.asyncio
async def test_create_data_entry(db_session: AsyncSession):
    """Test creating a data entry."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create data entry
    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip", "transport_mode": "plane"},
    )

    result = await repo.create(data_entry)

    assert result.id is not None
    assert result.carbon_report_module_id == module.id
    assert result.data_entry_type_id == DataEntryTypeEnum.trips
    assert result.data["name"] == "Test Trip"


@pytest.mark.asyncio
async def test_get_data_entry(db_session: AsyncSession):
    """Test retrieving a data entry by ID."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create data entry
    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    result = await repo.get(data_entry.id)

    assert result is not None
    assert result.id == data_entry.id
    assert result.data["name"] == "Test Trip"


@pytest.mark.asyncio
async def test_get_data_entry_not_found(db_session: AsyncSession):
    """Test retrieving a non-existent data entry returns None."""
    repo = DataEntryRepository(db_session)

    result = await repo.get(99999)

    assert result is None


@pytest.mark.asyncio
async def test_update_data_entry(db_session: AsyncSession):
    """Test updating a data entry."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create data entry
    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip", "transport_mode": "plane"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    # Update data entry
    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=module.id,
        data={"transport_mode": "train", "new_field": "value"},
    )

    result = await repo.update(data_entry.id, update_data, user_id=1)

    assert result is not None
    assert result.data["name"] == "Test Trip"  # Original field preserved
    assert result.data["transport_mode"] == "train"  # Updated field
    assert result.data["new_field"] == "value"  # New field added


@pytest.mark.asyncio
async def test_update_data_entry_not_found(db_session: AsyncSession):
    """Test updating a non-existent data entry returns None."""
    repo = DataEntryRepository(db_session)

    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.trips.value,
        carbon_report_module_id=1,
        data={"name": "Updated"},
    )
    result = await repo.update(99999, update_data, user_id=1)

    assert result is None


@pytest.mark.asyncio
async def test_delete_data_entry(db_session: AsyncSession):
    """Test deleting a data entry."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create data entry
    data_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.trips,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    result = await repo.delete(data_entry.id)

    assert result is True

    # Verify deletion
    deleted_entry = await repo.get(data_entry.id)
    assert deleted_entry is None


@pytest.mark.asyncio
async def test_delete_data_entry_not_found(db_session: AsyncSession):
    """Test deleting a non-existent data entry returns False."""
    repo = DataEntryRepository(db_session)

    result = await repo.delete(99999)

    assert result is False


# ======================================================================
# Bulk Operations Tests
# ======================================================================


@pytest.mark.asyncio
async def test_bulk_create_data_entries(db_session: AsyncSession):
    """Test bulk creating multiple data entries."""
    repo = DataEntryRepository(db_session)

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
        for i in range(5)
    ]

    result = await repo.bulk_create(entries)

    assert len(result) == 5
    assert all(entry.id is not None for entry in result)
    assert result[0].data["name"] == "Trip 0"
    assert result[4].data["name"] == "Trip 4"


@pytest.mark.asyncio
async def test_bulk_delete_data_entries(db_session: AsyncSession):
    """Test bulk deleting data entries by module and type."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries of different types
    trips_entries = [
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

    db_session.add_all(trips_entries + [other_entry])
    await db_session.flush()

    # Bulk delete only trips
    await repo.bulk_delete(module.id, DataEntryTypeEnum.trips)
    await db_session.flush()

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
# Aggregation and Statistics Tests
# ======================================================================


@pytest.mark.asyncio
async def test_get_total_count_by_submodule(db_session: AsyncSession):
    """Test counting entries by submodule type."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries of different types
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

    result = await repo.get_total_count_by_submodule(module.id)

    assert DataEntryTypeEnum.trips.value in result
    assert result[DataEntryTypeEnum.trips.value] == 5


@pytest.mark.asyncio
async def test_get_total_per_field_fte(db_session: AsyncSession):
    """Test summing FTE across entries."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with FTE values
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Person {i}", "fte": 0.5 + i * 0.1},
        )
        for i in range(5)
    ]

    db_session.add_all(entries)
    await db_session.flush()

    result = await repo.get_total_per_field("fte", module.id)

    # 0.5 + 0.6 + 0.7 + 0.8 + 0.9 = 3.5
    assert result == pytest.approx(3.5, rel=0.01)


@pytest.mark.asyncio
async def test_get_total_per_field_kg_co2eq(db_session: AsyncSession):
    """Test summing kg_co2eq from JSONB data field."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with emissions
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}", "kg_co2eq": 100.0 * (i + 1)},
        )
        for i in range(3)
    ]

    db_session.add_all(entries)
    await db_session.flush()

    result = await repo.get_total_per_field("kg_co2eq", module.id)

    # 100 + 200 + 300 = 600
    assert result == pytest.approx(600.0, rel=0.01)


@pytest.mark.asyncio
async def test_get_total_per_field_with_type_filter(db_session: AsyncSession):
    """Test summing with data entry type filter."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create mixed entries
    trips = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}", "kg_co2eq": 100.0},
        )
        for i in range(3)
    ]

    db_session.add_all(trips)
    await db_session.flush()

    result = await repo.get_total_per_field(
        "kg_co2eq", module.id, DataEntryTypeEnum.trips.value
    )

    # Only trips counted: 100 * 3 = 300
    assert result == pytest.approx(300.0, rel=0.01)


@pytest.mark.asyncio
async def test_get_total_per_field_empty_result(db_session: AsyncSession):
    """Test summing returns 0.0 for empty result."""
    repo = DataEntryRepository(db_session)

    result = await repo.get_total_per_field("fte", carbon_report_module_id=99999)

    assert result == 0.0


@pytest.mark.asyncio
async def test_get_stats_by_data_entry_type(db_session: AsyncSession):
    """Test aggregating by data_entry_type_id."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with FTE
    entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.trips,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}", "fte": 1.0},
        )
        for i in range(3)
    ]

    db_session.add_all(entries)
    await db_session.flush()

    result = await repo.get_stats(
        module.id, aggregate_by="data_entry_type_id", aggregate_field="fte"
    )

    assert str(DataEntryTypeEnum.trips.value) in result
    assert result[str(DataEntryTypeEnum.trips.value)] == pytest.approx(3.0, rel=0.01)


@pytest.mark.asyncio
async def test_get_stats_by_function(db_session: AsyncSession):
    """Test aggregating headcount by function."""
    repo = DataEntryRepository(db_session)

    # Create test module
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Create entries with functions
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
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"function": "Admin", "fte": 1.0},
        ),
    ]

    db_session.add_all(entries)
    await db_session.flush()

    result = await repo.get_stats(
        module.id, aggregate_by="function", aggregate_field="fte"
    )

    # Results should be grouped by function (with role mapping applied)
    assert len(result) > 0


# ======================================================================
# Filter and Sort Tests
# ======================================================================


def test_apply_name_filter_no_filter():
    """Test that no filter is applied when filter is empty."""
    repo = DataEntryRepository(MagicMock())
    mock_statement = MagicMock()
    mock_handler = MagicMock()

    result_stmt, filter_pattern = repo._apply_name_filter(
        mock_statement, None, mock_handler
    )

    assert filter_pattern == ""
    assert result_stmt == mock_statement


def test_apply_name_filter_with_pattern():
    """Test that filter is applied with valid pattern."""
    repo = DataEntryRepository(MagicMock())
    mock_statement = MagicMock()
    mock_handler = MagicMock()
    mock_handler.filter_map = DEFAULT_FILTER_MAP

    result_stmt, filter_pattern = repo._apply_name_filter(
        mock_statement, "test", mock_handler
    )

    assert filter_pattern == "%test%"


def test_apply_name_filter_max_length():
    """Test that filter is truncated to 100 characters."""
    repo = DataEntryRepository(MagicMock())
    mock_statement = MagicMock()
    mock_handler = MagicMock()
    mock_handler.filter_map = DEFAULT_FILTER_MAP

    long_filter = "a" * 150
    result_stmt, filter_pattern = repo._apply_name_filter(
        mock_statement, long_filter, mock_handler
    )

    # Should be truncated to 100 + 2 for %% = 102
    assert len(filter_pattern) == 102
    assert filter_pattern == f"%{'a' * 100}%"


def test_apply_name_filter_wildcard_only():
    """Test that wildcard-only filters are ignored."""
    repo = DataEntryRepository(MagicMock())
    mock_statement = MagicMock()
    mock_handler = MagicMock()

    for wildcard in ["%", "*", "  "]:
        result_stmt, filter_pattern = repo._apply_name_filter(
            mock_statement, wildcard, mock_handler
        )
        assert filter_pattern == ""


# ======================================================================
# Default Filter Map Test
# ======================================================================


def test_default_filter_map():
    """Test that DEFAULT_FILTER_MAP is properly defined."""
    assert "name" in DEFAULT_FILTER_MAP
    assert DEFAULT_FILTER_MAP["name"] is not None
