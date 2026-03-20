"""Unit tests for emission breakdown pure functions."""

import pytest

from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum
from app.utils.emission_breakdown import (
    HEADCOUNT_PER_FTE_KG,
    MODULE_BREAKDOWN_ORDER,
    _get_category,
    build_chart_breakdown,
    build_treemap,
)

# ======================================================================
# build_chart_breakdown tests
# ======================================================================


def test_build_chart_breakdown_basic():
    """Equipment splits by subcategory; travel splits by emission type."""
    rows = [
        # new rows are
        # # (module_type_id, emission_type_id, scope, kg_co2eq)
        # Equipment (module_type_id=4): all share emission_type=equipment(2),
        # subcategory determines chart key
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
            "Scientific",
            10_000.0,
        ),  # scientific_equipment
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__it.value,
            "It",
            3_000.0,
        ),  # it_equipment
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__other.value,
            "Other",
            200.0,
        ),  # other_purchases (no scientific/it classification)
        # Travel (module_type_id=2): emission_type distinguishes plane/train
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__plane.value,
            "plane",
            3_000.0,
        ),
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__train.value,
            "train",
            1_500.0,
        ),
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


def test_build_chart_breakdown_emission_type_for_buildings():
    """Buildings room energy → 'Buildings room' bar with leaf keys."""
    rows = [
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__lighting.value,
            2,
            3_000.0,
        ),
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__cooling.value,
            2,
            2_000.0,
        ),
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__heating_elec.value,
            2,
            4_000.0,
        ),
    ]
    result = build_chart_breakdown(rows)

    room_bar = next(
        d for d in result["module_breakdown"] if d["category"] == "Buildings room"
    )
    assert room_bar["lighting"] == pytest.approx(3.0)
    assert room_bar["cooling"] == pytest.approx(2.0)
    assert room_bar["heating_elec"] == pytest.approx(4.0)
    assert room_bar["ventilation"] == pytest.approx(0.0)


def test_build_chart_breakdown_energy_combustion():
    """Buildings combustion and heating_thermal → 'Buildings energy combustion' bar."""
    rows = [
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__lighting.value,
            2,
            4_000.0,
        ),  # lighting → Buildings room
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__combustion.value,
            1,
            2_000.0,
        ),  # combustion → Buildings energy combustion
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__heating_thermal.value,
            1,
            1_000.0,
        ),  # heating_thermal (Scope 1) → Buildings energy combustion
    ]
    result = build_chart_breakdown(rows)

    room_bar = next(
        d for d in result["module_breakdown"] if d["category"] == "Buildings room"
    )
    assert room_bar["lighting"] == pytest.approx(4.0)
    assert room_bar.get("heating_thermal", 0.0) == pytest.approx(0.0)

    combustion_bar = next(
        d
        for d in result["module_breakdown"]
        if d["category"] == "Buildings energy combustion"
    )
    assert combustion_bar["combustion"] == pytest.approx(2.0)
    assert combustion_bar["heating_thermal"] == pytest.approx(1.0)

    assert result["total_tonnes_co2eq"] == pytest.approx(7.0)


def test_get_category_building_leaf_inherits_parent_override():
    """Building room leaf (non-thermal) inherits 'Buildings room' from parent."""
    category = _get_category(
        ModuleTypeEnum.buildings.value,
        EmissionType.buildings__rooms__lighting.value,
    )
    assert category == "Buildings room"


def test_get_category_heating_thermal_routes_to_energy_combustion():
    """heating_thermal explicit override beats parent 'Buildings room' route."""
    category = _get_category(
        ModuleTypeEnum.buildings.value,
        EmissionType.buildings__rooms__heating_thermal.value,
    )
    assert category == "Buildings energy combustion"


def test_get_category_combustion_routes_to_energy_combustion():
    """Direct fuel combustion routes to 'Buildings energy combustion'."""
    category = _get_category(
        ModuleTypeEnum.buildings.value,
        EmissionType.buildings__combustion.value,
    )
    assert category == "Buildings energy combustion"


def test_build_chart_breakdown_emission_type_for_cloud():
    """External cloud & AI uses emission type as chart key (all 4 types)."""
    rows = [
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__stockage.value,
            "External_Clouds",
            800.0,
        ),  # stockage
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__virtualisation.value,
            "External_Clouds",
            600.0,
        ),  # virtualisation
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__calcul.value,
            "External_Clouds",
            2_000.0,
        ),  # calcul
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__calcul.value,
            "External_Clouds",
            500.0,
        ),  # calcul (aggregated)
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__ai__provider_others.value,
            "External_Ai",
            1_000.0,
        ),  # ai_provider
    ]
    result = build_chart_breakdown(rows)

    cloud = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert cloud["stockage"] == pytest.approx(0.8)
    assert cloud["virtualisation"] == pytest.approx(0.6)
    assert cloud["calcul"] == pytest.approx(2.5)
    assert cloud["provider_others"] == pytest.approx(1.0)


def test_build_chart_breakdown_external_cloud_parents_map():
    """External cloud/AI exposes top-level parent mapping for level-2 types."""
    rows = [
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__calcul.value,
            "External_Clouds",
            1_000.0,
        ),
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__ai__provider_google.value,
            "External_Ai",
            2_000.0,
        ),
    ]

    result = build_chart_breakdown(rows)
    assert result["module_breakdown_parents"]["External cloud & AI"] == {
        "calcul": "clouds",
        "provider_google": "ai",
    }
    cloud = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert "__parents" not in cloud
    # Parent aggregations are emitted as chart keys too (in tonnes).
    assert cloud["clouds"] == pytest.approx(1.0)
    assert cloud["ai"] == pytest.approx(2.0)


def test_build_chart_breakdown_exposes_backend_canonical_aggregates():
    """Canonical aggregate keys are computed server-side for chart consumers."""
    rows = [
        # Buildings room leaf should appear in "Buildings room" bar
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__lighting.value,
            2,
            900.0,
        ),
        # Travel leaves should expose aggregate "plane" / "train"
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__plane__eco.value,
            3,
            1_200.0,
        ),
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__train__class_1.value,
            3,
            800.0,
        ),
        # External cloud/AI leaves should expose aggregate "clouds" / "ai"
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__stockage.value,
            3,
            600.0,
        ),
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__ai__provider_openai.value,
            3,
            400.0,
        ),
    ]
    result = build_chart_breakdown(rows)

    buildings = next(
        d for d in result["module_breakdown"] if d["category"] == "Buildings room"
    )
    assert buildings["lighting"] == pytest.approx(0.9)

    travel = next(
        d for d in result["module_breakdown"] if d["category"] == "Professional travel"
    )
    assert travel["plane"] == pytest.approx(1.2)
    assert travel["train"] == pytest.approx(0.8)

    external = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert external["clouds"] == pytest.approx(0.6)
    assert external["ai"] == pytest.approx(0.4)

    external_treemap = next(
        d for d in result["module_treemap"] if d["name"] == "External cloud & AI"
    )
    assert external_treemap["value"] == pytest.approx(1.0)
    child_names = {c["name"] for c in external_treemap["children"]}
    assert child_names == {"clouds", "ai"}


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
        (
            ModuleTypeEnum.professional_travel.value,
            EmissionType.professional_travel__plane.value,
            1,
            1_000.0,
        ),
        (
            ModuleTypeEnum.buildings.value,
            EmissionType.buildings__rooms__lighting.value,
            2,
            500.0,
        ),
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
            1,
            800.0,
        ),
        (
            ModuleTypeEnum.external_cloud_and_ai.value,
            EmissionType.external__clouds__calcul.value,
            1,
            300.0,
        ),
    ]
    result = build_chart_breakdown(rows)

    categories = [d["category"] for d in result["module_breakdown"]]
    assert categories == MODULE_BREAKDOWN_ORDER

    travel = next(
        d for d in result["module_breakdown"] if d["category"] == "Professional travel"
    )
    assert travel["plane"] == pytest.approx(1.0)

    infra = next(
        d for d in result["module_breakdown"] if d["category"] == "Buildings room"
    )
    assert infra["lighting"] == pytest.approx(0.5)

    rcf = next(
        d for d in result["module_breakdown"] if d["category"] == "External cloud & AI"
    )
    assert rcf["calcul"] == pytest.approx(0.3)

    purchases = next(
        d for d in result["module_breakdown"] if d["category"] == "Purchases"
    )
    assert purchases == {
        "category": "Purchases",
        "additional": 0.0,
        "additionalStdDev": 0.0,
        "biological_chemical_gaseous": 0.0,
        "biological_chemical_gaseousStdDev": 0.0,
        "consumable_accessories": 0.0,
        "consumable_accessoriesStdDev": 0.0,
        "it_equipment": 0.0,
        "it_equipmentStdDev": 0.0,
        "other": 0.0,
        "otherStdDev": 0.0,
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
    expected_food_tonnes = HEADCOUNT_PER_FTE_KG[EmissionType.food] * total_fte / 1000.0
    assert food_entry["food"] == pytest.approx(expected_food_tonnes)

    commuting_entry = next(
        d for d in result["additional_breakdown"] if d["category"] == "Commuting"
    )
    expected_commuting_tonnes = (
        HEADCOUNT_PER_FTE_KG[EmissionType.commuting] * total_fte / 1000.0
    )
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
        (4, EmissionType.equipment__scientific.value, 1, 5_000.0),
    ]
    result = build_chart_breakdown(rows, total_fte=0.0)

    pp = result["per_person_breakdown"]
    assert pp.get("equipment", 0.0) == 0.0
    assert pp["stdDev"] == 0


def test_build_chart_breakdown_stddev_keys():
    """Each value key has a corresponding *StdDev key (0.0 placeholder)."""
    rows = [
        (4, EmissionType.equipment__scientific.value, 1, 10_000.0),
        (
            3,
            EmissionType.buildings__rooms__lighting.value,
            2,
            9_000.0,
        ),  # maps to "Buildings room"
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
        (4, EmissionType.equipment__scientific.value, 1, 5_000.0),
        (4, EmissionType.equipment__it.value, 1, None),  # type: ignore[arg-type]
    ]
    result = build_chart_breakdown(rows)

    equip = next(d for d in result["module_breakdown"] if d["category"] == "Equipment")
    assert equip["scientific"] == pytest.approx(5.0)  # None row skipped
    assert equip["it"] == pytest.approx(0.0)


def test_build_chart_breakdown_emission_type_aggregation():
    """Multiple rows with same subcategory aggregate correctly."""
    rows = [
        (4, EmissionType.equipment__scientific.value, 1, 4_000.0),
        (4, EmissionType.equipment__scientific.value, 1, 2_000.0),
        (4, EmissionType.equipment__it.value, 1, 3_000.0),
    ]
    result = build_chart_breakdown(rows)

    equip = next(d for d in result["module_breakdown"] if d["category"] == "Equipment")
    assert equip["scientific"] == pytest.approx(6.0)
    assert equip["it"] == pytest.approx(3.0)


def test_build_chart_breakdown_validated_categories():
    """validated_categories reflects which modules are validated."""
    rows = [
        (
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
            1,
            1_000.0,
        )
    ]
    result = build_chart_breakdown(
        rows,
        validated_module_type_ids={
            ModuleTypeEnum.equipment_electric_consumption.value,
            EmissionType.equipment__scientific.value,
        },
    )
    assert "Equipment" in result["validated_categories"]
    assert "Professional travel" not in result["validated_categories"]
    assert "Buildings room" not in result["validated_categories"]
    assert "Buildings energy combustion" not in result["validated_categories"]


def test_build_chart_breakdown_validated_includes_additional_when_headcount():
    """Additional categories are validated when headcount is validated."""
    rows = [(4, EmissionType.equipment__scientific.value, 1, 1_000.0)]
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
