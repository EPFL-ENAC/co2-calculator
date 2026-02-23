"""Unit tests for compute_validated_totals (pure function, no DB)."""

import pytest

from app.utils.report_computations import compute_validated_totals

HEADCOUNT = "1"


# ======================================================================
# Realistic multi-module fixture
# ======================================================================


class TestRealisticScenario:
    """4 modules with headcount FTE override — one call, many assertions."""

    @pytest.fixture()
    def result(self):
        return compute_validated_totals(
            emission_stats={"1": 5000.0, "2": 25000.0, "4": 15000.0, "7": 3200.0},
            fte_stats={"1": 120.0},
            headcount_type_id=HEADCOUNT,
        )

    def test_headcount_uses_fte(self, result):
        assert result["modules"][1] == 120.0

    def test_module_2_tonnes(self, result):
        assert result["modules"][2] == pytest.approx(25.0)

    def test_module_4_tonnes(self, result):
        assert result["modules"][4] == pytest.approx(15.0)

    def test_module_7_tonnes(self, result):
        assert result["modules"][7] == pytest.approx(3.2)

    def test_module_key_order(self, result):
        assert list(result["modules"].keys()) == [1, 2, 4, 7]

    def test_total_tonnes(self, result):
        assert result["total_tonnes_co2eq"] == pytest.approx(48.2)

    def test_total_fte(self, result):
        assert result["total_fte"] == pytest.approx(120.0)


# ======================================================================
# Edge cases (parametrized)
# ======================================================================


@pytest.mark.parametrize(
    "emission, fte, expected_modules, expected_tonnes, expected_fte",
    [
        pytest.param(
            {},
            {},
            {},
            0.0,
            0.0,
            id="both_empty",
        ),
        pytest.param(
            {"4": 0.0, "2": 1000.0},
            {},
            {4: 0.0, 2: 1.0},
            1.0,
            0.0,
            id="zero_emission",
        ),
        pytest.param(
            {},
            {"1": 0.0},
            {1: 0.0},
            0.0,
            0.0,
            id="zero_fte",
        ),
        pytest.param(
            {"1": 8000.0},
            {},
            {1: 8.0},
            8.0,
            0.0,
            id="headcount_no_fte_falls_back_to_emission",
        ),
        pytest.param(
            {},
            {"1": 50.0},
            {1: 50.0},
            0.0,
            50.0,
            id="fte_only_no_emissions",
        ),
    ],
)
def test_edge_cases(emission, fte, expected_modules, expected_tonnes, expected_fte):
    result = compute_validated_totals(emission, fte, HEADCOUNT)
    assert result["modules"] == pytest.approx(expected_modules)
    assert result["total_tonnes_co2eq"] == pytest.approx(expected_tonnes)
    assert result["total_fte"] == pytest.approx(expected_fte)
