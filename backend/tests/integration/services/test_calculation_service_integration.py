"""Integration tests for CO2 calculation service.

Tests cover:
- End-to-end calculation flows with realistic data
- Integration with database fixtures for emission factors
- Aggregation across multiple equipment items and submodules
- Calculation accuracy with reference values
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.services.calculation_service import (
    calculate_equipment_co2,
    calculate_equipment_emission_versioned,
    calculate_module_totals,
    calculate_submodule_summary,
    enrich_item_with_calculations,
)


@pytest_asyncio.fixture
async def emission_factor_swiss(db_session: AsyncSession):
    """Create Swiss electricity mix emission factor for testing."""
    factor = EmissionFactor(
        factor_name="swiss_electricity_mix",
        value=0.125,
        version=1,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        region="CH",
        source="Swiss Federal Office of Energy",
        factor_metadata={
            "description": "Swiss electricity consumption mix",
            "unit": "kgCO2eq/kWh",
        },
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


@pytest_asyncio.fixture
async def emission_factor_eu(db_session: AsyncSession):
    """Create EU electricity mix emission factor for testing."""
    factor = EmissionFactor(
        factor_name="eu_electricity_mix",
        value=0.275,
        version=1,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        region="EU",
        source="European Environment Agency",
        factor_metadata={
            "description": "EU average electricity consumption mix",
            "unit": "kgCO2eq/kWh",
        },
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


class TestCalculationWithRealisticData:
    """Test calculations with realistic equipment data."""

    def test_desktop_computer_typical_usage(self):
        """Test CO2 calculation for a typical desktop computer.

        Scenario: Office desktop computer
        - Usage: 8 hours/day active (23.8%), 16 hours/day standby (76.2%)
        - Active power: 100W, Standby power: 5W
        - Swiss electricity mix: 0.125 kgCO2eq/kWh
        """
        # 40 hrs active (23.8%), 128 hrs standby per week (76.2%)
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected annual consumption: 241.28 kWh
        # Expected annual emissions: 30.16 kgCO2eq
        assert result == 30.16

    def test_laptop_mobile_usage(self):
        """Test CO2 calculation for a laptop with mobile usage pattern.

        Scenario: Mobile laptop
        - Usage: 4 hours/day active (16.7%), 2 hours/day standby (8.3%)
        - Active power: 45W, Standby power: 2W
        - Swiss electricity mix: 0.125 kgCO2eq/kWh
        """
        result = calculate_equipment_co2(
            act_usage_hrs_wk=28.0,  # 4 hrs/day
            pas_usage_hrs_wk=14.0,  # 2 hrs/day
            act_power_w=45.0,
            pas_power_w=2.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: ~8.37 kgCO2eq/year
        assert result == 8.37

    def test_server_24_7_operation(self):
        """Test CO2 calculation for a server running 24/7.

        Scenario: Always-on server
        - Usage: 24/7 active operation
        - Active power: 300W, No standby
        - Swiss electricity mix: 0.125 kgCO2eq/kWh
        """
        result = calculate_equipment_co2(
            act_usage_hrs_wk=168.0,  # 24/7
            pas_usage_hrs_wk=0.0,
            act_power_w=300.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: 300W * 168hrs * 52wks / 1000 * 0.125 = 327.6 kgCO2eq
        assert result == 327.6

    def test_monitor_energy_saving(self):
        """Test CO2 calculation for monitor with energy-saving mode.

        Scenario: Office monitor with aggressive sleep mode
        - Usage: 8 hours/day active (23.8%), 16 hours/day sleep (76.2%)
        - Active power: 35W, Sleep power: 0.5W
        - Swiss electricity mix: 0.125 kgCO2eq/kWh
        """
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=35.0,
            pas_power_w=0.5,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: ~9.52 kgCO2eq/year
        assert result == 9.52


class TestCalculationWithDifferentEmissionFactors:
    """Test calculations with different emission factors."""

    def test_swiss_vs_eu_emission_factor(self):
        """Compare CO2 emissions using Swiss vs EU electricity mix."""
        equipment_params = {
            "act_usage_hrs_wk": 40.0,
            "pas_usage_hrs_wk": 128.0,
            "act_power_w": 100.0,
            "pas_power_w": 5.0,
            "status": "In service",
        }

        swiss_emissions = calculate_equipment_co2(
            **equipment_params, emission_factor=0.125
        )
        eu_emissions = calculate_equipment_co2(
            **equipment_params, emission_factor=0.275
        )

        # EU mix should produce 2.2x more emissions (0.275/0.125)
        assert swiss_emissions == 30.16
        assert eu_emissions == 66.35
        assert pytest.approx(eu_emissions / swiss_emissions, rel=0.01) == 2.2

    def test_renewable_energy_scenario(self):
        """Test CO2 calculation with renewable energy (low emission factor)."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.02,  # Very low (mostly renewable)
            status="In service",
        )

        # Expected: 241.28 kWh * 0.02 = 4.83 kgCO2eq
        assert result == 4.83

    def test_coal_heavy_grid_scenario(self):
        """Test CO2 calculation with coal-heavy grid (high emission factor)."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.8,  # High (coal-dominated)
            status="In service",
        )

        # Expected: 241.28 kWh * 0.8 = 193.02 kgCO2eq
        assert result == 193.02


class TestSubmoduleAndModuleAggregation:
    """Test aggregation across multiple equipment items and submodules."""

    def test_desktop_computers_submodule(self):
        """Test aggregation for a submodule of desktop computers."""
        # Create realistic equipment items
        items = [
            {
                "id": 1,
                "name": "Desktop 1",
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
            },
            {
                "id": 2,
                "name": "Desktop 2",
                "act_usage": 30,
                "pas_usage": 70,
                "act_power": 120,
                "pas_power": 6,
                "kg_co2eq": 41.46,
            },
            {
                "id": 3,
                "name": "Desktop 3",
                "act_usage": 20,
                "pas_usage": 80,
                "act_power": 90,
                "pas_power": 4,
                "kg_co2eq": 25.54,
            },
        ]

        summary = calculate_submodule_summary(items, emission_factor=0.125)

        assert summary["total_items"] == 3
        assert summary["total_kg_co2eq"] == 98.39
        assert summary["annual_consumption_kwh"] == 570.44  # 251.16 + 209.04 + 110.24

    def test_complete_module_with_multiple_submodules(self):
        """Test complete module calculation with realistic submodule structure."""
        submodules = {
            "desktop_computers": {
                "items": [],
                "summary": {
                    "total_items": 25,
                    "annual_consumption_kwh": 6279.0,  # 25 * 251.16
                    "total_kg_co2eq": 784.75,  # 25 * 31.39
                },
            },
            "laptops": {
                "items": [],
                "summary": {
                    "total_items": 50,
                    "annual_consumption_kwh": 3276.0,  # 50 * 65.52
                    "total_kg_co2eq": 409.5,  # 50 * 8.19
                },
            },
            "monitors": {
                "items": [],
                "summary": {
                    "total_items": 40,
                    "annual_consumption_kwh": 3014.4,  # 40 * 75.36
                    "total_kg_co2eq": 376.8,  # 40 * 9.42
                },
            },
            "servers": {
                "items": [],
                "summary": {
                    "total_items": 5,
                    "annual_consumption_kwh": 1638.0,  # 5 * 327.6
                    "total_kg_co2eq": 1638.0,  # 5 * 327.6
                },
            },
        }

        totals = calculate_module_totals(submodules)

        assert totals["total_submodules"] == 4
        assert totals["total_items"] == 120
        assert totals["total_annual_consumption_kwh"] == 14207.4
        assert totals["total_kg_co2eq"] == 3209.05

    def test_mixed_status_equipment_aggregation(self):
        """Test aggregation with mixed equipment statuses."""
        items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
                "status": "In service",
            },
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 0.0,  # Not in service
                "status": "Decommissioned",
            },
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
                "status": "In service",
            },
        ]

        summary = calculate_submodule_summary(items, emission_factor=0.125)

        # Only 2 items contribute to emissions
        assert summary["total_items"] == 3
        assert summary["total_kg_co2eq"] == 62.78


class TestVersionedCalculationIntegration:
    """Test versioned calculation with database integration."""

    @pytest.mark.asyncio
    async def test_versioned_calculation_with_db_emission_factor(
        self, emission_factor_swiss: EmissionFactor
    ):
        """Test versioned calculation using emission factor from database."""

        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "active_power_w": 100,
            "standby_power_w": 5,
            "status": "In service",
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=emission_factor_swiss.value,
            emission_factor_id=emission_factor_swiss.id,
            formula_version="v1_linear",
        )

        assert result["annual_kwh"] == 251.16
        assert result["kg_co2eq"] == 31.39
        assert result["emission_factor_id"] == emission_factor_swiss.id
        assert result["formula_version"] == "v1_linear"
        assert result["calculation_inputs"]["emission_factor"] == 0.125

    @pytest.mark.asyncio
    async def test_versioned_calculation_different_emission_factors(
        self, emission_factor_swiss: EmissionFactor, emission_factor_eu: EmissionFactor
    ):
        """Test versioned calculations with different emission factors."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "active_power_w": 100,
            "standby_power_w": 5,
            "status": "In service",
        }

        # Calculate with Swiss factor
        swiss_result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=emission_factor_swiss.value,
            emission_factor_id=emission_factor_swiss.id,
        )

        # Calculate with EU factor
        eu_result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=emission_factor_eu.value,
            emission_factor_id=emission_factor_eu.id,
        )

        # Energy consumption should be the same
        assert swiss_result["annual_kwh"] == eu_result["annual_kwh"] == 251.16

        # Emissions should differ based on emission factor
        assert swiss_result["kg_co2eq"] == 31.39  # 0.125 factor
        assert eu_result["kg_co2eq"] == 69.07  # 0.275 factor

        # Verify correct factor IDs are stored
        assert swiss_result["emission_factor_id"] == emission_factor_swiss.id
        assert eu_result["emission_factor_id"] == emission_factor_eu.id


class TestEnrichmentWithRealisticWorkflow:
    """Test item enrichment in realistic workflow scenarios."""

    def test_enrich_equipment_list_workflow(self):
        """Test enriching a list of equipment items as in a real API response."""
        # Simulating equipment data from database
        equipment_items = [
            {
                "id": 1,
                "name": "Desktop Computer - Office 101",
                "category": "desktop",
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "status": "In service",
            },
            {
                "id": 2,
                "name": "Laptop - Mobile User",
                "category": "laptop",
                "act_usage": 15,
                "pas_usage": 10,
                "act_power": 45,
                "pas_power": 2,
                "status": "In service",
            },
            {
                "id": 3,
                "name": "Server - Data Center",
                "category": "server",
                "act_usage": 100,
                "pas_usage": 0,
                "act_power": 300,
                "pas_power": 0,
                "status": "In service",
            },
        ]

        emission_factor = 0.125

        # Enrich all items
        enriched_items = [
            enrich_item_with_calculations(item, emission_factor=emission_factor)
            for item in equipment_items
        ]

        # Verify all items have CO2 calculations
        assert all("kg_co2eq" in item for item in enriched_items)
        assert enriched_items[0]["kg_co2eq"] == 31.39
        assert enriched_items[1]["kg_co2eq"] == 4.52
        # Server: 100hrs * 300W * 52 / 1000 * 0.125 = 195.0
        assert enriched_items[2]["kg_co2eq"] == 195.0

        # Verify original data is preserved
        assert enriched_items[0]["name"] == "Desktop Computer - Office 101"
        assert enriched_items[1]["category"] == "laptop"
        assert enriched_items[2]["status"] == "In service"

    def test_enrich_and_aggregate_workflow(self):
        """Test complete workflow: enrich items then calculate summary."""
        equipment_items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "status": "In service",
            },
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "status": "In service",
            },
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "status": "In service",
            },
        ]

        emission_factor = 0.125

        # Step 1: Enrich all items
        enriched_items = [
            enrich_item_with_calculations(item, emission_factor=emission_factor)
            for item in equipment_items
        ]

        # Step 2: Calculate summary
        summary = calculate_submodule_summary(enriched_items, emission_factor)

        # Verify summary
        assert summary["total_items"] == 3
        assert summary["annual_consumption_kwh"] == 753.48  # 3 * 251.16
        assert summary["total_kg_co2eq"] == 94.17  # 3 * 31.39


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions with integration context."""

    def test_zero_power_equipment(self):
        """Test equipment with zero power consumption."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=0.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        assert result == 0.0

    def test_minimal_power_equipment(self):
        """Test equipment with minimal power consumption (IoT devices)."""
        # IoT sensor: 0.5W active, 0.1W standby
        result = calculate_equipment_co2(
            act_usage_hrs_wk=168.0,  # Always on
            pas_usage_hrs_wk=0.0,
            act_power_w=0.5,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: 0.5W * 168hrs * 52wks / 1000 * 0.125 = 0.55 kgCO2eq
        assert result == 0.55

    def test_high_power_equipment(self):
        """Test equipment with very high power consumption (HPC)."""
        # High-performance computing server: 2000W
        result = calculate_equipment_co2(
            act_usage_hrs_wk=168.0,  # Always on
            pas_usage_hrs_wk=0.0,
            act_power_w=2000.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: 2000W * 168hrs * 52wks / 1000 * 0.125 = 2184.0 kgCO2eq
        assert result == 2184.0

    def test_large_equipment_fleet(self):
        """Test aggregation with large number of equipment items."""
        # Simulate 1000 identical desktop computers
        num_items = 1000
        items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
            }
            for _ in range(num_items)
        ]

        summary = calculate_submodule_summary(items, emission_factor=0.125)

        assert summary["total_items"] == num_items
        assert summary["total_kg_co2eq"] == 31390.0  # 1000 * 31.39
        assert summary["annual_consumption_kwh"] == 251160.0  # 1000 * 251.16
