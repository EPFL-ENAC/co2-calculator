"""Unit tests for equipment repository functions."""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry_type import DataEntryTypeEnum
from app.models.emission_factor import EmissionFactor, PowerFactor
from app.models.equipment import Equipment, EquipmentEmission
from app.repositories import equipment_repo


@pytest_asyncio.fixture
async def emission_factor(db_session: AsyncSession):
    """Create a sample emission factor."""
    factor = EmissionFactor(
        factor_name="swiss_electricity_mix",
        value=0.125,
        version=1,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        region="CH",
        source="Test data",
        factor_metadata={},
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


@pytest_asyncio.fixture
async def power_factor(db_session: AsyncSession):
    """Create a sample power factor."""
    factor = PowerFactor(
        submodule="scientific",
        equipment_class="Centrifugation",
        sub_class="Ultra centrifuges",
        active_power_w=1300.0,
        standby_power_w=130.0,
        version=1,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        source="Test data",
        power_metadata={},
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


@pytest_asyncio.fixture
async def sample_equipment_with_emissions(
    db_session: AsyncSession, emission_factor, power_factor
):
    """Create sample equipment items with emissions."""
    equipment_list = [
        # Scientific equipment
        Equipment(
            cost_center="C1348",
            cost_center_description="Test Lab",
            name="Ultra Centrifuge 1",
            category="Scientific equipment",
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class="Ultra centrifuges",
            status="In service",
            active_usage_pct=20.0,
            passive_usage_pct=80.0,
            active_power_w=1300.0,
            standby_power_w=130.0,
            unit_id="TEST-UNIT-1",
            equipment_metadata={},
        ),
        Equipment(
            cost_center="C1348",
            cost_center_description="Test Lab",
            name="Microscope 1",
            category="Scientific equipment",
            submodule="scientific",
            equipment_class="Microscopy",
            status="In service",
            active_usage_pct=30.0,
            passive_usage_pct=70.0,
            active_power_w=500.0,
            standby_power_w=50.0,
            unit_id="TEST-UNIT-1",
            equipment_metadata={},
        ),
        # IT equipment
        Equipment(
            cost_center="C1349",
            cost_center_description="IT Department",
            name="Workstation 1",
            category="IT equipment",
            submodule="it",
            equipment_class="Desktop Computers",
            status="In service",
            active_usage_pct=40.0,
            passive_usage_pct=60.0,
            active_power_w=200.0,
            standby_power_w=20.0,
            unit_id="TEST-UNIT-2",
            equipment_metadata={},
        ),
        # Decommissioned equipment
        Equipment(
            cost_center="C1348",
            cost_center_description="Test Lab",
            name="Old Equipment",
            category="Scientific equipment",
            submodule="scientific",
            equipment_class="Other",
            status="Decommissioned",
            active_usage_pct=0.0,
            passive_usage_pct=0.0,
            active_power_w=100.0,
            standby_power_w=10.0,
            unit_id="TEST-UNIT-1",
            equipment_metadata={},
        ),
    ]

    for equip in equipment_list:
        db_session.add(equip)
    await db_session.commit()

    # Add emissions for each equipment
    for equip in equipment_list:
        await db_session.refresh(equip)
        emission = EquipmentEmission(
            equipment_id=equip.id,
            annual_kwh=1000.0,
            kg_co2eq=125.0,
            emission_factor_id=emission_factor.id,
            power_factor_id=(
                power_factor.id if equip.submodule == "scientific" else None
            ),
            formula_version="v1_linear",
            calculation_inputs={},
            is_current=True,
        )
        db_session.add(emission)

    await db_session.commit()

    return equipment_list


class TestGetEquipmentWithEmissions:
    """Tests for get_equipment_with_emissions function."""

    @pytest.mark.asyncio
    async def test_get_all_equipment(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test getting all equipment with emissions."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service"
        )

        assert total == 3  # 3 in service items
        assert len(result) == 3
        for equip, emission, *_ in result:
            assert isinstance(equip, Equipment)
            assert isinstance(emission, EquipmentEmission)
            assert emission.is_current is True

    @pytest.mark.asyncio
    async def test_filter_by_unit_id(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test filtering equipment by unit_id."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, unit_id="TEST-UNIT-1", status="In service"
        )

        assert total == 2  # 2 items in TEST-UNIT-1
        assert len(result) == 2
        for equip, emission, *_ in result:
            assert equip.unit_id == "TEST-UNIT-1"

    @pytest.mark.asyncio
    async def test_filter_by_submodule(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test filtering equipment by submodule."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, submodule_key=DataEntryTypeEnum.scientific, status="In service"
        )

        assert total == 2  # 2 scientific items
        assert len(result) == 2
        for equip, emission, *_ in result:
            assert equip.submodule == "scientific"

    @pytest.mark.asyncio
    async def test_filter_by_status(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test filtering equipment by status."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, status="Decommissioned"
        )

        assert total == 1
        assert len(result) == 1
        assert result[0][0].status == "Decommissioned"

    @pytest.mark.asyncio
    async def test_pagination_limit(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test pagination with limit."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service", limit=2, offset=0
        )

        assert total == 3  # Total count
        assert len(result) == 2  # Limited to 2

    @pytest.mark.asyncio
    async def test_pagination_offset(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test pagination with offset."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service", limit=2, offset=2
        )

        assert total == 3
        assert len(result) == 1  # Only 1 item left after offset

    @pytest.mark.asyncio
    async def test_combined_filters(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test combining multiple filters."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session,
            unit_id="TEST-UNIT-1",
            submodule_key=DataEntryTypeEnum.scientific.value,
            status="In service",
        )

        assert total == 2
        assert len(result) == 2
        for equip, emission, *_ in result:
            assert equip.unit_id == "TEST-UNIT-1"
            assert equip.submodule == "scientific"
            assert equip.status == "In service"

    @pytest.mark.asyncio
    async def test_empty_result(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test query with no matching results."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, unit_id="NONEXISTENT"
        )

        assert total == 0
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_ordering_by_equipment_class(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test that results are ordered by equipment_class."""
        result, total = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service"
        )

        # Check ordering
        classes = [equip.equipment_class for equip, *_ in result]
        assert classes == sorted(classes)


class TestGetEquipmentSummaryBySubmodule:
    """Tests for get_equipment_summary_by_submodule function."""

    @pytest.mark.asyncio
    async def test_summary_all_equipment(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test getting summary for all equipment."""
        summary = await equipment_repo.get_equipment_summary_by_submodule(
            db_session, status="In service"
        )

        assert DataEntryTypeEnum.scientific.value in summary
        assert DataEntryTypeEnum.it.value in summary
        assert summary[DataEntryTypeEnum.scientific.value]["total_items"] == 2
        assert summary[DataEntryTypeEnum.it.value]["total_items"] == 1

    @pytest.mark.asyncio
    async def test_summary_aggregation(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test that aggregation values are correct."""
        summary = await equipment_repo.get_equipment_summary_by_submodule(
            db_session, status="In service"
        )

        # Check structure
        for submodule, stats in summary.items():
            assert "total_items" in stats
            assert "annual_consumption_kwh" in stats
            assert "total_kg_co2eq" in stats
            assert isinstance(stats["total_items"], int)
            assert isinstance(stats["annual_consumption_kwh"], float)
            assert isinstance(stats["total_kg_co2eq"], float)

    @pytest.mark.asyncio
    async def test_summary_filter_by_unit(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test summary filtered by unit_id."""
        summary = await equipment_repo.get_equipment_summary_by_submodule(
            db_session, unit_id="TEST-UNIT-1", status="In service"
        )

        assert DataEntryTypeEnum.scientific.value in summary
        assert summary[DataEntryTypeEnum.scientific.value]["total_items"] == 2
        assert (
            DataEntryTypeEnum.it.value not in summary
        )  # IT equipment is in different unit

    @pytest.mark.asyncio
    async def test_summary_filter_by_status(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test summary filtered by status."""
        summary = await equipment_repo.get_equipment_summary_by_submodule(
            db_session, status="Decommissioned"
        )

        assert DataEntryTypeEnum.scientific.value in summary
        assert summary[DataEntryTypeEnum.scientific.value]["total_items"] == 1

    @pytest.mark.asyncio
    async def test_summary_empty_result(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test summary with no matching equipment."""
        summary = await equipment_repo.get_equipment_summary_by_submodule(
            db_session, unit_id="NONEXISTENT"
        )

        assert summary == {}


class TestGetCurrentEmissionFactor:
    """Tests for get_current_emission_factor function."""

    @pytest.mark.asyncio
    async def test_get_current_factor(self, db_session: AsyncSession, emission_factor):
        """Test getting current emission factor."""
        result = await equipment_repo.get_current_emission_factor(
            db_session, "swiss_electricity_mix"
        )

        assert result is not None
        factor_id, factor_value = result
        assert factor_id == emission_factor.id
        assert factor_value == 0.125

    @pytest.mark.asyncio
    async def test_get_factor_nonexistent(self, db_session: AsyncSession):
        """Test getting non-existent emission factor."""
        result = await equipment_repo.get_current_emission_factor(
            db_session, "nonexistent_factor"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_factor_prefers_latest_version(self, db_session: AsyncSession):
        """Test that latest version is returned when multiple exist."""
        # Add multiple versions
        factors = [
            EmissionFactor(
                factor_name="test_factor",
                value=0.100,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=datetime(2024, 12, 31),
                region="CH",
                source="Test",
                factor_metadata={},
            ),
            EmissionFactor(
                factor_name="test_factor",
                value=0.110,
                version=2,
                valid_from=datetime(2025, 1, 1),
                valid_to=None,  # Current version
                region="CH",
                source="Test",
                factor_metadata={},
            ),
        ]
        for factor in factors:
            db_session.add(factor)
        await db_session.commit()

        result = await equipment_repo.get_current_emission_factor(
            db_session, "test_factor"
        )

        assert result is not None
        _, factor_value = result
        assert factor_value == 0.110  # Latest version

    @pytest.mark.asyncio
    async def test_get_factor_only_current(self, db_session: AsyncSession):
        """Test that only factors with valid_to=None are returned."""
        # Add factor with valid_to set (not current)
        factor = EmissionFactor(
            factor_name="old_factor",
            value=0.100,
            version=1,
            valid_from=datetime(2023, 1, 1),
            valid_to=datetime(2023, 12, 31),
            region="CH",
            source="Test",
            factor_metadata={},
        )
        db_session.add(factor)
        await db_session.commit()

        result = await equipment_repo.get_current_emission_factor(
            db_session, "old_factor"
        )

        assert result is None


class TestRetireCurrentEmission:
    """Tests for retire_current_emission function."""

    @pytest.mark.asyncio
    async def test_retire_emission(
        self, db_session: AsyncSession, sample_equipment_with_emissions
    ):
        """Test retiring current emission."""
        equipment = sample_equipment_with_emissions[0]

        # Verify current emission exists
        result, _ = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service", limit=1
        )
        assert result[0][1].is_current is True

        # Retire it
        await equipment_repo.retire_current_emission(db_session, equipment.id)

        # Verify it's no longer current
        result, _ = await equipment_repo.get_equipment_with_emissions(
            db_session, status="In service", limit=1
        )
        # Should not find any current emissions for this equipment now
        assert len(result) == 0 or result[0][0].id != equipment.id

    @pytest.mark.asyncio
    async def test_retire_nonexistent_emission(self, db_session: AsyncSession):
        """Test retiring emission for equipment with no current emission."""
        # Should not raise an error
        await equipment_repo.retire_current_emission(db_session, 99999)


class TestInsertEmission:
    """Tests for insert_emission function."""

    @pytest.mark.asyncio
    async def test_insert_emission(
        self,
        db_session: AsyncSession,
        sample_equipment_with_emissions,
        emission_factor,
    ):
        """Test inserting new emission record."""
        equipment = sample_equipment_with_emissions[0]

        # First retire current emission
        await equipment_repo.retire_current_emission(db_session, equipment.id)

        # Insert new emission
        payload = {
            "annual_kwh": 1500.0,
            "kg_co2eq": 187.5,
            "emission_factor_id": emission_factor.id,
            "power_factor_id": None,
            "formula_version": "v2_updated",
            "calculation_inputs": {"test": "data"},
        }

        new_emission = await equipment_repo.insert_emission(
            db_session, equipment.id, payload
        )

        assert new_emission is not None
        assert new_emission.equipment_id == equipment.id
        assert new_emission.annual_kwh == 1500.0
        assert new_emission.kg_co2eq == 187.5
        assert new_emission.is_current is True
        assert new_emission.formula_version == "v2_updated"
        assert new_emission.calculation_inputs == {"test": "data"}

    @pytest.mark.asyncio
    async def test_insert_emission_with_defaults(
        self,
        db_session: AsyncSession,
        sample_equipment_with_emissions,
        emission_factor,
    ):
        """Test inserting emission with default values."""
        equipment = sample_equipment_with_emissions[0]

        # Minimal payload
        payload = {
            "annual_kwh": 1200.0,
            "kg_co2eq": 150.0,
            "emission_factor_id": emission_factor.id,
        }

        new_emission = await equipment_repo.insert_emission(
            db_session, equipment.id, payload
        )

        assert new_emission.formula_version == "v1_linear"  # Default
        assert new_emission.calculation_inputs == {}  # Default
        assert new_emission.power_factor_id is None

    @pytest.mark.asyncio
    async def test_insert_emission_multiple_for_same_equipment(
        self,
        db_session: AsyncSession,
        sample_equipment_with_emissions,
        emission_factor,
    ):
        """Test inserting multiple emissions for same equipment."""
        equipment = sample_equipment_with_emissions[0]

        # Retire first
        await equipment_repo.retire_current_emission(db_session, equipment.id)

        # Insert first new emission
        payload1 = {
            "annual_kwh": 1000.0,
            "kg_co2eq": 125.0,
            "emission_factor_id": emission_factor.id,
        }
        await equipment_repo.insert_emission(db_session, equipment.id, payload1)

        # Retire and insert second
        await equipment_repo.retire_current_emission(db_session, equipment.id)
        payload2 = {
            "annual_kwh": 1100.0,
            "kg_co2eq": 137.5,
            "emission_factor_id": emission_factor.id,
        }
        emission2 = await equipment_repo.insert_emission(
            db_session, equipment.id, payload2
        )

        # Verify only the second is current
        result, _ = await equipment_repo.get_equipment_with_emissions(
            db_session, limit=100
        )

        current_emissions_for_equipment = [
            e for eq, e, *_ in result if eq.id == equipment.id
        ]
        assert len(current_emissions_for_equipment) == 1
        assert current_emissions_for_equipment[0].id == emission2.id
        assert current_emissions_for_equipment[0].is_current is True
