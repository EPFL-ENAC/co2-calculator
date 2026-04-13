"""Utilities for emission chart categorization and breakdown payload shaping.

This module is the backend contract for chart-related category semantics:

- Category keys are snake_case values from ``EmissionCategory``.
- ``module_breakdown`` and ``additional_breakdown`` rows always include
    ``category``, ``category_key``, and an ``emissions`` list, with extra
    flattened YY/parent keys for charting convenience.
- ``per_person_breakdown`` keys are snake_case and stable:
    ``process_emissions``, ``buildings``, ``equipment``,
    ``research_facilities``, ``professional_travel``, ``purchases``,
    ``external_cloud_and_ai``, plus headcount keys
    ``commuting``, ``food``, ``waste`` when applicable.
"""

# Define Scope enum locally (if needed for legacy)
from enum import IntEnum, StrEnum
from typing import Any, NotRequired, Sequence, TypedDict

from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum
from app.utils.it_breakdown import IT_EMISSION_TYPES


class Scope(IntEnum):
    scope1 = 1
    scope2 = 2
    scope3 = 3


class EmissionCategory(StrEnum):
    # scope 1
    process_emissions = "process_emissions"
    buildings_energy_combustion = "buildings_energy_combustion"
    # scope 2
    buildings_room = "buildings_room"
    equipment = "equipment"
    # scope 3
    external_cloud_and_ai = "external_cloud_and_ai"
    purchases = "purchases"
    research_facilities = "research_facilities"
    professional_travel = "professional_travel"
    # additional breakdown
    commuting = "commuting"
    food = "food"
    waste = "waste"
    embodied_energy = "embodied_energy"


class EmissionMeta(TypedDict):
    scope: Scope
    category: EmissionCategory


class EmissionBreakdownValue(TypedDict):
    emission_type: str
    key: str
    value: float
    parent_key: NotRequired[str]
    quantity: NotRequired[float]
    quantity_unit: NotRequired[str]


class EmissionBreakdownCategoryRow(TypedDict):
    category: str
    category_key: str
    emissions: list[EmissionBreakdownValue]


EMISSION_SCOPE: dict[EmissionType, EmissionMeta] = {
    # Additional Categories — scope 3
    EmissionType.food: {
        "scope": Scope.scope3,
        "category": EmissionCategory.food,
    },
    EmissionType.food__vegetarian: {
        "scope": Scope.scope3,
        "category": EmissionCategory.food,
    },
    EmissionType.food__non_vegetarian: {
        "scope": Scope.scope3,
        "category": EmissionCategory.food,
    },
    EmissionType.waste: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__incineration: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__composting: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas__organic_waste_food_leftovers: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__biogas__cooking_vegetable_oil: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__paper: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__cardboard: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__plastics: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__glass: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__ferrous_metals: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__non_ferrous_metals: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__electronics: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__wood: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__pet: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__aluminum: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__textile: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__toner_and_ink_cartridges: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.waste__recycling__inert_waste: {
        "scope": Scope.scope3,
        "category": EmissionCategory.waste,
    },
    EmissionType.commuting: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__walking: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__cycling: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__powered_two_wheeler: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__public_transport: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    EmissionType.commuting__car: {
        "scope": Scope.scope3,
        "category": EmissionCategory.commuting,
    },
    # Professional Travel — all scope 3
    EmissionType.professional_travel__train__class_1: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__train__class_2: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__first: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__business: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    EmissionType.professional_travel__plane__eco: {
        "scope": Scope.scope3,
        "category": EmissionCategory.professional_travel,
    },
    # Buildings — scope 2 except heating_thermal (scope 1)
    EmissionType.buildings__rooms__lighting: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_thermal: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },  # confirmed
    # --- Room-type granularity (8-digit WW items) ---
    EmissionType.buildings__rooms__lighting__office: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__laboratories: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__archives: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__libraries: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__auditoriums: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__lighting__miscellaneous: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__office: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__laboratories: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__archives: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__libraries: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__auditoriums: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__cooling__miscellaneous: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__office: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__laboratories: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__archives: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__libraries: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__auditoriums: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__ventilation__miscellaneous: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__office: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__laboratories: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__archives: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__libraries: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__auditoriums: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_elec__miscellaneous: {
        "scope": Scope.scope2,
        "category": EmissionCategory.buildings_room,
    },
    EmissionType.buildings__rooms__heating_thermal__office: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__laboratories: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__archives: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__libraries: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__auditoriums: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__rooms__heating_thermal__miscellaneous: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    # --- Combustion fuel-type granularity ---
    EmissionType.buildings__combustion: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },  # direct fuel combustion
    EmissionType.buildings__combustion__natural_gas: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__heating_oil: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__biomethane: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__pellets: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__forest_chips: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__combustion__wood_logs: {
        "scope": Scope.scope1,
        "category": EmissionCategory.buildings_energy_combustion,
    },
    EmissionType.buildings__embodied_energy: {
        "scope": Scope.scope3,
        "category": EmissionCategory.embodied_energy,
    },
    # Process Emissions — all scope 1
    EmissionType.process_emissions__ch4: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__co2: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__n2o: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    EmissionType.process_emissions__refrigerants: {
        "scope": Scope.scope1,
        "category": EmissionCategory.process_emissions,
    },
    # Equipment — all scope 2
    EmissionType.equipment__scientific: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    EmissionType.equipment__it: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    EmissionType.equipment__other: {
        "scope": Scope.scope2,
        "category": EmissionCategory.equipment,
    },
    # Purchases — scope 3 except additional (scope 1)
    EmissionType.purchases__goods_and_services: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__scientific_equipment: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__it_equipment: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__consumable_accessories: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__biological_chemical_gaseous: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__services: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__vehicles: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__other: {
        "scope": Scope.scope3,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__additional: {
        "scope": Scope.scope1,
        "category": EmissionCategory.purchases,
    },
    EmissionType.purchases__additional__ln2: {
        "scope": Scope.scope1,
        "category": EmissionCategory.purchases,
    },
    # Research Facilities — all scope 3
    EmissionType.research_facilities__facilities: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    EmissionType.research_facilities__animal: {
        "scope": Scope.scope3,
        "category": EmissionCategory.research_facilities,
    },
    # External Clouds & AI — all scope 3
    EmissionType.external__clouds__virtualisation: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__clouds__calcul: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__clouds__stockage: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_google: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_mistral_ai: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_anthropic: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_openai: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_cohere: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
    EmissionType.external__ai__provider_others: {
        "scope": Scope.scope3,
        "category": EmissionCategory.external_cloud_and_ai,
    },
}


# Headcount categories are those whose emission types sit at level 0 in
# EMISSION_SCOPE (food, waste, commuting — no "__" sub-path).
_HEADCOUNT_ADDITIONAL: frozenset[EmissionCategory] = frozenset(
    [
        EmissionCategory.commuting,
        EmissionCategory.food,
        EmissionCategory.waste,
    ]
)
# Buildings-derived additional categories (validated independently of headcount).
_BUILDINGS_ADDITIONAL: frozenset[EmissionCategory] = frozenset(
    [
        EmissionCategory.embodied_energy,
    ]
)
_ADDITIONAL_CATEGORIES: frozenset[EmissionCategory] = (
    _HEADCOUNT_ADDITIONAL | _BUILDINGS_ADDITIONAL
)

# Order follows the EmissionCategory enum declaration.
MODULE_BREAKDOWN_ORDER: list[EmissionCategory] = [
    c for c in EmissionCategory if c not in _ADDITIONAL_CATEGORIES
]
ADDITIONAL_BREAKDOWN_ORDER: list[EmissionCategory] = [
    c for c in EmissionCategory if c in _ADDITIONAL_CATEGORIES
]

CATEGORY_TO_MODULE_PER_UNIT: dict[EmissionCategory, int] = {
    EmissionCategory.process_emissions: ModuleTypeEnum.process_emissions.value,
    EmissionCategory.buildings_energy_combustion: ModuleTypeEnum.buildings.value,
    EmissionCategory.buildings_room: ModuleTypeEnum.buildings.value,
    EmissionCategory.equipment: ModuleTypeEnum.equipment_electric_consumption.value,
    EmissionCategory.external_cloud_and_ai: ModuleTypeEnum.external_cloud_and_ai.value,
    EmissionCategory.purchases: ModuleTypeEnum.purchase.value,
    EmissionCategory.research_facilities: ModuleTypeEnum.research_facilities.value,
    EmissionCategory.professional_travel: ModuleTypeEnum.professional_travel.value,
}


MODULE_TYPE_TO_PER_FTE_KEY: dict[int, str] = {
    ModuleTypeEnum.process_emissions.value: "process_emissions",
    ModuleTypeEnum.buildings.value: "buildings",
    ModuleTypeEnum.equipment_electric_consumption.value: "equipment",
    ModuleTypeEnum.external_cloud_and_ai.value: "external_cloud_and_ai",
    ModuleTypeEnum.purchase.value: "purchases",
    ModuleTypeEnum.research_facilities.value: "research_facilities",
    ModuleTypeEnum.professional_travel.value: "professional_travel",
}


HEADCOUNT_PER_FTE_KG: dict[EmissionType, float] = {
    EmissionType.food: 420.0,
    EmissionType.waste: 125.0,
    EmissionType.commuting: 1375.0,
}


def _resolve_emission_type(emission_type_id: int) -> EmissionType | None:
    try:
        return EmissionType(emission_type_id)
    except ValueError:
        return None


def _build_emission_value(
    emission_type: EmissionType,
    kg_co2eq: float,
    quantity: float | None = None,
    quantity_unit: str | None = None,
) -> EmissionBreakdownValue:
    value: EmissionBreakdownValue = {
        "emission_type": emission_type.name,
        "key": emission_type.name.split("__")[-1],
        "value": kg_co2eq / 1000.0,
    }
    if emission_type.level >= 2 and emission_type.parent is not None:
        value["parent_key"] = emission_type.parent.name.split("__")[-1]
    if quantity is not None:
        value["quantity"] = quantity
    if quantity_unit is not None:
        value["quantity_unit"] = quantity_unit
    return value


def _build_category_row(
    category: EmissionCategory,
    values_kg: dict[EmissionType, float],
    quantities: dict[EmissionType, tuple[float | None, str | None]] | None = None,
) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "category": category.value,
        "category_key": category.value,
    }
    emissions: list[EmissionBreakdownValue] = []
    parent_sums: dict[str, float] = {}
    for emission_type, kg_co2eq in sorted(values_kg.items(), key=lambda i: i[0].value):
        if kg_co2eq <= 0:
            continue
        qty, qty_unit = (quantities or {}).get(emission_type, (None, None))
        emission = _build_emission_value(emission_type, kg_co2eq, qty, qty_unit)
        emissions.append(emission)
        key = emission["key"]
        value = emission["value"]
        flat[key] = flat.get(key, 0.0) + value
        parent_key = emission.get("parent_key")
        if parent_key is not None:
            parent_sums[parent_key] = parent_sums.get(parent_key, 0.0) + value
    flat["emissions"] = emissions
    flat.update(parent_sums)
    return flat


def build_chart_breakdown(
    rows: Sequence[tuple[int, int, float] | tuple[int, int, float, float | None]],
    total_fte: float = 0.0,
    headcount_validated: bool = False,
    buildings_validated: bool = False,
    validated_module_type_ids: set[int] | None = None,
    exclude_module_type_ids: set[int] | frozenset[int] = frozenset(),
) -> dict:
    """Build chart payload sections from raw aggregated emission rows.

    Args:
        rows: Aggregated tuples of
            ``(module_type_id, emission_type_id, kg_co2eq)`` or
            ``(module_type_id, emission_type_id, kg_co2eq, sum_quantity)``.
        total_fte: Total headcount FTE used for per-person normalization and
            headcount-derived additional categories.
        headcount_validated: Whether headcount module is validated for the
            report. When ``True`` and ``total_fte > 0``, additional categories
            are synthesized from real DB rows (or ``HEADCOUNT_PER_FTE_KG`` as
            fallback when no sub-type rows are present).
        buildings_validated: Whether buildings module is validated. Controls
            validation status for embodied_energy additional category.
        validated_module_type_ids: Set of validated module type IDs used to
            determine ``validated_categories``.

    Returns:
        A dictionary with:

        - ``module_breakdown``: non-headcount categories in deterministic enum
          order, each row containing category keys, emission entries, and
          flattened YY/parent sums in tonnes.
        - ``additional_breakdown``: additional categories appended after main
          categories. Contains headcount-derived categories (``commuting``,
          ``food``, ``waste``) and building-derived embodied energy
          (``embodied_energy``) when present.
        - ``per_person_breakdown``: snake_case metric keys normalized by FTE.
        - ``validated_categories``: validated category keys (snake_case).
        - ``total_tonnes_co2eq``: global total including real emissions and
          synthesized headcount emissions when applicable.
        - ``total_fte``: passthrough total FTE.

    Notes:
        - Unknown emission_type IDs are ignored.
        - Headcount sub-type rows (food__, waste__, commuting__) flow into
          ``additional_breakdown`` directly.
        - If no sub-type rows exist for a category and headcount is validated,
          falls back to ``HEADCOUNT_PER_FTE_KG`` synthetic totals.
        - If ``total_fte <= 0``, per-person values are ``0.0`` and additional
          headcount rows remain empty even when headcount is validated.
    """
    category_data: dict[EmissionCategory, dict[EmissionType, float]] = {}
    additional_data: dict[EmissionCategory, dict[EmissionType, float]] = {}
    additional_quantities: dict[
        EmissionCategory, dict[EmissionType, tuple[float | None, str | None]]
    ] = {}
    module_totals_kg: dict[int, float] = {}
    real_kg = 0.0
    additional_kg = 0.0

    def _additional_quantity_unit(category: EmissionCategory) -> str:
        if category is EmissionCategory.commuting:
            return "km"
        return "kg"

    for row in rows:
        if len(row) == 3:
            module_type_id, emission_type_id, kg_co2eq = row
            sum_quantity: float | None = None
        else:
            module_type_id, emission_type_id, kg_co2eq, sum_quantity = row
        if module_type_id in exclude_module_type_ids:
            continue
        emission_type = _resolve_emission_type(emission_type_id)
        if emission_type is None:
            continue
        meta = EMISSION_SCOPE.get(emission_type)
        if meta is None:
            continue
        category = meta["category"]
        if category in ADDITIONAL_BREAKDOWN_ORDER:
            sub = additional_data.setdefault(category, {})
            sub[emission_type] = sub.get(emission_type, 0.0) + kg_co2eq
            if sum_quantity is not None:
                qty_map = additional_quantities.setdefault(category, {})
                existing_qty, existing_unit = qty_map.get(emission_type, (0.0, None))
                # quantity_unit is not summed from DB; store alongside quantity sum
                qty_map[emission_type] = (
                    (existing_qty or 0.0) + sum_quantity,
                    existing_unit or _additional_quantity_unit(category),
                )
            additional_kg += kg_co2eq
        else:
            sub = category_data.setdefault(category, {})
            sub[emission_type] = sub.get(emission_type, 0.0) + kg_co2eq
            module_totals_kg[module_type_id] = (
                module_totals_kg.get(module_type_id, 0.0) + kg_co2eq
            )
            real_kg += kg_co2eq

    module_breakdown = [
        _build_category_row(category, category_data.get(category, {}))
        for category in MODULE_BREAKDOWN_ORDER
        if CATEGORY_TO_MODULE_PER_UNIT.get(category) not in exclude_module_type_ids
    ]

    # Build additional_breakdown from real DB sub-type rows.
    # Fall back to HEADCOUNT_PER_FTE_KG synthetic values per category when that
    # category has no real rows (backward compatibility with pre-emit_per_factor data).
    fallback_data: dict[EmissionType, float] = (
        {et: per_fte_kg * total_fte for et, per_fte_kg in HEADCOUNT_PER_FTE_KG.items()}
        if headcount_validated and total_fte > 0
        else {}
    )

    additional_breakdown = []
    fallback_kg_applied = 0.0
    for category in ADDITIONAL_BREAKDOWN_ORDER:
        real_cat = additional_data.get(category, {})
        if real_cat:
            additional_breakdown.append(
                _build_category_row(
                    category,
                    real_cat,
                    additional_quantities.get(category),
                )
            )
        else:
            # Fallback: synthesize from HEADCOUNT_PER_FTE_KG for headcount categories
            fallback_cat = {
                et: kg
                for et, kg in fallback_data.items()
                if EMISSION_SCOPE[et]["category"] is category
            }
            additional_breakdown.append(_build_category_row(category, fallback_cat))
            fallback_kg_applied += sum(fallback_cat.values())

    additional_total_kg = additional_kg + fallback_kg_applied

    per_person: dict[str, float] = {
        pp_key: (module_totals_kg.get(mid, 0.0) / total_fte / 1000.0)
        if total_fte > 0
        else 0.0
        for mid, pp_key in MODULE_TYPE_TO_PER_FTE_KEY.items()
    }
    if headcount_validated and total_fte > 0:
        for category in _HEADCOUNT_ADDITIONAL:
            cat_kg = sum(additional_data.get(category, {}).values())
            if cat_kg <= 0:
                cat_kg = sum(
                    kg
                    for et, kg in fallback_data.items()
                    if EMISSION_SCOPE[et]["category"] is category
                )
            per_person[category.value] = cat_kg / total_fte / 1000.0

    total_tonnes = (real_kg + additional_total_kg) / 1000.0

    validated_ids = validated_module_type_ids or set()
    validated_categories = [
        category.value
        for category in MODULE_BREAKDOWN_ORDER
        if (mid := CATEGORY_TO_MODULE_PER_UNIT.get(category)) is not None
        and mid in validated_ids
    ]
    if headcount_validated:
        validated_categories.extend(
            c.value for c in ADDITIONAL_BREAKDOWN_ORDER if c in _HEADCOUNT_ADDITIONAL
        )
    if buildings_validated:
        validated_categories.extend(
            c.value for c in ADDITIONAL_BREAKDOWN_ORDER if c in _BUILDINGS_ADDITIONAL
        )

    # IT summary: sum IT-relevant emission types from already-processed data
    it_kg = sum(
        kg
        for cat_vals in category_data.values()
        for et, kg in cat_vals.items()
        if et in IT_EMISSION_TYPES
    )
    it_summary = {
        "total_tonnes_co2eq": it_kg / 1000.0,
        "percentage_of_total": (it_kg / real_kg * 100.0) if real_kg > 0 else 0.0,
    }

    return {
        "module_breakdown": module_breakdown,
        "additional_breakdown": additional_breakdown,
        "per_person_breakdown": per_person,
        "validated_categories": validated_categories,
        "headcount_validated": headcount_validated,
        "buildings_validated": buildings_validated,
        "total_tonnes_co2eq": total_tonnes,
        "total_fte": total_fte,
        "embodied_energy_by_building": [],
        "embodied_energy_by_category": [],
        "it_summary": it_summary,
    }


def build_treemap(rows: list[tuple[str, float]]) -> list[dict]:
    """Build normalized treemap nodes from ``(name, kg_co2eq)`` pairs.

    Args:
        rows: Node tuples where the numeric value is in kilograms CO2eq.

    Returns:
        A list of nodes with ``name``, ``value`` (kg), and ``percentage`` over
        the positive-value total. Non-positive rows are excluded. Returns an
        empty list when the positive total is zero.
    """
    total = sum(kg for _, kg in rows if kg > 0)
    if total <= 0:
        return []

    return [
        {
            "name": name,
            "value": kg,
            "percentage": (kg / total * 100) if total > 0 else 0.0,
        }
        for name, kg in rows
        if kg > 0
    ]
