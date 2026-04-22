"""Tests for backoffice.py pure helper functions."""

from app.api.v1.backoffice import (
    _get_year_keys,
    _get_years_to_process,
    _is_year_based,
    get_completion_for_years,
    get_module_outlier_values,
    get_module_status,
)


# ---------------------------------------------------------------------------
# get_module_status
# ---------------------------------------------------------------------------
class TestGetModuleStatus:
    def test_dict_with_status(self):
        assert get_module_status({"status": "validated"}) == "validated"

    def test_dict_without_status(self):
        assert get_module_status({}) == "not_started"

    def test_string_value(self):
        assert get_module_status("in-progress") == "in-progress"

    def test_non_string_non_dict(self):
        assert get_module_status(42) == "not_started"


# ---------------------------------------------------------------------------
# get_module_outlier_values
# ---------------------------------------------------------------------------
class TestGetModuleOutlierValues:
    def test_dict_with_outlier(self):
        assert get_module_outlier_values({"outlier_values": 5}) == 5

    def test_dict_without_outlier(self):
        assert get_module_outlier_values({}) == 0

    def test_string_value(self):
        assert get_module_outlier_values("validated") == 0


# ---------------------------------------------------------------------------
# _is_year_based
# ---------------------------------------------------------------------------
class TestIsYearBased:
    def test_year_keys(self):
        assert _is_year_based({"2024": {}, "2025": {}}) is True

    def test_non_year_keys(self):
        assert _is_year_based({"headcount": "validated"}) is False

    def test_empty_dict(self):
        assert _is_year_based({}) is False

    def test_mixed_keys(self):
        # Has at least one year key
        assert _is_year_based({"2024": {}, "meta": "info"}) is True

    def test_short_digit_string(self):
        assert _is_year_based({"12": {}}) is False


# ---------------------------------------------------------------------------
# _get_year_keys
# ---------------------------------------------------------------------------
class TestGetYearKeys:
    def test_extracts_year_keys(self):
        assert sorted(_get_year_keys({"2024": {}, "2025": {}, "meta": "x"})) == [
            "2024",
            "2025",
        ]

    def test_no_year_keys(self):
        assert _get_year_keys({"headcount": "ok"}) == []


# ---------------------------------------------------------------------------
# _get_years_to_process
# ---------------------------------------------------------------------------
class TestGetYearsToProcess:
    def test_no_filter_returns_all(self):
        completion = {"2024": {}, "2025": {}}
        result = _get_years_to_process(completion)
        assert sorted(result) == ["2024", "2025"]

    def test_filter_existing_year(self):
        completion = {"2024": {}, "2025": {}}
        assert _get_years_to_process(completion, ["2024"]) == ["2024"]

    def test_filter_nonexistent_year(self):
        completion = {"2024": {}}
        assert _get_years_to_process(completion, ["2099"]) == []


# ---------------------------------------------------------------------------
# get_completion_for_years
# ---------------------------------------------------------------------------
class TestGetCompletionForYears:
    def test_old_format_passthrough(self):
        old = {"headcount": {"status": "validated", "outlier_values": 0}}
        assert get_completion_for_years(old) is old

    def test_single_year(self):
        completion = {
            "2024": {
                "headcount": {"status": "validated", "outlier_values": 2},
                "buildings": {"status": "in-progress", "outlier_values": 1},
            }
        }
        result = get_completion_for_years(completion, ["2024"])
        assert result["headcount"]["status"] == "validated"
        assert result["headcount"]["outlier_values"] == 2

    def test_multiple_years_best_status_wins(self):
        completion = {
            "2024": {"headcount": {"status": "in-progress", "outlier_values": 1}},
            "2025": {"headcount": {"status": "validated", "outlier_values": 3}},
        }
        result = get_completion_for_years(completion)
        assert result["headcount"]["status"] == "validated"
        assert result["headcount"]["outlier_values"] == 4

    def test_skips_non_dict_year_data(self):
        completion = {"2024": "bad_data"}
        result = get_completion_for_years(completion)
        assert result == {}
