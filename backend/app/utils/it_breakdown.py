"""Utilities for building an IT-focused emission breakdown.

Aggregates IT-related emissions from four source modules:

- **Equipment** (``equipment__it``): IT device electricity consumption (Scope 2)
- **Purchases** (``purchases__it_equipment``): IT hardware procurement (Scope 3)
- **External Cloud & AI** (all ``external__clouds__*`` and ``external__ai__*``):
  cloud computing and AI provider emissions (Scope 3)
- **Research Facilities** (``research_facilities__*``): IT-related research
  facility emissions (Scope 3)
"""

from typing import Any

from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum

# ---------------------------------------------------------------------------
# IT category definitions
# ---------------------------------------------------------------------------

IT_CATEGORY_EQUIPMENT = "equipment_it"
IT_CATEGORY_PURCHASES = "purchases_it"
IT_CATEGORY_CLOUD_AI = "external_cloud_and_ai"
IT_CATEGORY_RESEARCH = "research_facilities_it"

# Emission types that count as IT
_IT_EQUIPMENT_TYPES: frozenset[EmissionType] = frozenset(
    [
        EmissionType.equipment__it,
    ]
)

_IT_PURCHASES_TYPES: frozenset[EmissionType] = frozenset(
    [
        EmissionType.purchases__it_equipment,
    ]
)

_IT_CLOUD_AI_TYPES: frozenset[EmissionType] = frozenset(
    [
        EmissionType.external__clouds__virtualisation,
        EmissionType.external__clouds__calcul,
        EmissionType.external__clouds__stockage,
        EmissionType.external__ai__provider_google,
        EmissionType.external__ai__provider_mistral_ai,
        EmissionType.external__ai__provider_anthropic,
        EmissionType.external__ai__provider_openai,
        EmissionType.external__ai__provider_cohere,
        EmissionType.external__ai__provider_others,
    ]
)

_IT_RESEARCH_TYPES: frozenset[EmissionType] = frozenset(
    [
        EmissionType.research_facilities,
        EmissionType.research_facilities__facilities,
        EmissionType.research_facilities__animal,
    ]
)

IT_EMISSION_TYPES: frozenset[EmissionType] = (
    _IT_EQUIPMENT_TYPES | _IT_PURCHASES_TYPES | _IT_CLOUD_AI_TYPES | _IT_RESEARCH_TYPES
)

# Maps IT category key -> set of module_type_ids that feed into it
_IT_CATEGORY_MODULE_IDS: dict[str, set[int]] = {
    IT_CATEGORY_EQUIPMENT: {ModuleTypeEnum.equipment_electric_consumption.value},
    IT_CATEGORY_PURCHASES: {ModuleTypeEnum.purchase.value},
    IT_CATEGORY_CLOUD_AI: {ModuleTypeEnum.external_cloud_and_ai.value},
    IT_CATEGORY_RESEARCH: {ModuleTypeEnum.research_facilities.value},
}

# Ordered list of IT categories for deterministic output
IT_CATEGORIES_ORDER: list[str] = [
    IT_CATEGORY_EQUIPMENT,
    IT_CATEGORY_PURCHASES,
    IT_CATEGORY_CLOUD_AI,
    IT_CATEGORY_RESEARCH,
]


def _categorize_it_emission(emission_type: EmissionType) -> str | None:
    """Return the IT category key for an emission type, or None."""
    if emission_type in _IT_EQUIPMENT_TYPES:
        return IT_CATEGORY_EQUIPMENT
    if emission_type in _IT_PURCHASES_TYPES:
        return IT_CATEGORY_PURCHASES
    if emission_type in _IT_CLOUD_AI_TYPES:
        return IT_CATEGORY_CLOUD_AI
    if emission_type in _IT_RESEARCH_TYPES:
        return IT_CATEGORY_RESEARCH
    return None


def build_it_breakdown(
    rows: list[tuple[int, int, float]],
    total_fte: float = 0.0,
    total_emissions_kg: float = 0.0,
    validated_module_type_ids: set[int] | None = None,
    top_class_detail: dict[str, list[dict[str, Any]]] | None = None,
    exclude_module_type_ids: set[int] | frozenset[int] = frozenset(),
) -> dict[str, Any]:
    """Build an IT-focused emission breakdown from raw aggregated rows.

    Args:
        rows: Aggregated tuples of ``(module_type_id, emission_type_id, kg_co2eq)``.
        total_fte: Total headcount FTE for per-person normalization.
        total_emissions_kg: Total emissions (all modules) in kg for percentage
            calculation. When zero, recomputed from ``rows`` after applying
            ``exclude_module_type_ids`` (matches chart breakdown behaviour).
        validated_module_type_ids: Set of validated module type IDs.
        exclude_module_type_ids: Module type IDs to omit (same as emission
            breakdown / results summary).

    Returns:
        A dictionary with ``total_it_tonnes_co2eq``, ``total_it_per_fte``,
        ``categories`` (ordered list), ``scope_breakdown``, and validation info.
    """
    exclude = exclude_module_type_ids or frozenset()
    filtered_rows = [r for r in rows if r[0] not in exclude]
    # Align % of total with chart breakdown when modules are excluded.
    if exclude:
        total_emissions_kg = sum(kg for _, _, kg in filtered_rows)

    validated_ids = validated_module_type_ids or set()

    # Accumulate kg per IT category and per emission type within cloud/AI
    category_kg: dict[str, float] = {cat: 0.0 for cat in IT_CATEGORIES_ORDER}
    cloud_ai_detail: dict[str, float] = {}

    for _module_type_id, emission_type_id, kg_co2eq in filtered_rows:
        try:
            et = EmissionType(emission_type_id)
        except ValueError:
            continue

        it_cat = _categorize_it_emission(et)
        if it_cat is None:
            continue

        category_kg[it_cat] += kg_co2eq

        if it_cat == IT_CATEGORY_CLOUD_AI:
            key = et.name.split("__")[-1]
            # Group AI providers under a single "ai" key
            parent = et.parent
            if parent is not None and parent.name.startswith("external__ai"):
                key = "ai"
            cloud_ai_detail[key] = cloud_ai_detail.get(key, 0.0) + kg_co2eq

    total_it_kg = sum(category_kg.values())
    total_it_tonnes = total_it_kg / 1000.0
    total_it_per_fte = (total_it_kg / total_fte / 1000.0) if total_fte > 0 else 0.0

    percentage_of_total = (
        (total_it_kg / total_emissions_kg * 100.0) if total_emissions_kg > 0 else 0.0
    )

    # Build scope breakdown
    scope_2_kg = category_kg[IT_CATEGORY_EQUIPMENT]
    scope_3_kg = (
        category_kg[IT_CATEGORY_PURCHASES]
        + category_kg[IT_CATEGORY_CLOUD_AI]
        + category_kg[IT_CATEGORY_RESEARCH]
    )

    # Determine validation status (skip categories whose module is excluded)
    active_categories = [
        ck
        for ck in IT_CATEGORIES_ORDER
        if not _IT_CATEGORY_MODULE_IDS[ck].issubset(exclude)
    ]
    validated_sources: list[str] = []
    for cat_key in IT_CATEGORIES_ORDER:
        module_ids = _IT_CATEGORY_MODULE_IDS[cat_key]
        if module_ids.issubset(exclude):
            continue
        if module_ids.issubset(validated_ids):
            validated_sources.append(cat_key)

    all_validated = len(active_categories) > 0 and len(validated_sources) == len(
        active_categories
    )
    partially_validated = len(validated_sources) > 0 and not all_validated

    # Build categories list
    tc_detail = top_class_detail or {}
    categories: list[dict[str, Any]] = []
    for cat_key in IT_CATEGORIES_ORDER:
        kg = category_kg[cat_key]
        cat_entry: dict[str, Any] = {
            "category_key": cat_key,
            "tonnes_co2eq": kg / 1000.0,
            "percentage": (kg / total_it_kg * 100.0) if total_it_kg > 0 else 0.0,
        }
        if cat_key == IT_CATEGORY_CLOUD_AI and cloud_ai_detail:
            cat_entry["emissions"] = [
                {"key": k, "value": v / 1000.0}
                for k, v in sorted(cloud_ai_detail.items())
            ]
            # Cloud & AI: use sub-breakdown keys (ai, stockage, etc.)
            cat_entry["top_items"] = [
                {"name": k, "value": v / 1000.0}
                for k, v in sorted(cloud_ai_detail.items(), key=lambda x: -x[1])
            ]
        elif cat_key in tc_detail:
            # Equipment IT / Purchases IT: flatten top-class children
            items: list[dict[str, Any]] = []
            for subcategory in tc_detail[cat_key]:
                for child in subcategory.get("children", []):
                    items.append(
                        {
                            "name": child["name"],
                            "value": child["value"] / 1000.0,  # kg → tonnes
                        }
                    )
            # Sort descending by value, "rest" always last
            items.sort(key=lambda x: (x["name"] == "rest", -x["value"]))
            cat_entry["top_items"] = items
        categories.append(cat_entry)

    return {
        "total_it_tonnes_co2eq": total_it_tonnes,
        "total_it_per_fte": total_it_per_fte,
        "percentage_of_total": percentage_of_total,
        "categories": categories,
        "scope_breakdown": {
            "scope_2": scope_2_kg / 1000.0,
            "scope_3": scope_3_kg / 1000.0,
        },
        "validated": all_validated,
        "partially_validated": partially_validated,
        "validated_sources": validated_sources,
    }
