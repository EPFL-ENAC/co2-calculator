"""Units for the additional_value column, by taxonomy subtree."""

from app.modules.emissions.taxonomy import EmissionType

_UNIT_ROOTS: dict[EmissionType, str] = {
    EmissionType.commuting: "km",
    EmissionType.professional_travel: "km",
    EmissionType.food: "kg",
    EmissionType.waste: "kg",
}


def additional_value_unit(emission_type: EmissionType) -> str | None:
    """Unit of the additional_value column for a given EmissionType."""
    node: EmissionType | None = emission_type
    while node is not None:
        unit = _UNIT_ROOTS.get(node)
        if unit is not None:
            return unit
        node = node.parent
    return None
