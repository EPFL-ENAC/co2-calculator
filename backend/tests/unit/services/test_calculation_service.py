"""Unit tests for CO2 calculation service.

Tests cover:
- Core calculation functions (calculate_equipment_co2, calculate_annual_kwh)
- Utility functions (convert_percentage_to_hours)
- Enrichment functions (enrich_item_with_calculations)
- Aggregation functions (calculate_submodule_summary, calculate_module_totals)
- Versioned calculation functions (calculate_equipment_emission_versioned)
"""

from unittest.mock import patch

import pytest

from app.services.calculation_service import (
    calculate_annual_kwh,
    calculate_equipment_co2,
    calculate_equipment_emission_versioned,
    calculate_module_totals,
    calculate_submodule_summary,
    convert_percentage_to_hours,
    enrich_item_with_calculations,
)


class TestCalculateEquipmentCO2:
    """Tests for calculate_equipment_co2 function."""

    def test_calculate_co2_basic(self):
        """Test basic CO2 calculation for equipment in service."""
        # Given: Equipment with 40hrs active, 128hrs passive per week
        # 100W active, 5W passive, 0.125 kgCO2eq/kWh emission factor
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: [(40*100 + 128*5) * 52 / 1000] * 0.125
        # = [(4000 + 640) * 52 / 1000] * 0.125
        # = [4640 * 52 / 1000] * 0.125
        # = 241.28 * 0.125 = 30.16
        assert result == 30.16

    def test_calculate_co2_zero_passive(self):
        """Test CO2 calculation with zero passive power."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=100.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: [(40*100) * 52 / 1000] * 0.125 = 26.0
        assert result == 26.0

    def test_calculate_co2_all_passive(self):
        """Test CO2 calculation with all passive usage."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=0.0,
            pas_usage_hrs_wk=168.0,
            act_power_w=0.0,
            pas_power_w=5.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: [(168*5) * 52 / 1000] * 0.125 = 5.46
        assert result == 5.46

    def test_calculate_co2_not_in_service(self):
        """Test that equipment not in service returns 0 emissions."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.125,
            status="Decommissioned",
        )

        assert result == 0.0

    def test_calculate_co2_different_statuses(self):
        """Test various non-service statuses return 0 emissions."""
        statuses = ["In stock", "Broken", "Retired", "Under repair"]

        for status in statuses:
            result = calculate_equipment_co2(
                act_usage_hrs_wk=40.0,
                pas_usage_hrs_wk=128.0,
                act_power_w=100.0,
                pas_power_w=5.0,
                emission_factor=0.125,
                status=status,
            )
            assert result == 0.0, f"Status '{status}' should return 0 emissions"

    def test_calculate_co2_zero_emission_factor(self):
        """Test CO2 calculation with zero emission factor."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
            emission_factor=0.0,
            status="In service",
        )

        assert result == 0.0

    def test_calculate_co2_zero_all_inputs(self):
        """Test CO2 calculation with all zero inputs."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=0.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=0.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        assert result == 0.0

    @pytest.mark.parametrize(
        "act_hrs,pas_hrs,act_power,pas_power,emission_factor,expected",
        [
            # High power consumption
            (40, 128, 500, 50, 0.125, 171.6),
            # Low power consumption
            (40, 128, 10, 1, 0.125, 3.43),
            # Different emission factors
            (40, 128, 100, 5, 0.25, 60.32),  # Higher EF
            (40, 128, 100, 5, 0.05, 12.06),  # Lower EF
            # Edge cases with full week usage
            (168, 0, 100, 0, 0.125, 109.2),  # All active
            (0, 168, 0, 10, 0.125, 10.92),  # All passive
        ],
    )
    def test_calculate_co2_parametrized(
        self, act_hrs, pas_hrs, act_power, pas_power, emission_factor, expected
    ):
        """Test CO2 calculation with various parameter combinations."""
        result = calculate_equipment_co2(
            act_usage_hrs_wk=act_hrs,
            pas_usage_hrs_wk=pas_hrs,
            act_power_w=act_power,
            pas_power_w=pas_power,
            emission_factor=emission_factor,
            status="In service",
        )

        assert pytest.approx(result, rel=0.01) == expected

    @patch("app.services.calculation_service.settings")
    def test_calculate_co2_uses_settings_weeks(self, mock_settings):
        """Test that calculation uses WEEKS_PER_YEAR from settings."""
        mock_settings.WEEKS_PER_YEAR = 50  # Custom value instead of 52

        result = calculate_equipment_co2(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=100.0,
            pas_power_w=0.0,
            emission_factor=0.125,
            status="In service",
        )

        # Expected: [(40*100) * 50 / 1000] * 0.125 = 25.0
        assert result == 25.0


class TestCalculateAnnualKwh:
    """Tests for calculate_annual_kwh function."""

    def test_calculate_kwh_basic(self):
        """Test basic kWh calculation."""
        result = calculate_annual_kwh(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=128.0,
            act_power_w=100.0,
            pas_power_w=5.0,
        )

        # Expected: [(40*100 + 128*5) * 52 / 1000] = 241.28
        assert result == 241.28

    def test_calculate_kwh_zero_passive(self):
        """Test kWh calculation with zero passive consumption."""
        result = calculate_annual_kwh(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=100.0,
            pas_power_w=0.0,
        )

        # Expected: [(40*100) * 52 / 1000] = 208.0
        assert result == 208.0

    def test_calculate_kwh_all_zeros(self):
        """Test kWh calculation with all zero inputs."""
        result = calculate_annual_kwh(
            act_usage_hrs_wk=0.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=0.0,
            pas_power_w=0.0,
        )

        assert result == 0.0

    @pytest.mark.parametrize(
        "act_hrs,pas_hrs,act_power,pas_power,expected",
        [
            (40, 128, 500, 50, 1372.8),  # High power
            (40, 128, 10, 1, 27.46),  # Low power
            (168, 0, 100, 0, 873.6),  # All active
            (0, 168, 0, 10, 87.36),  # All passive
        ],
    )
    def test_calculate_kwh_parametrized(
        self, act_hrs, pas_hrs, act_power, pas_power, expected
    ):
        """Test kWh calculation with various parameters."""
        result = calculate_annual_kwh(
            act_usage_hrs_wk=act_hrs,
            pas_usage_hrs_wk=pas_hrs,
            act_power_w=act_power,
            pas_power_w=pas_power,
        )

        assert pytest.approx(result, rel=0.01) == expected

    @patch("app.services.calculation_service.settings")
    def test_calculate_kwh_uses_settings_weeks(self, mock_settings):
        """Test that calculation uses WEEKS_PER_YEAR from settings."""
        mock_settings.WEEKS_PER_YEAR = 50

        result = calculate_annual_kwh(
            act_usage_hrs_wk=40.0,
            pas_usage_hrs_wk=0.0,
            act_power_w=100.0,
            pas_power_w=0.0,
        )

        # Expected: [(40*100) * 50 / 1000] = 200.0
        assert result == 200.0


class TestConvertPercentageToHours:
    """Tests for convert_percentage_to_hours function."""

    def test_convert_typical_usage(self):
        """Test typical usage percentage conversion."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=25.0, pas_usage_pct=75.0
        )

        # 25% of 168 hours = 42 hours
        # 75% of 168 hours = 126 hours
        assert act_hrs == 42.0
        assert pas_hrs == 126.0

    def test_convert_all_active(self):
        """Test 100% active usage conversion."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=100.0, pas_usage_pct=0.0
        )

        assert act_hrs == 168.0
        assert pas_hrs == 0.0

    def test_convert_all_passive(self):
        """Test 100% passive usage conversion."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=0.0, pas_usage_pct=100.0
        )

        assert act_hrs == 0.0
        assert pas_hrs == 168.0

    def test_convert_equal_split(self):
        """Test 50/50 split conversion."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=50.0, pas_usage_pct=50.0
        )

        assert act_hrs == 84.0
        assert pas_hrs == 84.0

    def test_convert_zero_both(self):
        """Test both zero percentages (edge case)."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=0.0, pas_usage_pct=0.0
        )

        assert act_hrs == 0.0
        assert pas_hrs == 0.0

    @pytest.mark.parametrize(
        "act_pct,pas_pct,expected_act,expected_pas",
        [
            (10, 90, 16.8, 151.2),
            (30, 70, 50.4, 117.6),
            (60, 40, 100.8, 67.2),
            (80, 20, 134.4, 33.6),
            (1, 99, 1.68, 166.32),
        ],
    )
    def test_convert_parametrized(self, act_pct, pas_pct, expected_act, expected_pas):
        """Test percentage conversion with various splits."""
        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=act_pct, pas_usage_pct=pas_pct
        )

        assert act_hrs == expected_act
        assert pas_hrs == expected_pas

    @patch("app.services.calculation_service.settings")
    def test_convert_uses_settings_hours(self, mock_settings):
        """Test that conversion uses HOURS_PER_WEEK from settings."""
        mock_settings.HOURS_PER_WEEK = 160  # Custom value instead of 168

        act_hrs, pas_hrs = convert_percentage_to_hours(
            act_usage_pct=25.0, pas_usage_pct=75.0
        )

        # 25% of 160 = 40, 75% of 160 = 120
        assert act_hrs == 40.0
        assert pas_hrs == 120.0


class TestEnrichItemWithCalculations:
    """Tests for enrich_item_with_calculations function."""

    def test_enrich_item_basic(self):
        """Test basic item enrichment with CO2 calculation."""
        item = {
            "id": 1,
            "name": "Desktop Computer",
            "act_usage": 42,  # hours per week
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        result = enrich_item_with_calculations(item, emission_factor=0.125)

        assert "kg_co2eq" in result
        assert result["kg_co2eq"] > 0
        # Verify calculation: 42hrs active, 126hrs passive
        # (42*100 + 126*5) * 52 / 1000 * 0.125 = 31.39
        assert result["kg_co2eq"] == 31.39

    def test_enrich_item_uses_default_emission_factor(self):
        """Test that default Swiss emission factor is used when not provided."""
        item = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        with patch("app.services.calculation_service.settings") as mock_settings:
            mock_settings.EMISSION_FACTOR_SWISS_MIX = 0.125
            mock_settings.WEEKS_PER_YEAR = 52
            mock_settings.HOURS_PER_WEEK = 168
            result = enrich_item_with_calculations(item)

        assert result["kg_co2eq"] == 31.39

    def test_enrich_item_not_in_service(self):
        """Test enrichment for equipment not in service."""
        item = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
            "status": "Decommissioned",
        }

        result = enrich_item_with_calculations(item, emission_factor=0.125)

        assert result["kg_co2eq"] == 0.0

    def test_enrich_item_with_version_tracking(self):
        """Test enrichment includes version tracking metadata."""
        item = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        result = enrich_item_with_calculations(
            item,
            emission_factor=0.125,
            factor_version_id=42,
            power_factor_version_id=99,
        )

        assert result["_factor_version_id"] == 42
        assert result["_power_factor_version_id"] == 99

    def test_enrich_item_with_hours_instead_of_percentages(self):
        """Test enrichment when usage is already in hours (> 100)."""
        item = {
            "act_usage": 40,  # hours (not percentage)
            "pas_usage": 128,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        result = enrich_item_with_calculations(item, emission_factor=0.125)

        # Should use hours directly without conversion
        assert result["kg_co2eq"] == 30.16

    def test_enrich_item_zero_usage(self):
        """Test enrichment with zero usage."""
        item = {
            "act_usage": 0,
            "pas_usage": 0,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        result = enrich_item_with_calculations(item, emission_factor=0.125)

        assert result["kg_co2eq"] == 0.0

    def test_enrich_item_missing_fields_default_to_zero(self):
        """Test enrichment handles missing fields gracefully."""
        item = {"status": "In service"}

        result = enrich_item_with_calculations(item, emission_factor=0.125)

        assert result["kg_co2eq"] == 0.0

    def test_enrich_item_modifies_in_place(self):
        """Test that enrichment modifies the item dict in-place."""
        item = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
        }

        returned_item = enrich_item_with_calculations(item, emission_factor=0.125)

        # Should be the same object
        assert returned_item is item
        assert "kg_co2eq" in item


class TestCalculateSubmoduleSummary:
    """Tests for calculate_submodule_summary function."""

    def test_summary_single_item(self):
        """Test summary calculation for a single item."""
        items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
                "status": "In service",
            }
        ]

        result = calculate_submodule_summary(items, emission_factor=0.125)

        assert result["total_items"] == 1
        assert result["annual_consumption_kwh"] == 251.16
        assert result["total_kg_co2eq"] == 31.39

    def test_summary_multiple_items(self):
        """Test summary calculation for multiple items."""
        items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 31.39,
            },
            {
                "act_usage": 50,
                "pas_usage": 50,
                "act_power": 200,
                "pas_power": 10,
                "kg_co2eq": 136.76,
            },
            {
                "act_usage": 10,
                "pas_usage": 90,
                "act_power": 50,
                "pas_power": 2,
                "kg_co2eq": 7.38,
            },
        ]

        result = calculate_submodule_summary(items, emission_factor=0.125)

        assert result["total_items"] == 3
        # Item 1: (42*100 + 126*5) * 52 / 1000 = 251.16 kWh
        # Item 2: (50*200 + 50*10) * 52 / 1000 = 546.0 kWh
        # Item 3: (10*50 + 90*2) * 52 / 1000 = 35.36 kWh
        # Total: 832.52 kWh
        assert pytest.approx(result["annual_consumption_kwh"], rel=0.01) == 832.52
        assert result["total_kg_co2eq"] == 175.53

    def test_summary_empty_items(self):
        """Test summary calculation with empty items list."""
        items = []

        result = calculate_submodule_summary(items, emission_factor=0.125)

        assert result["total_items"] == 0
        assert result["annual_consumption_kwh"] == 0.0
        assert result["total_kg_co2eq"] == 0.0

    def test_summary_uses_item_co2(self):
        """Test that summary uses pre-calculated kg_co2eq from items."""
        items = [
            {
                "act_usage": 42,
                "pas_usage": 126,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 999.99,  # Custom value
            }
        ]

        result = calculate_submodule_summary(items, emission_factor=0.125)

        # Should use the provided kg_co2eq value
        assert result["total_kg_co2eq"] == 999.99

    def test_summary_with_hours_usage(self):
        """Test summary when usage is in hours (> 100)."""
        items = [
            {
                "act_usage": 40,  # hours
                "pas_usage": 128,
                "act_power": 100,
                "pas_power": 5,
                "kg_co2eq": 30.16,
            }
        ]

        result = calculate_submodule_summary(items, emission_factor=0.125)

        assert result["annual_consumption_kwh"] == 241.28


class TestCalculateModuleTotals:
    """Tests for calculate_module_totals function."""

    def test_totals_single_submodule(self):
        """Test totals calculation for a single submodule."""
        submodules = {
            "desktop_computers": {
                "summary": {
                    "total_items": 10,
                    "annual_consumption_kwh": 2000.0,
                    "total_kg_co2eq": 250.0,
                }
            }
        }

        result = calculate_module_totals(submodules)

        assert result["total_submodules"] == 1
        assert result["total_items"] == 10
        assert result["total_annual_consumption_kwh"] == 2000.0
        assert result["total_kg_co2eq"] == 250.0

    def test_totals_multiple_submodules(self):
        """Test totals calculation for multiple submodules."""
        submodules = {
            "desktop_computers": {
                "summary": {
                    "total_items": 10,
                    "annual_consumption_kwh": 2000.0,
                    "total_kg_co2eq": 250.0,
                }
            },
            "laptops": {
                "summary": {
                    "total_items": 20,
                    "annual_consumption_kwh": 1500.0,
                    "total_kg_co2eq": 187.5,
                }
            },
            "monitors": {
                "summary": {
                    "total_items": 15,
                    "annual_consumption_kwh": 800.0,
                    "total_kg_co2eq": 100.0,
                }
            },
        }

        result = calculate_module_totals(submodules)

        assert result["total_submodules"] == 3
        assert result["total_items"] == 45
        assert result["total_annual_consumption_kwh"] == 4300.0
        assert result["total_kg_co2eq"] == 537.5

    def test_totals_empty_submodules(self):
        """Test totals calculation with empty submodules dict."""
        submodules = {}

        result = calculate_module_totals(submodules)

        assert result["total_submodules"] == 0
        assert result["total_items"] == 0
        assert result["total_annual_consumption_kwh"] == 0.0
        assert result["total_kg_co2eq"] == 0.0

    def test_totals_submodule_missing_summary(self):
        """Test totals calculation handles missing summary gracefully."""
        submodules = {
            "desktop_computers": {},  # No summary
            "laptops": {
                "summary": {
                    "total_items": 20,
                    "annual_consumption_kwh": 1500.0,
                    "total_kg_co2eq": 187.5,
                }
            },
        }

        result = calculate_module_totals(submodules)

        assert result["total_submodules"] == 2
        assert result["total_items"] == 20
        assert result["total_annual_consumption_kwh"] == 1500.0
        assert result["total_kg_co2eq"] == 187.5


class TestCalculateEquipmentEmissionVersioned:
    """Tests for calculate_equipment_emission_versioned function."""

    def test_versioned_calculation_basic(self):
        """Test basic versioned calculation with metadata."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power_w": 100,
            "pas_power_w": 5,
            "status": "In service",
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
            power_factor_id=99,
            formula_version="v1_linear",
        )

        assert result["annual_kwh"] == 251.16
        assert result["kg_co2eq"] == 31.39
        assert result["emission_factor_id"] == 42
        assert result["power_factor_id"] == 99
        assert result["formula_version"] == "v1_linear"

    def test_versioned_calculation_includes_inputs(self):
        """Test versioned calculation includes calculation inputs metadata."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power_w": 100,
            "pas_power_w": 5,
            "status": "In service",
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
        )

        assert "calculation_inputs" in result
        inputs = result["calculation_inputs"]
        assert inputs["act_usage_hrs_wk"] == 42
        assert inputs["pas_usage_hrs_wk"] == 126
        assert inputs["act_power_w"] == 100
        assert inputs["pas_power_w"] == 5
        assert inputs["emission_factor"] == 0.125
        assert inputs["status"] == "In service"

    def test_versioned_calculation_alternative_keys(self):
        """Test versioned calculation handles alternative key names."""
        # Using 'act_usage' instead of 'act_usage_pct'
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power": 100,
            "pas_power": 5,
            "status": "In service",
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
        )

        assert result["annual_kwh"] == 251.16
        assert result["kg_co2eq"] == 31.39

    def test_versioned_calculation_not_in_service(self):
        """Test versioned calculation for equipment not in service."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power_w": 100,
            "pas_power_w": 5,
            "status": "Decommissioned",
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
        )

        assert result["kg_co2eq"] == 0.0
        # But annual_kwh should still be calculated
        assert result["annual_kwh"] == 251.16

    def test_versioned_calculation_no_power_factor(self):
        """Test versioned calculation without power factor ID."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power_w": 100,
            "pas_power_w": 5,
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
            power_factor_id=None,
        )

        assert result["power_factor_id"] is None

    def test_versioned_calculation_custom_formula_version(self):
        """Test versioned calculation with custom formula version."""
        equipment_data = {
            "act_usage": 42,
            "pas_usage": 126,
            "act_power_w": 100,
            "pas_power_w": 5,
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
            formula_version="v2_exponential",
        )

        assert result["formula_version"] == "v2_exponential"

    def test_versioned_calculation_with_hours(self):
        """Test versioned calculation when usage is in hours."""
        equipment_data = {
            "act_usage": 40,
            "pas_usage": 128,
            "act_power_w": 100,
            "pas_power_w": 5,
        }

        result = calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=0.125,
            emission_factor_id=42,
        )

        assert result["annual_kwh"] == 241.28
        assert result["kg_co2eq"] == 30.16
