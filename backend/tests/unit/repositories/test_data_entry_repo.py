"""Unit tests for DataEntryRepository."""

from unittest.mock import MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import emission_type_scope
from app.repositories.data_entry_repo import DEFAULT_FILTER_MAP, DataEntryRepository
from app.schemas.data_entry import DataEntryUpdate
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    TRAVELER_OTHER_INTERNAL,
)

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
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip", "cabin_class": "eco"},
    )

    result = await repo.create(data_entry)

    assert result.id is not None
    assert result.carbon_report_module_id == module.id
    assert result.data_entry_type_id == DataEntryTypeEnum.plane
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
        data_entry_type_id=DataEntryTypeEnum.plane,
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
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Test Trip", "cabin_class": "eco"},
    )
    db_session.add(data_entry)
    await db_session.flush()

    # Update data entry
    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        carbon_report_module_id=module.id,
        data={"cabin_class": "business", "new_field": "value"},
    )

    result = await repo.update(data_entry.id, update_data, user_id=1)

    assert result is not None
    assert result.data["name"] == "Test Trip"  # Original field preserved
    assert result.data["cabin_class"] == "business"  # Updated field
    assert result.data["new_field"] == "value"  # New field added


@pytest.mark.asyncio
async def test_update_data_entry_not_found(db_session: AsyncSession):
    """Test updating a non-existent data entry returns None."""
    repo = DataEntryRepository(db_session)

    update_data = DataEntryUpdate(
        data_entry_type_id=DataEntryTypeEnum.plane.value,
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
        data_entry_type_id=DataEntryTypeEnum.plane,
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
            data_entry_type_id=DataEntryTypeEnum.plane,
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
async def test_bulk_insert_returning_ids_preserves_row_order(db_session: AsyncSession):
    """Returned ids must map back to ``rows`` in submitted order.

    Pins the API contract ``bulk_insert_returning_ids`` relies on
    (``sort_by_parameter_order=True`` on the Core INSERT's RETURNING) —
    without it, row/id ordering is implementation-defined per SQLAlchemy's
    own docs, not something to rely on even where it happens to hold in ad
    hoc testing (plan #2050 §C2/C3 follow-up, where this replaced per-row
    ``DataEntry(...)`` ORM construction for the Simulator Plan prefill copy
    path — a silent reorder here would misattribute one entry's data to
    another's id). Note: this specific test doesn't reproduce a failure
    without the flag on SQLite (small single-statement batches don't
    trigger reordering here) — it pins the contract, not an observed local
    bug; the flag was verified against real Postgres/psycopg separately.
    Uses a distinguishing marker per row rather than trusting sequential-id
    assumptions, so a genuine reorder would fail this even if ids still
    happened to come back sorted.
    """
    repo = DataEntryRepository(db_session)
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    rows = [
        {
            "data_entry_type_id": DataEntryTypeEnum.plane.value,
            "carbon_report_module_id": module.id,
            "data": {"marker": i},
            "status": DataEntryStatusEnum.PENDING,
            "year": None,
            "unit_id": None,
            "source": None,
            "created_by_id": None,
        }
        for i in range(20)
    ]

    ids = await repo.bulk_insert_returning_ids(rows)
    assert len(ids) == 20

    from sqlmodel import select

    stmt = select(DataEntry).where(DataEntry.id.in_(ids))
    by_id = {e.id: e.data["marker"] for e in (await db_session.exec(stmt)).all()}
    assert [by_id[row_id] for row_id in ids] == list(range(20))


@pytest.mark.asyncio
async def test_bulk_insert_returning_ids_empty_rows(db_session: AsyncSession):
    """No rows in, no round trip, empty list out."""
    repo = DataEntryRepository(db_session)
    assert await repo.bulk_insert_returning_ids([]) == []


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
    plane_entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane,
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

    db_session.add_all(plane_entries + [other_entry])
    await db_session.flush()

    # Bulk delete only plane entries
    await repo.bulk_delete(module.id, DataEntryTypeEnum.plane)
    await db_session.flush()

    # Verify plane entries are deleted
    from sqlmodel import select

    stmt = select(DataEntry).where(
        DataEntry.carbon_report_module_id == module.id,
        DataEntry.data_entry_type_id == DataEntryTypeEnum.plane.value,
    )
    result = await db_session.exec(stmt)
    remaining_plane = list(result.all())
    assert len(remaining_plane) == 0

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
            data_entry_type_id=DataEntryTypeEnum.plane,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}"},
        )
        for i in range(5)
    ]

    db_session.add_all(entries)
    await db_session.flush()

    result = await repo.get_total_count_by_submodule(module.id)

    assert DataEntryTypeEnum.plane.value in result
    assert result[DataEntryTypeEnum.plane.value] == 5


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
            data_entry_type_id=DataEntryTypeEnum.plane,
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
    plane_entries = [
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane,
            status=DataEntryStatusEnum.PENDING,
            data={"name": f"Trip {i}", "kg_co2eq": 100.0},
        )
        for i in range(3)
    ]

    db_session.add_all(plane_entries)
    await db_session.flush()

    result = await repo.get_total_per_field(
        "kg_co2eq", module.id, DataEntryTypeEnum.plane.value
    )

    # Only plane entries counted: 100 * 3 = 300
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
            data_entry_type_id=DataEntryTypeEnum.plane,
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

    assert str(DataEntryTypeEnum.plane.value) in result
    assert result[str(DataEntryTypeEnum.plane.value)] == pytest.approx(3.0, rel=0.01)


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


# ======================================================================
# get_stats_by_carbon_report_id Tests (FTE aggregation)
# ======================================================================


@pytest.mark.asyncio
async def test_get_headcount_members_returns_members_with_institutional_id(
    db_session: AsyncSession,
):
    """Members with a user_institutional_id are returned ordered by name."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=0,  # in_progress
    )
    db_session.add(module)
    await db_session.flush()
    if module.id is None:
        pytest.fail("Module ID should not be None after flush")
    db_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={"name": "Zara Ali", "user_institutional_id": "200002"},
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={"name": "Alice Dupont", "user_institutional_id": "100001"},
            ),
        ]
    )
    await db_session.flush()

    result = await repo.get_headcount_members(module.id)

    assert len(result) == 2
    # ordered by name ascending
    assert result[0]["name"] == "Alice Dupont"
    assert result[0]["institutional_id"] == "100001"
    assert result[1]["name"] == "Zara Ali"
    assert result[1]["institutional_id"] == "200002"


@pytest.mark.asyncio
async def test_get_headcount_members_excludes_entries_without_institutional_id(
    db_session: AsyncSession,
):
    """Members missing user_institutional_id are excluded from the result."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=0,  # in_progress
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={"name": "Alice Dupont", "user_institutional_id": "100001"},
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={"name": "No-ID Member"},
            ),
        ]
    )
    await db_session.flush()

    result = await repo.get_headcount_members(module.id)

    assert len(result) == 1
    assert result[0]["name"] == "Alice Dupont"


@pytest.mark.asyncio
async def test_get_headcount_members_excludes_non_member_types(
    db_session: AsyncSession,
):
    """Non-member data entries in the same module are not included."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=0,  # in_progress
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={"name": "Alice Dupont", "user_institutional_id": "100001"},
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.plane,
                data={"name": "Some Trip", "user_institutional_id": "999999"},
            ),
        ]
    )
    await db_session.flush()

    result = await repo.get_headcount_members(module.id)

    assert len(result) == 1
    assert result[0]["name"] == "Alice Dupont"


@pytest.mark.asyncio
async def test_get_headcount_members_empty_module(db_session: AsyncSession):
    """No entries → empty list."""
    repo = DataEntryRepository(db_session)
    result = await repo.get_headcount_members(99999)
    assert result == []


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_found(db_session: AsyncSession):
    """Returns the matching DataEntry when the institutional ID exists."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.member,
        data={"name": "Alice Dupont", "user_institutional_id": "100001"},
    )
    db_session.add(entry)
    await db_session.flush()

    result = await repo.get_member_by_institutional_id(module.id, "100001")

    assert result is not None
    assert result["institutional_id"] == "100001"
    assert result["name"] == "Alice Dupont"


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_not_found(db_session: AsyncSession):
    """Returns None when no entry matches the institutional ID."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    result = await repo.get_member_by_institutional_id(module.id, "999999")

    assert result is None


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_scoped_to_module(
    db_session: AsyncSession,
):
    """Does not return a match from a different module."""
    repo = DataEntryRepository(db_session)

    module_a = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    module_b = CarbonReportModule(
        carbon_report_id=2,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add_all([module_a, module_b])
    await db_session.flush()

    db_session.add(
        DataEntry(
            carbon_report_module_id=module_a.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            data={"name": "Alice Dupont", "user_institutional_id": "100001"},
        )
    )
    await db_session.flush()

    # Looking up from module_b should find nothing
    result = await repo.get_member_by_institutional_id(module_b.id, "100001")
    assert result is None


@pytest.mark.asyncio
async def test_get_member_by_institutional_id_ignores_non_member_types(
    db_session: AsyncSession,
):
    """A matching institutional_id on a non-member entry is not returned."""
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add(
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane,
            data={"name": "Alice Dupont", "user_institutional_id": "100001"},
        )
    )
    await db_session.flush()

    result = await repo.get_member_by_institutional_id(module.id, "100001")
    assert result is None


# ======================================================================
# list_by_data_entry_type_and_year Tests
# ======================================================================


@pytest.mark.asyncio
async def test_list_by_data_entry_type_and_year_matching_year(
    db_session: AsyncSession,
):
    """Entries from a CarbonReport with the matching year are returned."""
    repo = DataEntryRepository(db_session)

    project = CarbonProject(unit_id=1, carbon_report_type=CarbonReportType.CALCULATOR)
    db_session.add(project)
    await db_session.flush()
    report = CarbonReport(
        year=2025, unit_id=1, overall_status=0, carbon_project_id=project.id
    )
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={"name": "Trip A"},
    )
    db_session.add(entry)
    await db_session.flush()

    results = await repo.list_by_data_entry_type_and_year(DataEntryTypeEnum.plane, 2025)

    assert len(results) == 1
    assert results[0].id == entry.id
    assert results[0].data_entry_type_id == DataEntryTypeEnum.plane


@pytest.mark.asyncio
async def test_list_by_data_entry_type_and_year_non_matching_year(
    db_session: AsyncSession,
):
    """Entries from a CarbonReport with a different year are not returned."""
    repo = DataEntryRepository(db_session)

    project = CarbonProject(unit_id=1, carbon_report_type=CarbonReportType.CALCULATOR)
    db_session.add(project)
    await db_session.flush()
    report = CarbonReport(
        year=2025, unit_id=1, overall_status=0, carbon_project_id=project.id
    )
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add(
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane,
            status=DataEntryStatusEnum.PENDING,
            data={"name": "Trip A"},
        )
    )
    await db_session.flush()

    results = await repo.list_by_data_entry_type_and_year(DataEntryTypeEnum.plane, 2024)

    assert results == []


@pytest.mark.asyncio
async def test_list_by_data_entry_type_and_year_empty_result(
    db_session: AsyncSession,
):
    """Returns empty list when no data entries exist for the type/year."""
    repo = DataEntryRepository(db_session)

    results = await repo.list_by_data_entry_type_and_year(DataEntryTypeEnum.plane, 2025)

    assert results == []


@pytest.mark.asyncio
async def test_list_by_data_entry_type_and_year_filters_by_type(
    db_session: AsyncSession,
):
    """Only entries of the requested data_entry_type are returned."""
    repo = DataEntryRepository(db_session)

    project = CarbonProject(unit_id=1, carbon_report_type=CarbonReportType.CALCULATOR)
    db_session.add(project)
    await db_session.flush()
    report = CarbonReport(
        year=2025, unit_id=1, overall_status=0, carbon_project_id=project.id
    )
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add(
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane,
            status=DataEntryStatusEnum.PENDING,
            data={"name": "Plane Trip"},
        )
    )
    db_session.add(
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.train,
            status=DataEntryStatusEnum.PENDING,
            data={"name": "Train Trip"},
        )
    )
    await db_session.flush()

    results = await repo.list_by_data_entry_type_and_year(DataEntryTypeEnum.plane, 2025)

    assert len(results) == 1
    assert results[0].data_entry_type_id == DataEntryTypeEnum.plane


# ======================================================================
# Regression: read path must not persist computed fields back to data
# ======================================================================


@pytest.mark.asyncio
async def test_get_submodule_data_does_not_persist_computed_fields(
    db_session: AsyncSession,
):
    """``get_submodule_data`` must never write computed values (kg_co2eq,
    primary_factor, distance_km, traveler_name, room_surface_square_meter)
    back to the source-of-truth ``DataEntry.data`` JSON column.

    Pre-fix, the method reassigned ``data_entry.data = {...}`` on the loaded
    ORM row, which SQLAlchemy then flushed to the DB. This test fails on
    that buggy code and passes after Option 1 + Option 2 are applied.
    """
    from sqlmodel import select

    repo = DataEntryRepository(db_session)

    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    original_data = {
        "origin_iata": "GVA",
        "destination_iata": "ZRH",
        "cabin_class": "business",
        "user_institutional_id": "150322",
        "number_of_trips": 1,
        "primary_factor_id": None,
    }
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data=dict(original_data),
    )
    db_session.add(entry)
    await db_session.commit()
    entry_id = entry.id

    # Act: list the entries — pre-fix, this would mutate `data_entry.data`
    # in-memory and SQLAlchemy would flush the mutation on the next query.
    await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )
    await db_session.commit()
    db_session.expire_all()

    refreshed = (
        await db_session.execute(select(DataEntry).where(DataEntry.id == entry_id))
    ).scalar_one()

    # The JSON column must be byte-identical to the original input.
    assert refreshed.data == original_data
    for forbidden_key in (
        "kg_co2eq",
        "primary_factor",
        "traveler_name",
        "distance_km",
        "room_surface_square_meter",
    ):
        assert forbidden_key not in refreshed.data, (
            f"computed key {forbidden_key!r} leaked into DataEntry.data"
        )


@pytest.mark.asyncio
async def test_get_submodule_data_populates_reference_kg_for_snapshot_rows(
    db_session: AsyncSession,
):
    """Planner snapshot rows expose the source (reference-year) entry's summed
    emissions as ``reference_kg_co2eq`` — the 100% baseline the % slider scales
    from. Ordinary rows (no ``source_data_entry_id``) get ``None``.
    """
    repo = DataEntryRepository(db_session)

    # Reference-year Calculator entry with two emission leaves summing to 1000.
    ref_report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(ref_report)
    await db_session.flush()
    ref_module = CarbonReportModule(
        carbon_report_id=ref_report.id,
        module_type_id=ModuleTypeEnum.process_emissions.value,
        status="in_progress",
    )
    db_session.add(ref_module)
    await db_session.flush()
    source_entry = DataEntry(
        carbon_report_module_id=ref_module.id,
        data_entry_type_id=DataEntryTypeEnum.process_emissions,
        status=DataEntryStatusEnum.PENDING,
        data={"category": "Refrigerant", "subcategory": "NF3", "quantity_kg": 50},
        year=2025,
    )
    db_session.add(source_entry)
    await db_session.flush()
    db_session.add_all(
        [
            DataEntryEmission(
                data_entry_id=source_entry.id,
                emission_type_id=EmissionType.process_emissions__co2.value,
                kg_co2eq=600.0,
            ),
            DataEntryEmission(
                data_entry_id=source_entry.id,
                emission_type_id=EmissionType.process_emissions__n2o.value,
                kg_co2eq=400.0,
            ),
        ]
    )
    await db_session.flush()

    # Plan-year module with a snapshot row pointing at the source, plus a
    # normal (non-snapshot) row that must stay ``None``.
    plan_report = CarbonReport(
        year=2027, reference_year=2025, unit_id=1, overall_status=0
    )
    db_session.add(plan_report)
    await db_session.flush()
    plan_module = CarbonReportModule(
        carbon_report_id=plan_report.id,
        module_type_id=ModuleTypeEnum.process_emissions.value,
        status="in_progress",
    )
    db_session.add(plan_module)
    await db_session.flush()
    snapshot_entry = DataEntry(
        carbon_report_module_id=plan_module.id,
        data_entry_type_id=DataEntryTypeEnum.process_emissions,
        status=DataEntryStatusEnum.PENDING,
        data={
            "category": "Refrigerant",
            "subcategory": "NF3",
            "quantity_kg": 50,
            "source_data_entry_id": source_entry.id,
            "percentage_of_reference_year": 40,
        },
        year=2027,
    )
    plain_entry = DataEntry(
        carbon_report_module_id=plan_module.id,
        data_entry_type_id=DataEntryTypeEnum.process_emissions,
        status=DataEntryStatusEnum.PENDING,
        data={"category": "CH4", "quantity_kg": 65},
        year=2027,
    )
    db_session.add_all([snapshot_entry, plain_entry])
    await db_session.commit()

    response = await repo.get_submodule_data(
        carbon_report_module_id=plan_module.id,
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    by_id = {item.id: item for item in response.items}
    assert by_id[snapshot_entry.id].reference_kg_co2eq == 1000.0
    assert by_id[plain_entry.id].reference_kg_co2eq is None
    # The stored slider value is surfaced so the table reflects it on refetch.
    assert by_id[snapshot_entry.id].percentage_of_reference_year == 40
    assert by_id[plain_entry.id].percentage_of_reference_year is None


# ======================================================================
# Enrichment fallback: FactorResolver replaces the stored-id dereference
# (plan 1661) — the entry's classification is the source of truth, not a
# legacy ``data["primary_factor_id"]`` value.
# ======================================================================


async def _make_equipment_entry(
    db_session: AsyncSession,
    *,
    extra_data: dict | None = None,
    year: int | None = 2025,
) -> DataEntry:
    """Build an equipment entry with no emission rows, so
    ``get_submodule_data`` always falls through to the resolver.
    """
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    data = {"name": "Laptop", "equipment_class": "laptop", "sub_class": "13-inch"}
    if extra_data:
        data.update(extra_data)

    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        status=DataEntryStatusEnum.PENDING,
        data=data,
        year=year,
    )
    db_session.add(entry)
    await db_session.commit()
    return entry


async def _make_factor(
    db_session: AsyncSession,
    *,
    classification: dict,
    values: dict,
    year: int = 2025,
) -> Factor:
    factor = Factor(
        emission_type_id=EmissionType.equipment__scientific.value,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification=classification,
        values=values,
        year=year,
    )
    db_session.add(factor)
    await db_session.commit()
    return factor


@pytest.mark.asyncio
async def test_get_submodule_data_resolves_factor_from_classification_in_sql(
    db_session: AsyncSession,
):
    """An entry with a classification but NO emission rows gets its factor
    from the correlated SQL subquery — sort/filter/display all see it.
    """
    repo = DataEntryRepository(db_session)
    entry = await _make_equipment_entry(db_session)
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 42.0, "standby_power_w": 3.0},
    )

    response = await repo.get_submodule_data(
        carbon_report_module_id=entry.carbon_report_module_id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="active_power_w",
        sort_order="asc",
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.active_power_w == 42.0
    assert item.standby_power_w == 3.0


@pytest.mark.asyncio
async def test_get_submodule_data_ignores_legacy_stored_id_pointing_at_deleted_factor(
    db_session: AsyncSession,
):
    """A legacy ``data["primary_factor_id"]`` pointing at a deleted factor
    must never be dereferenced — the classification join wins, and no 500
    is raised chasing the stale id.
    """
    repo = DataEntryRepository(db_session)
    entry = await _make_equipment_entry(
        db_session, extra_data={"primary_factor_id": 999999}
    )
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 99.0, "standby_power_w": 9.0},
    )

    response = await repo.get_submodule_data(
        carbon_report_module_id=entry.carbon_report_module_id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.active_power_w == 99.0
    assert item.standby_power_w == 9.0


@pytest.mark.asyncio
async def test_get_submodule_data_year_none_yields_no_factor(
    db_session: AsyncSession,
):
    """An entry with ``year=None`` matches no factor (the join is
    year-equality-scoped), so factor-backed columns stay empty instead of
    resolving against the wrong year.
    """
    repo = DataEntryRepository(db_session)
    entry = await _make_equipment_entry(db_session, year=None)
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 42.0, "standby_power_w": 3.0},
    )

    response = await repo.get_submodule_data(
        carbon_report_module_id=entry.carbon_report_module_id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.active_power_w is None
    assert item.standby_power_w is None


@pytest.mark.asyncio
async def test_get_submodule_data_subkind_preference_ordering(
    db_session: AsyncSession,
):
    """The SQL join mirrors FactorResolver's chain: an exact
    ``(kind, subkind)`` row beats the subkind-less fallback row even when
    the fallback has a lower id; an unknown subkind falls back to the
    subkind-less row.
    """
    repo = DataEntryRepository(db_session)
    entry = await _make_equipment_entry(db_session)  # sub_class "13-inch"
    # Lower id: the kind-only fallback row. Higher id: the exact match.
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop"},
        values={"active_power_w": 1.0, "standby_power_w": 1.0},
    )
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 42.0, "standby_power_w": 3.0},
    )
    unknown_sub = await _make_equipment_entry(
        db_session, extra_data={"name": "Unknown", "sub_class": "17-inch"}
    )

    for module_id, expected_power, expected_name in (
        (entry.carbon_report_module_id, 42.0, "Laptop"),
        (unknown_sub.carbon_report_module_id, 1.0, "Unknown"),
    ):
        response = await repo.get_submodule_data(
            carbon_report_module_id=module_id,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            limit=10,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )
        assert len(response.items) == 1
        item = response.items[0]
        assert item.name == expected_name
        assert item.active_power_w == expected_power


@pytest.mark.asyncio
async def test_get_submodule_data_duplicate_factor_rows_resolve_deterministically(
    db_session: AsyncSession,
):
    """Duplicate factor generations (impossible in prod post-sweep, but
    seedable) must not 500 the page: the join picks the lowest id
    deterministically; other rows are unaffected.
    """
    repo = DataEntryRepository(db_session)
    entry = await _make_equipment_entry(db_session)
    first = await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 42.0, "standby_power_w": 3.0},
    )
    await _make_factor(
        db_session,
        classification={"equipment_class": "laptop", "sub_class": "13-inch"},
        values={"active_power_w": 777.0, "standby_power_w": 77.0},
    )
    assert first.id is not None

    response = await repo.get_submodule_data(
        carbon_report_module_id=entry.carbon_report_module_id,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.active_power_w == 42.0, "lowest factor id must win deterministically"


# ======================================================================
# Regression #1564 Part 2: travel<->headcount join must not fan out for a
# member holding multiple roles (sius_code) in the same unit.
# ======================================================================


@pytest.mark.asyncio
async def test_get_submodule_data_travel_not_duplicated_for_multi_role_member(
    db_session: AsyncSession,
):
    """A person can now legitimately have two headcount rows in the same
    unit (different sius_code, issue #1564 Part 1). The MemberEntry join
    used to fetch the traveler's display name must pick exactly one of
    those rows deterministically — not fan out and duplicate the travel
    entry once per matching role.
    """
    repo = DataEntryRepository(db_session)

    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Two headcount roles for the same person, same unit/module.
    db_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={
                    "name": "X X",
                    "user_institutional_id": "123456",
                    "sius_code": "53",
                },
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.member,
                data={
                    "name": "X X",
                    "user_institutional_id": "123456",
                    "sius_code": "54",
                },
            ),
        ]
    )
    await db_session.flush()

    travel_entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
            "cabin_class": "economy",
            "user_institutional_id": "123456",
            "number_of_trips": 1,
        },
    )
    db_session.add(travel_entry)
    await db_session.flush()
    assert travel_entry.id is not None
    db_session.add(
        DataEntryEmission(
            data_entry_id=travel_entry.id,
            emission_type_id=EmissionType.professional_travel__plane.value,
            kg_co2eq=100.0,
        )
    )
    await db_session.flush()

    response = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(response.items) == 1, (
        "a multi-role member's travel entry must appear exactly once, not "
        "once per matching headcount role"
    )
    assert response.summary.total_items == 1
    total_kg_co2eq = sum(item.kg_co2eq or 0 for item in response.items)
    assert total_kg_co2eq == pytest.approx(100.0), (
        "kg_co2eq must not be double-counted by the join fan-out"
    )


# ======================================================================
# Regression: _detach helper handles all session-state edge cases
# ======================================================================


@pytest.mark.asyncio
async def test_detach_handles_none_attached_and_already_detached(
    db_session: AsyncSession,
):
    """`_detach` must:
    - silently no-op on None entries (varargs may include unloaded joins),
    - successfully detach an attached ORM row,
    - swallow InvalidRequestError when an already-detached row is passed.

    Locks in the helper's contract so a future tightening of the except clause
    or removal of the None guard would be caught.
    """
    repo = DataEntryRepository(db_session)

    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={"origin_iata": "GVA"},
    )
    db_session.add(entry)
    await db_session.flush()

    # 1. None varargs are tolerated.
    repo._detach(None, None)

    # 2. An attached ORM instance is detached.
    assert entry in db_session.sync_session
    repo._detach(entry)
    assert entry not in db_session.sync_session

    # 3. A second call on the now-detached row swallows InvalidRequestError.
    repo._detach(entry)  # must not raise

    # 4. Mixed call (None + already-detached + freshly-loaded) all succeed.
    other = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={"origin_iata": "ZRH"},
    )
    db_session.add(other)
    await db_session.flush()
    repo._detach(None, entry, other)
    assert other not in db_session.sync_session


# ======================================================================
# Traveler sentinel resolution matrix (#1153, -1/null scheme)
# ======================================================================


def _plane_entry(module_id: int, sciper: str | None) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": sciper,
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
            "cabin_class": "economy",
        },
    )


def _member_entry(module_id: int, sciper: str | None, name: str) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.member,
        status=DataEntryStatusEnum.PENDING,
        data={
            "user_institutional_id": sciper,
            "name": name,
            "sius_code": "51",
            "fte": 1.0,
        },
    )


@pytest.mark.asyncio
async def test_traveler_resolution_matrix(db_session: AsyncSession):
    """PRD §4 matrix, driven through the real get_submodule_data query.

    Every row must round-trip its stored user_institutional_id unchanged
    (never overwritten by the resolver), regardless of whether a Headcount
    match exists.

    traveler_name's resolution *outcome* isn't independently observable
    here: ProfessionalTravelPlaneHandlerResponse doesn't declare that field,
    so model_validate silently drops it before it ever reaches
    response.items. The "NULL = NULL never spuriously matches" property is
    ANSI SQL three-valued-logic semantics (a database-engine guarantee, not
    application logic) — this test can't and doesn't need to re-verify it
    beyond confirming the query doesn't crash when a second NULL-valued
    member row exists (see the module_a member seed below).
    """
    repo = DataEntryRepository(db_session)

    module_a = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    module_b = CarbonReportModule(
        carbon_report_id=2,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module_a)
    db_session.add(module_b)
    await db_session.flush()

    # Headcount: "123456" is a member of module_a's report only.
    db_session.add(_member_entry(module_a.id, "123456", "Ada Lovelace"))
    # A second module_a member with no SCIPER yet (#951 made it optional).
    # Guards against NULL-fan-out/crash risk: the correlated subquery's
    # .limit(1) exists so that if a driver/dialect ever treated
    # NULL = NULL as true, matching >1 row would raise "more than one row
    # returned by a subquery used as an expression" instead of silently
    # mis-resolving a name. Not a name-resolution check (unobservable here).
    db_session.add(_member_entry(module_a.id, None, "No Sciper Yet"))
    # A different unit/year's Headcount also has "999999" — must NOT resolve
    # to module_a's travel row with the same SCIPER (unit isolation, PRD §4).
    db_session.add(_member_entry(module_b.id, "999999", "Wrong Unit Person"))
    await db_session.flush()

    rows = {
        "matched": _plane_entry(module_a.id, "123456"),
        "external": _plane_entry(module_a.id, None),
        "internal_explicit": _plane_entry(module_a.id, TRAVELER_OTHER_INTERNAL),
        "unresolved_source_id": _plane_entry(module_a.id, "45005"),
        "wrong_unit_match": _plane_entry(module_a.id, "999999"),
    }
    for entry in rows.values():
        db_session.add(entry)
    await db_session.flush()

    response = await repo.get_submodule_data(
        carbon_report_module_id=module_a.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    by_id = {item.id: item for item in response.items}

    # Every stored value survives unchanged — resolution never rewrites data.
    assert by_id[rows["matched"].id].user_institutional_id == "123456"
    assert by_id[rows["external"].id].user_institutional_id is None
    assert (
        by_id[rows["internal_explicit"].id].user_institutional_id
        == TRAVELER_OTHER_INTERNAL
    )
    assert by_id[rows["unresolved_source_id"].id].user_institutional_id == "45005"
    assert by_id[rows["wrong_unit_match"].id].user_institutional_id == "999999"


# ======================================================================
# #2050 Track H — planner_headcount missing from is_headcount_entry
# ======================================================================


@pytest.mark.asyncio
async def test_get_submodule_data_planner_headcount_uses_rollup_total(
    db_session: AsyncSession,
):
    """planner_headcount must read its total from the rollup row (the fast
    path member/student already use), not by summing the individual leaves
    itself (the slow, unfiltered ``else``-branch path — 825ms in production
    at real volume, #2050 Track H).

    In real data the rollup row's value always equals the sum of its
    leaves (``prepare_create`` computes it that way), so a realistic seed
    can't distinguish "which query ran" by value alone — both paths would
    happen to agree. This test deliberately seeds a rollup row whose value
    does NOT match the sum of its leaves, so the two candidate code paths
    diverge observably: reading the rollup row directly returns 99.0/factor
    42; re-summing the three leaves would return 18.0/factor 1. Before the
    fix (``is_headcount_entry`` missing ``planner_headcount``), this test
    fails with 18.0 — pinning that the *shape* of the query changed, not
    just that some number came back.
    """
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.planner_headcount,
        status=DataEntryStatusEnum.VALIDATED,
        data={"sius_code": "51", "fte": 2.0},
    )
    db_session.add(entry)
    await db_session.flush()

    leaves = [
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.food.value,
            kg_co2eq=10.0,
            primary_factor_id=1,
            scope=emission_type_scope(EmissionType.food),
        ),
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.waste.value,
            kg_co2eq=5.0,
            primary_factor_id=1,
            scope=emission_type_scope(EmissionType.waste),
        ),
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.commuting.value,
            kg_co2eq=3.0,
            primary_factor_id=1,
            scope=emission_type_scope(EmissionType.commuting),
        ),
        # The rollup row prepare_create already writes for this type today
        # (DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION already maps planner_headcount
        # -> EmissionType.headcount). Deliberately mismatched vs the leaves'
        # sum/factor — see docstring — to make the test discriminating.
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.headcount.value,
            kg_co2eq=99.0,
            primary_factor_id=42,
            scope=None,
            meta={"is_rollup": True},
        ),
    ]
    db_session.add_all(leaves)
    await db_session.flush()

    repo = DataEntryRepository(db_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.planner_headcount.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.kg_co2eq == pytest.approx(99.0)
    # kg_co2eq is the only assertable difference: is_headcount_entry is read
    # twice, so the fix also stops resolved_factor_id being computed here —
    # but PlannerHeadCountResponse exposes no factor field, so that second
    # dispatch has nothing observable to change. (It would be equivalent
    # anyway: the rollup row's primary_factor_id is min(leaf factor ids),
    # exactly what the generic path's func.min(primary_factor_id) produced.)


# ======================================================================
# #2050 Track J lever 2 — one query where the route made three
# ======================================================================


@pytest.mark.asyncio
async def test_get_headcount_fte_breakdown_matches_the_three_queries_it_replaces(
    db_session: AsyncSession,
):
    """The headcount branch of ``GET .../modules/{module_id}`` issued three
    sequential round trips over the same table, same module and same
    ``fte`` field: total FTE, member FTE grouped by sius_code, and student
    FTE. On dev each round trip costs ~160ms (#2050 G2), so the count is
    the cost, not the queries themselves.

    Asserted as equivalence against the three calls it replaces rather
    than against hand-written expected values: that is what makes it a
    safe swap, and it cannot drift if either side changes.
    """
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    # Two sius_codes for members, one student, plus an entry with no
    # sius_code at all (get_stats labels that group "unknown") and one
    # with no fte (a NULL that must not become 0.0 silently).
    seed = [
        (DataEntryTypeEnum.member, {"sius_code": "51", "fte": 2.0}),
        (DataEntryTypeEnum.member, {"sius_code": "51", "fte": 3.5}),
        (DataEntryTypeEnum.member, {"sius_code": "62", "fte": 1.25}),
        (DataEntryTypeEnum.member, {"fte": 4.0}),
        (DataEntryTypeEnum.student, {"sius_code": "51", "fte": 7.0}),
        (DataEntryTypeEnum.student, {"sius_code": "51"}),
    ]
    for data_entry_type, data in seed:
        db_session.add(
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=data_entry_type,
                status=DataEntryStatusEnum.VALIDATED,
                data=data,
            )
        )
    await db_session.flush()

    repo = DataEntryRepository(db_session)

    expected_total = await repo.get_total_per_field(
        field_name="fte",
        carbon_report_module_id=module.id,
        data_entry_type_id=None,
    )
    expected_member_stats = await repo.get_stats(
        carbon_report_module_id=module.id,
        aggregate_by="sius_code",
        aggregate_field="fte",
        data_entry_type_id=DataEntryTypeEnum.member.value,
    )
    expected_student_total = await repo.get_total_per_field(
        field_name="fte",
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.student.value,
    )

    breakdown = await repo.get_headcount_fte_breakdown(
        carbon_report_module_id=module.id
    )

    assert breakdown.total_fte == pytest.approx(expected_total)
    assert breakdown.student_fte == pytest.approx(expected_student_total)
    assert breakdown.member_fte_by_sius_code == expected_member_stats
    # Guard against the equivalence passing vacuously on empty results.
    assert breakdown.total_fte > 0
    assert set(breakdown.member_fte_by_sius_code) == {"51", "62", "unknown"}


@pytest.mark.asyncio
async def test_get_headcount_fte_breakdown_sorts_other_staff_last(
    db_session: AsyncSession,
):
    """#2254: dict order is the chart's bar order — codes ascending, with
    the "Other staff" sentinel (-1) last, so it cannot land before 51
    by numeric accident or GROUP BY whim.
    """
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    seed = [
        (DataEntryTypeEnum.member, {"sius_code": "-1", "fte": 0.5}),
        (DataEntryTypeEnum.member, {"sius_code": "59", "fte": 1.0}),
        (DataEntryTypeEnum.member, {"sius_code": "51", "fte": 2.0}),
        (DataEntryTypeEnum.member, {"sius_code": "-1", "fte": 0.25}),
    ]
    for data_entry_type, data in seed:
        db_session.add(
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=data_entry_type,
                status=DataEntryStatusEnum.VALIDATED,
                data=data,
            )
        )
    await db_session.flush()

    breakdown = await DataEntryRepository(db_session).get_headcount_fte_breakdown(
        carbon_report_module_id=module.id
    )

    assert list(breakdown.member_fte_by_sius_code) == ["51", "59", "-1"]
    assert breakdown.member_fte_by_sius_code["-1"] == pytest.approx(0.75)
