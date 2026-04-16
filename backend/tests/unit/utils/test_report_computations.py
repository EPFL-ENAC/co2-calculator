"""Tests for report_computations utility functions."""

import pytest

from app.utils.report_computations import (
    compute_results_summary,
    compute_validated_totals,
)


class TestComputeValidatedTotals:
    def test_basic(self):
        result = compute_validated_totals(
            emission_stats={"2": 2000.0, "3": 3000.0},
            fte_stats={"1": 50.0},
            headcount_type_id="1",
        )
        assert result["modules"][2] == 2.0  # 2000 kg -> 2 tonnes
        assert result["modules"][3] == 3.0
        assert result["total_tonnes_co2eq"] == 5.0
        assert result["total_fte"] == 50.0

    def test_headcount_uses_fte(self):
        result = compute_validated_totals(
            emission_stats={"1": 1000.0},
            fte_stats={"1": 42.0},
            headcount_type_id="1",
        )
        # headcount module should use FTE value, not emission
        assert result["modules"][1] == 42.0

    def test_empty(self):
        result = compute_validated_totals(
            emission_stats={}, fte_stats={}, headcount_type_id="1"
        )
        assert result["modules"] == {}
        assert result["total_tonnes_co2eq"] == 0.0
        assert result["total_fte"] == 0.0


class TestComputeResultsSummary:
    def test_basic(self):
        result = compute_results_summary(
            current_emissions={"2": 4000.0},
            current_fte={"1": 10.0},
            prev_emissions={"2": 2000.0},
            co2_per_km_kg=0.2,
            headcount_key="1",
        )
        assert len(result["module_results"]) == 1
        mod = result["module_results"][0]
        assert mod["module_type_id"] == 2
        assert mod["total_tonnes_co2eq"] == 4.0
        assert mod["previous_year_total_tonnes_co2eq"] == 2.0
        assert mod["year_comparison_percentage"] == 100.0  # doubled
        assert mod["equivalent_car_km"] == 20000.0

        unit = result["unit_totals"]
        assert unit["total_tonnes_co2eq"] == 4.0

    def test_zero_co2_per_km_raises(self):
        with pytest.raises(ValueError, match="positive"):
            compute_results_summary(
                current_emissions={},
                current_fte={},
                prev_emissions={},
                co2_per_km_kg=0,
                headcount_key="1",
            )

    def test_none_emissions_skipped(self):
        result = compute_results_summary(
            current_emissions={"2": None},
            current_fte={},
            prev_emissions={},
            co2_per_km_kg=0.2,
            headcount_key="1",
        )
        assert result["module_results"] == []
        assert result["unit_totals"]["total_tonnes_co2eq"] is None

    def test_exclude_module_type_ids(self):
        result = compute_results_summary(
            current_emissions={"2": 1000.0, "3": 2000.0},
            current_fte={},
            prev_emissions={},
            co2_per_km_kg=0.2,
            headcount_key="1",
            exclude_module_type_ids={2},
        )
        assert len(result["module_results"]) == 1
        assert result["module_results"][0]["module_type_id"] == 3

    def test_no_previous_year(self):
        result = compute_results_summary(
            current_emissions={"2": 1000.0},
            current_fte={"1": 5.0},
            prev_emissions={},
            co2_per_km_kg=0.2,
            headcount_key="1",
        )
        mod = result["module_results"][0]
        assert mod["previous_year_total_tonnes_co2eq"] is None
        assert mod["year_comparison_percentage"] is None
        assert mod["tonnes_co2eq_per_fte"] == 1.0 / 5.0

    def test_no_fte(self):
        result = compute_results_summary(
            current_emissions={"2": 1000.0},
            current_fte={},
            prev_emissions={},
            co2_per_km_kg=0.2,
            headcount_key="1",
        )
        mod = result["module_results"][0]
        assert mod["tonnes_co2eq_per_fte"] is None
        assert result["unit_totals"]["tonnes_co2eq_per_fte"] is None
