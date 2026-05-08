"""Utilities for emission chart categorization and breakdown payload shaping.

This module is the backend contract for chart-related category semantics:

- Category keys are snake_case values from ``EmissionCategory``.
- ``module_breakdown`` and ``additional_breakdown`` rows always include
    ``category``, ``category_key``, and an ``emissions`` list, with extra
    flattened YY/parent keys for charting convenience.
- ``per_person_breakdown`` keys are snake_case and stable:
    ``process_emissions``, ``buildings_room``, ``buildings_energy_combustion``,
    ``equipment``, ``research_facilities``, ``professional_travel``,
    ``purchases``, ``external_cloud_and_ai``, plus headcount keys
    ``commuting``, ``food``, ``waste`` when applicable.
"""

from typing import Any, NotRequired, Sequence, TypedDict

from app.models.data_entry_emission import (
    EmissionCategory,
    EmissionType,
)
from app.models.module_type import ModuleTypeEnum
from app.utils.it_breakdown import IT_EMISSION_TYPES


def additional_value_unit(emission_type: EmissionType) -> str | None:
    """Unit of the additional_value column for a given EmissionType."""
    node: EmissionType | None = emission_type
    while node is not None:
        if node is EmissionType.commuting or node is EmissionType.professional_travel:
            return "km"
        if node is EmissionType.food or node is EmissionType.waste:
            return "kg"
        node = node.parent
    return None


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
    parent_keys_order: list[str]


# Headcount categories: food, waste, commuting (additional breakdown).
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
    if emission_type.parent is not None and emission_type.parent.parent is not None:
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
    parent_keys_order: list[str] = []
    seen_bar_keys: set[str] = set()
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
        bar_key = parent_key if parent_key is not None else key
        if bar_key not in seen_bar_keys:
            seen_bar_keys.add(bar_key)
            parent_keys_order.append(bar_key)
    flat["emissions"] = emissions
    flat["parent_keys_order"] = parent_keys_order
    flat.update(parent_sums)
    return flat


def build_chart_breakdown(
    rows: Sequence[tuple[int, int, float, float | None]],
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
            ``(module_type_id, emission_type_id, kg_co2eq, sum_additional_value)``.
        total_fte: Total headcount FTE used for per-person normalization and
            headcount-derived additional categories.
        headcount_validated: Whether headcount module is validated for the
            report. When ``True`` and ``total_fte > 0``, additional categories
            are sourced from real DB sub-type rows.
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
        - ``per_person_breakdown``: category-level snake_case metric keys
          normalized by FTE. Buildings is split into ``buildings_room`` and
          ``buildings_energy_combustion`` (not a single ``buildings`` key).
        - ``validated_categories``: validated category keys (snake_case).
        - ``total_tonnes_co2eq``: global total of all DB-sourced emissions in tonnes.
        - ``total_fte``: passthrough total FTE.

    Notes:
        - Unknown emission_type IDs are ignored.
        - Headcount sub-type rows (food__, waste__, commuting__) flow into
          ``additional_breakdown`` directly.
        - If ``total_fte <= 0``, per-person values are ``0.0`` and additional
          headcount rows remain empty even when headcount is validated.
    """
    category_data: dict[EmissionCategory, dict[EmissionType, float]] = {}
    category_quantities: dict[
        EmissionCategory, dict[EmissionType, tuple[float | None, str | None]]
    ] = {}
    additional_data: dict[EmissionCategory, dict[EmissionType, float]] = {}
    additional_quantities: dict[
        EmissionCategory, dict[EmissionType, tuple[float | None, str | None]]
    ] = {}
    module_totals_kg: dict[int, float] = {}
    real_kg = 0.0
    additional_kg = 0.0

    for row in rows:
        module_type_id, emission_type_id, kg_co2eq, sum_additional_value = row
        if module_type_id in exclude_module_type_ids:
            continue
        emission_type = _resolve_emission_type(emission_type_id)
        if emission_type is None:
            continue
        if emission_type.scope is None:
            continue
        category = emission_type.category
        if category is None:
            continue
        if category in ADDITIONAL_BREAKDOWN_ORDER:
            sub = additional_data.setdefault(category, {})
            sub[emission_type] = kg_co2eq
            unit = additional_value_unit(emission_type)
            if sum_additional_value is not None and unit is not None:
                qty_map = additional_quantities.setdefault(category, {})
                qty_map[emission_type] = (sum_additional_value, unit)
            additional_kg += kg_co2eq
        else:
            sub = category_data.setdefault(category, {})
            sub[emission_type] = sub.get(emission_type, 0.0) + kg_co2eq
            unit = additional_value_unit(emission_type)
            if sum_additional_value is not None and unit is not None:
                qty_map = category_quantities.setdefault(category, {})
                qty_map[emission_type] = (sum_additional_value, unit)
            module_totals_kg[module_type_id] = (
                module_totals_kg.get(module_type_id, 0.0) + kg_co2eq
            )
            real_kg += kg_co2eq

    module_breakdown = [
        _build_category_row(
            category,
            category_data.get(category, {}),
            category_quantities.get(category),
        )
        for category in MODULE_BREAKDOWN_ORDER
        if CATEGORY_TO_MODULE_PER_UNIT.get(category) not in exclude_module_type_ids
    ]

    # Build additional_breakdown from real DB sub-type rows.
    additional_breakdown = []
    for category in ADDITIONAL_BREAKDOWN_ORDER:
        real_cat = additional_data.get(category, {})
        additional_breakdown.append(
            _build_category_row(
                category,
                real_cat,
                additional_quantities.get(category),
            )
        )

    additional_total_kg = additional_kg

    per_person: dict[str, float] = {
        category.value: (
            sum(category_data.get(category, {}).values()) / total_fte / 1000.0
            if total_fte > 0
            else 0.0
        )
        for category in MODULE_BREAKDOWN_ORDER
        if CATEGORY_TO_MODULE_PER_UNIT.get(category) not in exclude_module_type_ids
    }
    if headcount_validated and total_fte > 0:
        for category in _HEADCOUNT_ADDITIONAL:
            cat_kg = sum(additional_data.get(category, {}).values())
            per_person[category.value] = cat_kg / total_fte / 1000.0
    if buildings_validated and total_fte > 0:
        for category in _BUILDINGS_ADDITIONAL:
            cat_kg = sum(additional_data.get(category, {}).values())
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
