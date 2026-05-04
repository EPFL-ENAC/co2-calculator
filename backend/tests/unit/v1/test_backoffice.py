"""Tests for backoffice.py pure helper functions."""

from app.api.v1.backoffice import (
    CompletionCounts,
    _get_module_type_name,
    _get_year_keys,
    _get_years_to_process,
    _is_unit_complete,
    _is_year_based,
    calculate_completion_counts,
    calculate_total_outlier_values,
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
        assert get_module_status({}) == "default"

    def test_string_value(self):
        assert get_module_status("in-progress") == "in-progress"

    def test_non_string_non_dict(self):
        assert get_module_status(42) == "default"


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


# ---------------------------------------------------------------------------
# calculate_completion_counts
# ---------------------------------------------------------------------------
class TestCalculateCompletionCounts:
    def test_old_format(self):
        old = {
            "headcount": {"status": "validated"},
            "buildings": {"status": "in-progress"},
            "purchase": {"status": "default"},
        }
        counts = calculate_completion_counts(old)
        assert counts == CompletionCounts(validated=1, in_progress=1, default=1)

    def test_year_based(self):
        completion = {
            "2024": {
                "headcount": {"status": "validated"},
                "buildings": {"status": "in-progress"},
            },
            "2025": {
                "headcount": {"status": "validated"},
                "buildings": {"status": "validated"},
            },
        }
        counts = calculate_completion_counts(completion)
        assert counts.validated == 3
        assert counts.in_progress == 1
        assert counts.default == 0

    def test_year_filter(self):
        completion = {
            "2024": {"headcount": {"status": "validated"}},
            "2025": {"headcount": {"status": "in-progress"}},
        }
        counts = calculate_completion_counts(completion, ["2024"])
        assert counts.validated == 1
        assert counts.in_progress == 0


# ---------------------------------------------------------------------------
# calculate_total_outlier_values
# ---------------------------------------------------------------------------
class TestCalculateTotalOutlierValues:
    def test_sums_outliers(self):
        completion = {
            "2024": {
                "headcount": {"status": "validated", "outlier_values": 3},
                "buildings": {"status": "validated", "outlier_values": 2},
            }
        }
        assert calculate_total_outlier_values(completion) == 5

    def test_old_format(self):
        old = {
            "headcount": {"status": "validated", "outlier_values": 1},
            "buildings": {"status": "validated", "outlier_values": 4},
        }
        assert calculate_total_outlier_values(old) == 5


# ---------------------------------------------------------------------------
# _is_unit_complete
# ---------------------------------------------------------------------------
class TestIsUnitComplete:
    def test_old_format_complete(self):
        completion = {f"mod{i}": {"status": "validated"} for i in range(7)}
        assert _is_unit_complete(completion) is True

    def test_old_format_incomplete_count(self):
        completion = {f"mod{i}": {"status": "validated"} for i in range(6)}
        assert _is_unit_complete(completion) is False

    def test_old_format_incomplete_status(self):
        completion = {f"mod{i}": {"status": "validated"} for i in range(6)}
        completion["mod6"] = {"status": "in-progress"}
        assert _is_unit_complete(completion) is False

    def test_year_based_complete(self):
        year_data = {f"mod{i}": {"status": "validated"} for i in range(7)}
        completion = {"2024": year_data}
        assert _is_unit_complete(completion) is True

    def test_year_based_incomplete(self):
        year_data = {f"mod{i}": {"status": "validated"} for i in range(6)}
        year_data["mod6"] = {"status": "in-progress"}
        completion = {"2024": year_data}
        assert _is_unit_complete(completion) is False

    def test_year_filter(self):
        good = {f"mod{i}": {"status": "validated"} for i in range(7)}
        bad = {f"mod{i}": {"status": "in-progress"} for i in range(7)}
        completion = {"2024": good, "2025": bad}
        assert _is_unit_complete(completion, ["2024"]) is True
        assert _is_unit_complete(completion, ["2025"]) is False
        assert _is_unit_complete(completion) is False


# ---------------------------------------------------------------------------
# _get_module_type_name
# ---------------------------------------------------------------------------
class TestGetModuleTypeName:
    def test_known_ids(self):
        assert _get_module_type_name(1) == "headcount_member"
        assert _get_module_type_name(10) == "equipment_it"
        assert _get_module_type_name(20) == "professional_travel"
        assert _get_module_type_name(50) == "process_emissions"

    def test_unknown_id(self):
        assert _get_module_type_name(999) == "unknown_999"
