"""Emission resolution for planner purchases (manual EUR totals)."""

from app.modules.emissions.taxonomy import EmissionType

# Submodule slug (mirrors the Calculator purchase DataEntryTypeEnum names)
# → purchases emission subtree. The global budget maps to the generic
# purchases__goods_and_services node instead (see registry).
PLANNER_PURCHASE_EMISSIONS: dict[str, EmissionType] = {
    "scientific_equipment": EmissionType.purchases__scientific_equipment,
    "it_equipment": EmissionType.purchases__it_equipment,
    "consumable_accessories": EmissionType.purchases__consumable_accessories,
    "biological_chemical_gaseous_product": (
        EmissionType.purchases__biological_chemical_gaseous
    ),
    "services": EmissionType.purchases__services,
    "vehicles": EmissionType.purchases__vehicles,
    "other_purchases": EmissionType.purchases__other,
    "purchases_centralized": EmissionType.purchases__centralized,
}

# Additional (centralized) purchases are priced per kg of product in the
# Calculator, not per EUR, so no average EF can be derived for them and an
# amount entered against the category stays unpriced.
PLANNER_PURCHASE_UNPRICED_CATEGORIES: frozenset[str] = frozenset(
    {"purchases_centralized"}
)


def resolve_planner_purchase(data: dict) -> list[EmissionType] | None:
    emission_type = PLANNER_PURCHASE_EMISSIONS.get(data.get("purchase_category", ""))
    return [emission_type] if emission_type else None
