"""Unit tests for emission breakdown pure functions."""

import pytest

from app.utils.emission_breakdown import (
    HEADCOUNT_PER_FTE_KG,
    MODULE_BREAKDOWN_ORDER,
    build_chart_breakdown,
    build_treemap,
)

# ======================================================================
# build_chart_breakdown tests
# ======================================================================


def test_build_chart_breakdown_basic():
    """Subcategory-preferred modules keep their subdivisions;
    others use emission type."""
    rows = [
        # Equipment (module_type_id=4) uses subcategory
        (4, 2, "Scientific", 10_000.0),
        (4, 2, "It", 3_000.0),
        (4, 2, "Other", 200.0),
        # Travel (module_type_id=2) uses subcategory
        (2, 7, "plane", 3_000.0),
        (2, 8, "train", 1_500.0),
    ]
    result = build_chart_breakdown(rows)

    equip = next(d for d in result["module_breakdown"] if d["category"] == "Equipment")
    assert equip["scientific"] == pytest.approx(10.0)
    assert equip["it"] == pytest.approx(3.0)
    assert equip["other"] == pytest.approx(0.2)

    travel = next(
        d for d in result["module_breakdown"] if d["category"] == "Professional travel"
    )
    assert travel["plane"] == pytest.approx(3.0)
    assert travel["train"] == pytest.approx(1.5)

    assert result["total_tonnes_co2eq"] == pytest.approx(17.7)


def test_build_chart_breakdown_emission_type_for_infra():
    """Infrastructure energy → 'Buildings energy consumption' bar."""
    rows = [
        (3, 1, "Building", 9_000.0),
    ]
    result = build_chart_breakdown(rows)

    infra = next(
        d
        for d in result["module_breakdown"]
        if d["category"] == "Buildings energy consumption"
    )
    assert infra["energy"] == pytest.approx(9.0)


def test_build_chart_breakdown_building_room():
    """Infrastructure grey_energy → 'Buildings room' bar (not headcount)."""
    rows = [
        (3, 1, "Building", 4_000.0),  # energy → Buildings energy consumption
        (3, 6, "Building", 2_000.0),  # grey_energy → Buildings room
    ]
    result = build_chart_breakdown(rows)

    energy_bar = next(
        d
        for d in result["module_breakdown"]
        if d["category"] == "Buildings energy consumption"
    )
    assert energy_bar["energy"] == pytest.approx(4.0)

    room_bar = next(
        d for d in result["module_breakdown"] if d["category"] == "Buildings room"
    )
    assert room_bar["grey_energy"] == pytest.approx(2.0)

    assert result["total_tonnes_co2eq"] == pytest.approx(6.0)


def test_build_chart_breakdown_emission_type_for_rcf():
    """External cloud & AI uses emission type as chart key."""
    rows = [
        (7, 10, "External_Clouds", 2_000.0),  # stockage
        (7, 11, "External_Clouds", 1_000.0),  # virtualisation
        (7, 12, "External_Ai", 500.0),  # calcul
    ]
    result = build_chart_breakdown(rows)

    rcf = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert rcf["stockage"] == pytest.approx(2.0)
    assert rcf["virtualisation"] == pytest.approx(1.0)
    assert rcf["calcul"] == pytest.approx(0.5)


def test_build_chart_breakdown_empty_input():
    """Empty rows still produce all categories with zero values."""
    result = build_chart_breakdown([])

    assert len(result["module_breakdown"]) == len(MODULE_BREAKDOWN_ORDER)
    categories = [d["category"] for d in result["module_breakdown"]]
    assert categories == MODULE_BREAKDOWN_ORDER
    for entry in result["module_breakdown"]:
        for k, v in entry.items():
            if k != "category":
                assert v == 0.0
    additional_cats = [d["category"] for d in result["additional_breakdown"]]
    assert additional_cats == ["Commuting", "Food", "Waste", "Grey Energy"]
    for entry in result["additional_breakdown"]:
        for k, v in entry.items():
            if k != "category":
                assert v == 0.0
    assert result["total_tonnes_co2eq"] == pytest.approx(0.0)
    assert result["total_fte"] == pytest.approx(0.0)


def test_build_chart_breakdown_category_ordering():
    """All categories appear in MODULE_BREAKDOWN_ORDER."""
    rows = [
        (2, 7, "plane", 1_000.0),
        (3, 1, "Building", 500.0),
        (4, 2, "Scientific", 800.0),
        (7, 12, "External_Ai", 300.0),
    ]
    result = build_chart_breakdown(rows)

    categories = [d["category"] for d in result["module_breakdown"]]
    assert categories == MODULE_BREAKDOWN_ORDER

    travel = next(
        d for d in result["module_breakdown"] if d["category"] == "Professional travel"
    )
    assert travel["plane"] == pytest.approx(1.0)

    infra = next(
        d
        for d in result["module_breakdown"]
        if d["category"] == "Buildings energy consumption"
    )
    assert infra["energy"] == pytest.approx(0.5)

    rcf = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert rcf["calcul"] == pytest.approx(0.3)

    purchases = next(
        d for d in result["module_breakdown"] if d["category"] == "Purchases"
    )
    assert purchases == {
        "category": "Purchases",
        "additional_purchases": 0.0,
        "additional_purchasesStdDev": 0.0,
        "biological_chemical_gaseous_product": 0.0,
        "biological_chemical_gaseous_productStdDev": 0.0,
        "consumable_accessories": 0.0,
        "consumable_accessoriesStdDev": 0.0,
        "it_equipment": 0.0,
        "it_equipmentStdDev": 0.0,
        "other_purchases": 0.0,
        "other_purchasesStdDev": 0.0,
        "scientific_equipment": 0.0,
        "scientific_equipmentStdDev": 0.0,
        "services": 0.0,
        "servicesStdDev": 0.0,
        "vehicles": 0.0,
        "vehiclesStdDev": 0.0,
    }


def test_build_chart_breakdown_headcount_additional():
    """Headcount placeholder data lands in additional_breakdown,
    not module_breakdown."""
    rows = [
        (4, 2, "Scientific", 5_000.0),
    ]
    result = build_chart_breakdown(rows, total_fte=10.0, headcount_validated=True)

    additional_categories = [d["category"] for d in result["additional_breakdown"]]
    assert "Commuting" in additional_categories
    assert "Food" in additional_categories
    assert "Waste" in additional_categories
    assert "Grey Energy" in additional_categories

    module_categories = [d["category"] for d in result["module_breakdown"]]
    assert "Commuting" not in module_categories
    assert "Food" not in module_categories


def test_build_chart_breakdown_headcount_per_fte():
    """Placeholder values scale with FTE:
    HEADCOUNT_PER_FTE_KG[key] * total_fte / 1000."""
    total_fte = 20.0
    rows = []
    result = build_chart_breakdown(rows, total_fte=total_fte, headcount_validated=True)

    food_entry = next(
        d for d in result["additional_breakdown"] if d["category"] == "Food"
    )
    expected_food_tonnes = HEADCOUNT_PER_FTE_KG["food"] * total_fte / 1000.0
    assert food_entry["food"] == pytest.approx(expected_food_tonnes)

    commuting_entry = next(
        d for d in result["additional_breakdown"] if d["category"] == "Commuting"
    )
    expected_commuting_tonnes = HEADCOUNT_PER_FTE_KG["commuting"] * total_fte / 1000.0
    assert commuting_entry["commuting"] == pytest.approx(expected_commuting_tonnes)


def test_build_chart_breakdown_no_headcount():
    """When headcount_validated=False, additional categories
    still appear but with 0 values."""
    rows = [
        (4, 2, "Scientific", 5_000.0),
    ]
    result = build_chart_breakdown(rows, total_fte=10.0, headcount_validated=False)

    cats = [d["category"] for d in result["additional_breakdown"]]
    assert "Commuting" in cats
    assert "Food" in cats
    assert "Waste" in cats
    assert "Grey Energy" in cats
    for entry in result["additional_breakdown"]:
        for k, v in entry.items():
            if k != "category":
                assert v == 0.0


def test_build_chart_breakdown_per_person():
    """Per-person values = module total kg / FTE / 1000."""
    total_fte = 10.0
    rows = [
        (4, 2, "Scientific", 5_000.0),
        (4, 2, "It", 3_000.0),
        (2, 7, "plane", 2_000.0),
    ]
    result = build_chart_breakdown(rows, total_fte=total_fte)

    pp = result["per_person_breakdown"]
    # equipment: (5000 + 3000) / 10 / 1000 = 0.8
    assert pp["equipment"] == pytest.approx(0.8)
    # professionalTravel: 2000 / 10 / 1000 = 0.2
    assert pp["professionalTravel"] == pytest.approx(0.2)


def test_build_chart_breakdown_per_person_zero_fte():
    """When FTE=0, per-person values are all 0 (no division by zero)."""
    rows = [
        (4, 2, "Scientific", 5_000.0),
    ]
    result = build_chart_breakdown(rows, total_fte=0.0)

    pp = result["per_person_breakdown"]
    assert pp.get("equipment", 0.0) == 0.0
    assert pp["stdDev"] == 0


def test_build_chart_breakdown_stddev_keys():
    """Each value key has a corresponding *StdDev key (0.0 placeholder)."""
    rows = [
        (4, 2, "Scientific", 10_000.0),
        (3, 1, "Building", 9_000.0),  # maps to "Buildings energy consumption"
    ]
    result = build_chart_breakdown(rows)

    for entry in result["module_breakdown"]:
        keys = [k for k in entry.keys() if k != "category"]
        value_keys = [k for k in keys if not k.endswith("StdDev")]
        for vk in value_keys:
            assert f"{vk}StdDev" in entry, f"Missing StdDev key for {vk}"
            assert entry[f"{vk}StdDev"] == 0.0


def test_build_chart_breakdown_null_filtered():
    """None/null kg_co2eq values excluded from aggregation."""
    rows = [
        (4, 2, "Scientific", 5_000.0),
        (4, 2, "It", None),  # type: ignore[arg-type]
    ]
    result = build_chart_breakdown(rows)

    equip = next(d for d in result["module_breakdown"] if d["category"] == "Equipment")
    assert equip["scientific"] == pytest.approx(5.0)
    assert equip["it"] == pytest.approx(0.0)  # zero-filled, None row skipped


def test_build_chart_breakdown_subcategory_aggregation():
    """Multiple rows with same subcategory aggregate correctly."""
    rows = [
        (4, 2, "Scientific", 4_000.0),
        (4, 2, "Scientific", 2_000.0),
        (4, 2, "It", 3_000.0),
    ]
    result = build_chart_breakdown(rows)

    equip = next(d for d in result["module_breakdown"] if d["category"] == "Equipment")
    assert equip["scientific"] == pytest.approx(6.0)
    assert equip["it"] == pytest.approx(3.0)


def test_build_chart_breakdown_validated_categories():
    """validated_categories reflects which modules are validated."""
    rows = [(4, 2, "Scientific", 1_000.0)]
    result = build_chart_breakdown(
        rows,
        validated_module_type_ids={4, 2},
    )
    assert "Equipment" in result["validated_categories"]
    assert "Professional travel" in result["validated_categories"]
    assert "Buildings energy consumption" not in result["validated_categories"]


def test_build_chart_breakdown_validated_includes_additional_when_headcount():
    """Additional categories are validated when headcount is validated."""
    rows = [(4, 2, "Scientific", 1_000.0)]
    result = build_chart_breakdown(
        rows,
        total_fte=10.0,
        headcount_validated=True,
        validated_module_type_ids={4},
    )
    assert "Commuting" in result["validated_categories"]
    assert "Food" in result["validated_categories"]
    assert "Waste" in result["validated_categories"]
    assert "Grey Energy" in result["validated_categories"]


def test_build_chart_breakdown_additional_not_validated_without_headcount():
    """Additional categories are NOT validated when headcount is not validated."""
    rows = [(4, 2, "Scientific", 1_000.0)]
    result = build_chart_breakdown(
        rows,
        total_fte=10.0,
        headcount_validated=False,
        validated_module_type_ids={4},
    )
    assert "Commuting" not in result["validated_categories"]
    assert "Food" not in result["validated_categories"]


# ======================================================================
# build_treemap tests
# ======================================================================


def test_build_treemap_basic():
    """Correct treemap entries with percentages."""
    rows = [
        ("eco", 200.0),
        ("business", 600.0),
        ("first", 200.0),
    ]
    result = build_treemap(rows)

    assert len(result) == 3
    eco = next(r for r in result if r["name"] == "eco")
    assert eco["value"] == 200.0
    assert eco["percentage"] == pytest.approx(20.0)

    business = next(r for r in result if r["name"] == "business")
    assert business["value"] == 600.0
    assert business["percentage"] == pytest.approx(60.0)


def test_build_treemap_zero_total():
    """Zero/empty totals return empty list."""
    assert build_treemap([]) == []
    assert build_treemap([("zero", 0.0)]) == []
