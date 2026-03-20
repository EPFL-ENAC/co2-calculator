"""Unit tests for emission category chart helpers."""

import pytest

from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum
from app.utils.emission_category import (
    HEADCOUNT_PER_FTE_KG,
    MODULE_BREAKDOWN_ORDER,
    build_chart_breakdown,
    build_treemap,
)

EXPECTED_MODULE_BREAKDOWN_ORDER = [
    category.value for category in MODULE_BREAKDOWN_ORDER
]


def _row_by_category(rows: list[dict], category: str) -> dict:
    return next(row for row in rows if row["category"] == category)


def test_build_chart_breakdown_returns_emission_entries_only():
    rows = [
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
            10_000.0,
        ),
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__plane__eco.value,
            3_000.0,
        ),
    ]

    result = build_chart_breakdown(rows)

    categories = [row["category"] for row in result["module_breakdown"]]
    assert categories == EXPECTED_MODULE_BREAKDOWN_ORDER

    equipment = _row_by_category(result["module_breakdown"], "equipment")
    assert equipment["category_key"] == "equipment"
    assert equipment["scientific"] == pytest.approx(10.0)

    travel = _row_by_category(result["module_breakdown"], "professional_travel")
    assert travel["eco"] == pytest.approx(3.0)
    assert travel["plane"] == pytest.approx(3.0)  # parent_key sum

    assert result["total_tonnes_co2eq"] == pytest.approx(13.0)


def test_build_chart_breakdown_aggregates_same_emission_type():
    rows = [
        (4, EmissionType.equipment__scientific.value, 4_000.0),
        (4, EmissionType.equipment__scientific.value, 2_000.0),
        (4, EmissionType.equipment__it.value, 1_000.0),
    ]

    result = build_chart_breakdown(rows)
    equipment = _row_by_category(result["module_breakdown"], "equipment")
    assert equipment["scientific"] == pytest.approx(6.0)
    assert equipment["it"] == pytest.approx(1.0)


def test_build_chart_breakdown_separates_building_categories():
    rows = [
        (3, EmissionType.buildings__rooms__lighting.value, 3_000.0),
        (3, EmissionType.buildings__combustion.value, 2_000.0),
    ]

    result = build_chart_breakdown(rows)
    room = _row_by_category(result["module_breakdown"], "buildings_room")
    combustion = _row_by_category(
        result["module_breakdown"],
        "buildings_energy_combustion",
    )

    assert room["lighting"] == pytest.approx(3.0)
    assert combustion["combustion"] == pytest.approx(2.0)


def test_build_chart_breakdown_headcount_goes_to_additional_breakdown():
    result = build_chart_breakdown([], total_fte=20.0, headcount_validated=True)

    food = _row_by_category(result["additional_breakdown"], "food")
    commuting = _row_by_category(result["additional_breakdown"], "commuting")

    assert food["food"] == pytest.approx(
        HEADCOUNT_PER_FTE_KG[EmissionType.food] * 20.0 / 1000.0
    )
    assert commuting["commuting"] == pytest.approx(
        HEADCOUNT_PER_FTE_KG[EmissionType.commuting] * 20.0 / 1000.0
    )


def test_build_chart_breakdown_per_person_exposes_only_value_keys():
    rows = [
        (4, EmissionType.equipment__scientific.value, 5_000.0),
        (4, EmissionType.equipment__it.value, 3_000.0),
        (2, EmissionType.professional_travel__plane__eco.value, 2_000.0),
    ]

    result = build_chart_breakdown(rows, total_fte=10.0)
    per_person = result["per_person_breakdown"]

    assert per_person == {
        "buildings": pytest.approx(0.0),
        "equipment": pytest.approx(0.8),
        "research_facilities": pytest.approx(0.0),
        "professional_travel": pytest.approx(0.2),
        "purchases": pytest.approx(0.0),
        "external_cloud_and_ai": pytest.approx(0.0),
        "process_emissions": pytest.approx(0.0),
    }


def test_build_chart_breakdown_validated_categories_follow_module_validation():
    rows = [
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
            1_000.0,
        )
    ]

    result = build_chart_breakdown(
        rows,
        total_fte=10.0,
        headcount_validated=True,
        validated_module_type_ids={ModuleTypeEnum.equipment_electric_consumption.value},
    )

    assert "equipment" in result["validated_categories"]
    assert "commuting" in result["validated_categories"]
    assert "professional_travel" not in result["validated_categories"]


def test_build_treemap_basic():
    rows = [("eco", 200.0), ("business", 600.0), ("first", 200.0)]
    result = build_treemap(rows)

    assert len(result) == 3
    eco = next(row for row in result if row["name"] == "eco")
    assert eco["percentage"] == pytest.approx(20.0)


def test_build_treemap_zero_total():
    assert build_treemap([]) == []
    assert build_treemap([("zero", 0.0)]) == []
