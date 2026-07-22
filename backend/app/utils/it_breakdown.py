"""IT emission categorisation over the persisted stats maps.

Aggregates IT-related emissions from four source modules:

- **Equipment** (``equipment__it``): IT device electricity consumption (Scope 2)
- **Purchases** (``purchases__it_equipment``): IT hardware procurement (Scope 3)
- **External Cloud & AI** (all ``external__clouds__*`` and ``external__ai__*``):
  cloud computing and AI provider emissions (Scope 3)
- **Research Facilities** (``research_facilities__*``): IT-related research
  facility emissions (Scope 3)
"""

from app.modules.emissions import EmissionType, get_children, resolve_emission_type

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
        EmissionType.research_facilities__animal__rodent,
        EmissionType.research_facilities__animal__fish,
        EmissionType.research_facilities__it_facilities,
    ]
)

IT_EMISSION_TYPES: frozenset[EmissionType] = (
    _IT_EQUIPMENT_TYPES | _IT_PURCHASES_TYPES | _IT_CLOUD_AI_TYPES | _IT_RESEARCH_TYPES
)

# Ordered list of IT categories for deterministic output
IT_CATEGORIES_ORDER: list[str] = [
    IT_CATEGORY_EQUIPMENT,
    IT_CATEGORY_PURCHASES,
    IT_CATEGORY_CLOUD_AI,
    IT_CATEGORY_RESEARCH,
]

# IT category -> the stat bucket its source module reports under; used to
# derive per-category validation from a report's validated_buckets list.
IT_CATEGORY_TO_BUCKET_KEY: dict[str, str] = {
    IT_CATEGORY_EQUIPMENT: "equipment",
    IT_CATEGORY_PURCHASES: "purchases",
    IT_CATEGORY_CLOUD_AI: "external_cloud_and_ai",
    IT_CATEGORY_RESEARCH: "research_facilities",
}


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


def build_it_category_totals(by_emission_type: dict[str, float]) -> dict[str, float]:
    """Sum a flat ``by_emission_type`` map into IT category totals.

    Only childless nodes count: non-leaf values in the map are subtree
    rollups, and the IT type sets include both, so summing everything would
    double-count.
    """
    totals = {cat: 0.0 for cat in IT_CATEGORIES_ORDER}
    for et_id_str, kg_co2eq in by_emission_type.items():
        emission_type = resolve_emission_type(int(et_id_str))
        if emission_type is None or get_children(emission_type):
            continue
        category = _categorize_it_emission(emission_type)
        if category is not None:
            totals[category] += kg_co2eq or 0.0
    return totals


def build_cloud_ai_detail(by_emission_type: dict[str, float]) -> dict[str, float]:
    """Cloud & AI sub-detail in kg: cloud leaves by name, AI grouped as "ai"."""
    detail: dict[str, float] = {}
    for et_id_str, kg_co2eq in by_emission_type.items():
        emission_type = resolve_emission_type(int(et_id_str))
        if emission_type is None or emission_type not in _IT_CLOUD_AI_TYPES:
            continue
        key = emission_type.name.split("__")[-1]
        if emission_type.parent is EmissionType.external__ai:
            key = "ai"
        detail[key] = detail.get(key, 0.0) + (kg_co2eq or 0.0)
    return detail
