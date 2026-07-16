"""Emission resolution for planner purchases (manual CHF totals)."""

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
}


def resolve_planner_purchase(data: dict) -> list[EmissionType] | None:
    emission_type = PLANNER_PURCHASE_EMISSIONS.get(data.get("purchase_category", ""))
    return [emission_type] if emission_type else None
