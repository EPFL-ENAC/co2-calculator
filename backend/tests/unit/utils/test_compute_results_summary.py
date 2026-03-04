"""Unit tests for compute_results_summary (pure function, no DB)."""

import pytest

from app.utils.report_computations import compute_results_summary

HEADCOUNT_KEY = "1"
CO2_PER_KM_KG = 0.17


# ======================================================================
# Realistic multi-module fixture
# ======================================================================


class TestRealisticScenario:
    """5 modules covering: decrease, unchanged, div/0 prev, skipped None, no prev."""

    @pytest.fixture()
    def result(self):
        return compute_results_summary(
            current_emissions={
                "1": 5000.0,  # headcount — has FTE, prev went down
                "2": 12000.0,  # travel — prev unchanged
                "4": 8500.0,  # equipment — prev == 0 (div/0 guard)
                "5": None,  # purchases — not validated → skipped
                "7": 3200.0,  # cloud — no prev at all
            },
            current_fte={"1": 120.0},
            prev_emissions={"1": 6000.0, "2": 12000.0, "4": 0.0},
            co2_per_km_kg=CO2_PER_KM_KG,
            headcount_key=HEADCOUNT_KEY,
        )

    def _module(self, result, module_type_id: int) -> dict:
        return next(
            m for m in result["module_results"] if m["module_type_id"] == module_type_id
        )

    # --- module_results assertions ---

    def test_module_5_skipped(self, result):
        ids = [m["module_type_id"] for m in result["module_results"]]
        assert 5 not in ids

    def test_only_4_modules_emitted(self, result):
        assert len(result["module_results"]) == 4

    def test_headcount_total_fte_exposed(self, result):
        m = self._module(result, 1)
        assert m["total_fte"] == 120.0

    def test_non_headcount_fte_is_none(self, result):
        m = self._module(result, 2)
        assert m["total_fte"] is None

    def test_headcount_year_comparison_decrease(self, result):
        m = self._module(result, 1)
        assert m["year_comparison_percentage"] == pytest.approx(
            (5000 - 6000) / 6000 * 100
        )

    def test_travel_year_comparison_unchanged(self, result):
        m = self._module(result, 2)
        assert m["year_comparison_percentage"] == pytest.approx(0.0)

    def test_equipment_prev_zero_div_guard(self, result):
        m = self._module(result, 4)
        assert m["year_comparison_percentage"] is None
        assert m["previous_year_total_tonnes_co2eq"] == pytest.approx(0.0)

    def test_cloud_no_prev(self, result):
        m = self._module(result, 7)
        assert m["year_comparison_percentage"] is None
        assert m["previous_year_total_tonnes_co2eq"] is None

    def test_headcount_tonnes(self, result):
        m = self._module(result, 1)
        assert m["total_tonnes_co2eq"] == pytest.approx(5.0)

    def test_travel_equivalent_car_km(self, result):
        m = self._module(result, 2)
        assert m["equivalent_car_km"] == pytest.approx(12000 / CO2_PER_KM_KG)

    def test_headcount_tonnes_per_fte(self, result):
        m = self._module(result, 1)
        assert m["tonnes_co2eq_per_fte"] == pytest.approx(5.0 / 120.0)

    # --- unit_totals assertions ---

    def test_unit_total_tonnes(self, result):
        total_kg = 5000 + 12000 + 8500 + 3200
        assert result["unit_totals"]["total_tonnes_co2eq"] == pytest.approx(
            total_kg / 1000
        )

    def test_unit_total_fte(self, result):
        assert result["unit_totals"]["total_fte"] == 120.0

    def test_unit_tonnes_per_fte(self, result):
        total_kg = 5000 + 12000 + 8500 + 3200
        assert result["unit_totals"]["tonnes_co2eq_per_fte"] == pytest.approx(
            (total_kg / 1000) / 120.0
        )

    def test_unit_equivalent_car_km(self, result):
        total_kg = 5000 + 12000 + 8500 + 3200
        assert result["unit_totals"]["equivalent_car_km"] == pytest.approx(
            total_kg / CO2_PER_KM_KG
        )

    def test_unit_prev_total_tonnes(self, result):
        prev_kg = 6000 + 12000 + 0
        assert result["unit_totals"][
            "previous_year_total_tonnes_co2eq"
        ] == pytest.approx(prev_kg / 1000)

    def test_unit_year_comparison(self, result):
        curr_kg = 5000 + 12000 + 8500 + 3200
        prev_kg = 6000 + 12000 + 0
        assert result["unit_totals"]["year_comparison_percentage"] == pytest.approx(
            (curr_kg - prev_kg) / prev_kg * 100
        )

    def test_co2_per_km_kg_passthrough(self, result):
        assert result["co2_per_km_kg"] == CO2_PER_KM_KG


# ======================================================================
# Edge cases (targeted)
# ======================================================================


def test_empty_current_emissions():
    result = compute_results_summary({}, {"1": 100.0}, {}, CO2_PER_KM_KG, HEADCOUNT_KEY)
    assert result["unit_totals"]["total_tonnes_co2eq"] is None
    assert result["module_results"] == []


def test_empty_prev_emissions():
    result = compute_results_summary(
        {"2": 5000.0}, {}, {}, CO2_PER_KM_KG, HEADCOUNT_KEY
    )
    ut = result["unit_totals"]
    assert ut["previous_year_total_tonnes_co2eq"] is None
    assert ut["year_comparison_percentage"] is None


def test_prev_all_zero():
    result = compute_results_summary(
        {"1": 5000.0, "2": 3000.0},
        {},
        {"1": 0.0, "2": 0.0},
        CO2_PER_KM_KG,
        HEADCOUNT_KEY,
    )
    assert result["unit_totals"]["year_comparison_percentage"] is None


def test_no_fte():
    """No headcount module at all → total_fte and tonnes_per_fte are None."""
    result = compute_results_summary(
        {"2": 4000.0}, {}, {}, CO2_PER_KM_KG, HEADCOUNT_KEY
    )
    assert result["unit_totals"]["total_fte"] is None
    assert result["unit_totals"]["tonnes_co2eq_per_fte"] is None


def test_fte_zero():
    """FTE == 0 → tonnes_per_fte is None (div/0 guard)."""
    result = compute_results_summary(
        {"2": 4000.0}, {"1": 0.0}, {}, CO2_PER_KM_KG, HEADCOUNT_KEY
    )
    assert result["unit_totals"]["tonnes_co2eq_per_fte"] is None


def test_single_module_decrease():
    result = compute_results_summary(
        {"2": 4500.0}, {}, {"2": 5000.0}, CO2_PER_KM_KG, HEADCOUNT_KEY
    )
    m = result["module_results"][0]
    assert m["year_comparison_percentage"] == pytest.approx(-10.0)


def test_single_module_full_drop():
    result = compute_results_summary(
        {"2": 0.0}, {}, {"2": 5000.0}, CO2_PER_KM_KG, HEADCOUNT_KEY
    )
    m = result["module_results"][0]
    assert m["year_comparison_percentage"] == pytest.approx(-100.0)


@pytest.mark.parametrize("bad_value", [0, -1, -0.5])
def test_co2_per_km_kg_non_positive_raises(bad_value):
    with pytest.raises(ValueError, match="co2_per_km_kg must be positive"):
        compute_results_summary({"2": 1000.0}, {}, {}, bad_value, HEADCOUNT_KEY)
