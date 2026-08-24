"""Unit tests for the stat-bucket stats pipeline.

Covers the three pure layers: per-module bucket aggregation
(``compute_module_stats``), the report merge (``_build_report_stats``), and
the cross-report merge used by backoffice views (``merge_report_stats``).
"""

from types import SimpleNamespace

from app.core.constants import ModuleStatus
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions.registry import (
    MODULE_STAT_BUCKETS,
    ORDERED_STAT_BUCKETS,
)
from app.modules.emissions.taxonomy import EmissionType
from app.services.carbon_report_module_service import compute_module_stats
from app.services.carbon_report_service import _build_report_stats
from app.utils.report_stats import merge_report_stats


def _buildings_stats() -> dict:
    leaf = {
        str(EmissionType.buildings__combustion__propane.value): 100.0,
        str(EmissionType.buildings__rooms__heating_thermal__office.value): 50.0,
        str(EmissionType.buildings__rooms__lighting__office.value): 30.0,
        str(EmissionType.buildings__construction_and_renovation.value): 7.0,
    }
    return compute_module_stats(leaf, {}, MODULE_STAT_BUCKETS[ModuleTypeEnum.buildings])


def _headcount_stats() -> dict:
    leaf = {
        str(EmissionType.food__vegetarian.value): 20.0,
        str(EmissionType.commuting__car.value): 5.0,
    }
    quantities = {str(EmissionType.commuting__car.value): 99.0}
    return compute_module_stats(
        leaf,
        quantities,
        MODULE_STAT_BUCKETS[ModuleTypeEnum.headcount],
        module_extras={"total_fte": 10.0},
    )


def _equipment_stats() -> dict:
    leaf = {str(EmissionType.equipment__it.value): 1000.0}
    return compute_module_stats(leaf, {}, MODULE_STAT_BUCKETS[ModuleTypeEnum.equipment])


def _modules() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            module_type_id=ModuleTypeEnum.buildings.value,
            status=ModuleStatus.VALIDATED,
            stats=_buildings_stats(),
        ),
        SimpleNamespace(
            module_type_id=ModuleTypeEnum.headcount.value,
            status=ModuleStatus.VALIDATED,
            stats=_headcount_stats(),
        ),
        SimpleNamespace(
            module_type_id=ModuleTypeEnum.equipment.value,
            status=ModuleStatus.IN_PROGRESS,
            stats=_equipment_stats(),
        ),
    ]


def test_bucket_order_matches_chart_display_order():
    assert [bn.bucket.key for _, bn in ORDERED_STAT_BUCKETS] == [
        "process_emissions",
        "buildings_energy_combustion",
        "buildings_room",
        "equipment",
        "external_cloud_and_ai",
        "purchases",
        "research_facilities",
        "professional_travel",
        "commuting",
        "food",
        "waste",
        "embodied_energy",
    ]


def test_buildings_split_across_buckets():
    stats = _buildings_stats()
    # thermal heating counts as scope-1 combustion, not rooms
    assert stats["buckets"]["buildings_energy_combustion"]["total_kg"] == 150.0
    assert stats["buckets"]["buildings_room"]["total_kg"] == 30.0
    assert stats["buckets"]["embodied_energy"]["total_kg"] == 7.0
    assert stats["buckets"]["embodied_energy"]["additional"] is True
    assert stats["total"] == 187.0


def test_rooms_rollup_excludes_heating_thermal():
    stats = _buildings_stats()
    rooms = stats["buckets"]["buildings_room"]["by_emission_type"]
    assert rooms[str(EmissionType.buildings__rooms.value)] == 30.0


def test_headcount_buckets_carry_quantities_and_fte():
    stats = _headcount_stats()
    assert stats["buckets"]["food"]["total_kg"] == 20.0
    commuting = stats["buckets"]["commuting"]
    assert commuting["by_additional_value"][str(EmissionType.commuting__car.value)] == (
        99.0
    )
    assert stats["total_fte"] == 10.0


def test_report_stats_merge_and_validation():
    report = _build_report_stats(_modules())
    assert report["total"] == 187.0 + 25.0 + 1000.0
    assert report["total_fte"] == 10.0
    assert report["scope1"] == 150.0
    assert report["scope2"] == 30.0 + 1000.0
    assert "equipment" not in report["validated_buckets"]
    assert "food" in report["validated_buckets"]
    assert report["validated_total"] == 187.0 + 25.0
    assert report["it"]["categories"]["equipment_it"] == 1000.0
    assert abs(report["per_fte"]["buildings_room"] - 30.0 / 10 / 1000) < 1e-12


def test_simulator_reports_treat_all_modules_as_validated():
    report = _build_report_stats(_modules(), is_simulator=True)
    assert "equipment" in report["validated_buckets"]
    assert report["validated_total"] == report["total"]


def test_merge_report_stats_sums_across_reports():
    report = _build_report_stats(_modules())
    merged = merge_report_stats([report, report])
    assert merged["total"] == 2 * report["total"]
    assert merged["buckets"]["buildings_energy_combustion"]["total_kg"] == 300.0
    assert merged["total_fte"] == 20.0
    assert merged["it"]["categories"]["equipment_it"] == 2000.0
    assert merged["validated_buckets"] == report["validated_buckets"]


def test_merge_report_stats_empty_input():
    merged = merge_report_stats([])
    assert merged["buckets"] == {}
    assert merged["total"] == 0.0
    assert merged["it"]["total_kg"] == 0.0


def _embodied_report(by_building: list[dict], by_category: list[dict]) -> dict:
    """A minimal report whose embodied bucket carries the detail lists."""
    return {
        "buckets": {
            "embodied_energy": {
                "scope": 3,
                "additional": True,
                "total_kg": sum(row["kg_co2eq"] for row in by_category),
                "by_emission_type": {},
                "by_additional_value": {},
                "by_building": by_building,
                "by_category": by_category,
            }
        },
        "validated_buckets": ["embodied_energy"],
        "total": sum(row["kg_co2eq"] for row in by_category),
        "validated_total": 0.0,
        "total_fte": 0.0,
        "entry_count": 0,
    }


def test_merge_report_stats_sums_embodied_energy_detail():
    """Without this the combined Results view shows a total but an empty chart."""
    first = _embodied_report(
        by_building=[{"building_name": "GC", "kg_co2eq": 1000.0, "tonnes_co2eq": 1.0}],
        by_category=[
            {"category": "concrete", "kg_co2eq": 600.0, "tonnes_co2eq": 0.6},
            {"category": "steel", "kg_co2eq": 400.0, "tonnes_co2eq": 0.4},
        ],
    )
    second = _embodied_report(
        by_building=[
            # Same building in another unit collapses into one row.
            {"building_name": "GC", "kg_co2eq": 500.0, "tonnes_co2eq": 0.5},
            {"building_name": "BC", "kg_co2eq": 250.0, "tonnes_co2eq": 0.25},
        ],
        by_category=[{"category": "steel", "kg_co2eq": 750.0, "tonnes_co2eq": 0.75}],
    )

    bucket = merge_report_stats([first, second])["buckets"]["embodied_energy"]

    assert bucket["by_building"] == [
        {"building_name": "BC", "kg_co2eq": 250.0, "tonnes_co2eq": 0.25},
        {"building_name": "GC", "kg_co2eq": 1500.0, "tonnes_co2eq": 1.5},
    ]
    assert bucket["by_category"] == [
        {"category": "concrete", "kg_co2eq": 600.0, "tonnes_co2eq": 0.6},
        {"category": "steel", "kg_co2eq": 1150.0, "tonnes_co2eq": 1.15},
    ]


def test_merge_report_stats_omits_absent_bucket_detail():
    """Buckets that never carried detail lists must not grow empty ones."""
    merged = merge_report_stats([_build_report_stats(_modules())])
    assert "by_building" not in merged["buckets"]["equipment"]
    assert "by_category" not in merged["buckets"]["equipment"]
