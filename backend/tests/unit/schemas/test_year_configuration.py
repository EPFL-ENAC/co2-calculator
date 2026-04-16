"""Tests for year_configuration schemas — validators, handlers, CSV parsing."""

import pytest
from pydantic import ValidationError

from app.schemas.year_configuration import (
    BaseReductionObjectiveHandler,
    FootprintHandler,
    InstitutionalFootprintRow,
    PopulationHandler,
    PopulationProjectionRow,
    ReductionObjectiveGoal,
    ReductionObjectiveType,
    ScenariosHandler,
    SubmoduleConfig,
    UnitScenarioRow,
    YearConfigurationUpdate,
    validate_reduction_objective_csv,
)

# ── Row model validators ─────────────────────────────────────────────────────


class TestInstitutionalFootprintRow:
    def test_valid(self):
        row = InstitutionalFootprintRow(year=2024, category="energy", co2=123.4)
        assert row.co2 == 123.4

    def test_negative_co2_rejected(self):
        with pytest.raises(ValidationError, match="co2 must be >= 0"):
            InstitutionalFootprintRow(year=2024, category="energy", co2=-1.0)


class TestPopulationProjectionRow:
    def test_valid(self):
        row = PopulationProjectionRow(year=2024, pop=5000)
        assert row.pop == 5000

    def test_negative_pop_rejected(self):
        with pytest.raises(ValidationError, match="pop must be >= 0"):
            PopulationProjectionRow(year=2024, pop=-1)


class TestUnitScenarioRow:
    def test_valid(self):
        row = UnitScenarioRow(scenario="baseline", year=2024, reduction_percentage=0.5)
        assert row.reduction_percentage == 0.5

    def test_below_zero_rejected(self):
        with pytest.raises(
            ValidationError, match="reduction_percentage must be between"
        ):
            UnitScenarioRow(scenario="x", year=2024, reduction_percentage=-0.1)

    def test_above_one_rejected(self):
        with pytest.raises(
            ValidationError, match="reduction_percentage must be between"
        ):
            UnitScenarioRow(scenario="x", year=2024, reduction_percentage=1.1)


# ── Handler system ────────────────────────────────────────────────────────────


class TestHandlerSystem:
    def test_get_footprint_handler(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.FOOTPRINT)
        assert isinstance(h, FootprintHandler)
        assert h.config_key == "institutional_footprint"

    def test_get_population_handler(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.POPULATION)
        assert isinstance(h, PopulationHandler)
        assert h.config_key == "population_projections"

    def test_get_scenarios_handler(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.SCENARIOS)
        assert isinstance(h, ScenariosHandler)
        assert h.config_key == "unit_scenarios"

    def test_get_by_invalid_type(self):
        with pytest.raises(ValueError, match="No handler found"):
            BaseReductionObjectiveHandler.get_by_type(999)

    def test_expected_columns(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.FOOTPRINT)
        assert h.expected_columns == {"year", "category", "co2"}

    def test_required_columns(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.POPULATION)
        assert h.required_columns == {"year", "pop"}

    def test_validate_create(self):
        h = BaseReductionObjectiveHandler.get_by_type(ReductionObjectiveType.FOOTPRINT)
        result = h.validate_create({"year": 2024, "category": "energy", "co2": 10.0})
        assert isinstance(result, InstitutionalFootprintRow)


# ── validate_reduction_objective_csv ──────────────────────────────────────────


class TestValidateReductionObjectiveCSV:
    def test_valid_footprint(self):
        csv_bytes = b"year,category,co2\n2024,energy,100.5\n2023,food,50.0\n"
        rows = validate_reduction_objective_csv(csv_bytes, "footprint")
        assert len(rows) == 2
        assert rows[0] == {"year": 2024, "category": "energy", "co2": 100.5}

    def test_valid_population(self):
        csv_bytes = b"year,pop\n2024,5000\n2025,6000\n"
        rows = validate_reduction_objective_csv(csv_bytes, "population")
        assert len(rows) == 2
        assert rows[1]["pop"] == 6000

    def test_valid_scenarios(self):
        csv_bytes = b"scenario,year,reduction_percentage\nbaseline,2024,0.4\n"
        rows = validate_reduction_objective_csv(csv_bytes, "scenarios")
        assert len(rows) == 1
        assert rows[0]["reduction_percentage"] == 0.4

    def test_unknown_category(self):
        with pytest.raises(ValueError, match="Unknown category"):
            validate_reduction_objective_csv(b"a,b\n1,2\n", "unknown")

    def test_empty_csv(self):
        with pytest.raises(ValueError, match="empty"):
            validate_reduction_objective_csv(b"", "footprint")

    def test_missing_headers(self):
        csv_bytes = b"year,co2\n2024,10\n"  # missing 'category'
        with pytest.raises(ValueError, match="Missing required columns"):
            validate_reduction_objective_csv(csv_bytes, "footprint")

    def test_invalid_row_data(self):
        csv_bytes = b"year,category,co2\n2024,energy,-5\n"
        with pytest.raises(ValueError, match="Row 2"):
            validate_reduction_objective_csv(csv_bytes, "footprint")

    def test_utf8_bom(self):
        csv_bytes = b"\xef\xbb\xbfyear,pop\n2024,100\n"
        rows = validate_reduction_objective_csv(csv_bytes, "population")
        assert len(rows) == 1

    def test_latin1_encoding(self):
        csv_bytes = "year,category,co2\n2024,énergie,10.0\n".encode("latin-1")
        rows = validate_reduction_objective_csv(csv_bytes, "footprint")
        assert rows[0]["category"] == "énergie"


# ── SubmoduleConfig threshold validator ───────────────────────────────────────


class TestSubmoduleConfig:
    def test_valid_threshold(self):
        s = SubmoduleConfig(threshold=10.0)
        assert s.threshold == 10.0

    def test_null_threshold(self):
        s = SubmoduleConfig(threshold=None)
        assert s.threshold is None

    def test_negative_threshold_rejected(self):
        with pytest.raises(ValidationError, match="threshold must be >= 0"):
            SubmoduleConfig(threshold=-1.0)


# ── ReductionObjectiveGoal ────────────────────────────────────────────────────


class TestReductionObjectiveGoal:
    def test_valid_goal(self):
        g = ReductionObjectiveGoal(
            target_year=2030, reduction_percentage=0.4, reference_year=2019
        )
        assert g.target_year == 2030

    def test_percentage_out_of_range(self):
        with pytest.raises(ValidationError):
            ReductionObjectiveGoal(
                target_year=2030, reduction_percentage=1.5, reference_year=2019
            )


# ── YearConfigurationUpdate threshold validator ──────────────────────────────


class TestYearConfigurationUpdateValidation:
    def test_valid_thresholds(self):
        update = YearConfigurationUpdate(
            config={
                "modules": {
                    "1": {
                        "submodules": {
                            "10": {"threshold": 100.0},
                            "11": {"threshold": None},
                        }
                    }
                }
            }
        )
        assert update.config is not None

    def test_negative_threshold_rejected(self):
        with pytest.raises(ValidationError, match="threshold.*must be a number >= 0"):
            YearConfigurationUpdate(
                config={
                    "modules": {
                        "1": {
                            "submodules": {
                                "10": {"threshold": -5.0},
                            }
                        }
                    }
                }
            )

    def test_string_threshold_rejected(self):
        with pytest.raises(ValidationError, match="threshold.*must be a number >= 0"):
            YearConfigurationUpdate(
                config={
                    "modules": {
                        "1": {
                            "submodules": {
                                "10": {"threshold": "abc"},
                            }
                        }
                    }
                }
            )

    def test_no_modules_passes(self):
        update = YearConfigurationUpdate(config={"other_key": "value"})
        assert update.config is not None

    def test_none_config_passes(self):
        update = YearConfigurationUpdate(config=None)
        assert update.config is None

    def test_non_dict_module_skipped(self):
        update = YearConfigurationUpdate(config={"modules": {"1": "not_a_dict"}})
        assert update.config is not None

    def test_non_dict_submodules_skipped(self):
        update = YearConfigurationUpdate(
            config={"modules": {"1": {"submodules": "not_a_dict"}}}
        )
        assert update.config is not None

    def test_non_dict_submodule_value_skipped(self):
        update = YearConfigurationUpdate(
            config={"modules": {"1": {"submodules": {"10": "not_a_dict"}}}}
        )
        assert update.config is not None
