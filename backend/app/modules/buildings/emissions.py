"""Emission resolution for the buildings module."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType, FactorLike

# Buildings straddles the scope bands: fuel combustion and thermal heating are
# direct scope-1 emissions, electrically driven rooms are scope 2, and
# construction/renovation is embodied (scope 3, informative only).
STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="buildings_energy_combustion",
        scope=1,
        roots=(
            EmissionType.buildings__combustion,
            EmissionType.buildings__rooms__heating_thermal,
        ),
    ),
    StatBucket(
        key="buildings_room",
        scope=2,
        roots=(EmissionType.buildings__rooms,),
        exclude=(EmissionType.buildings__rooms__heating_thermal,),
    ),
    StatBucket(
        key="embodied_energy",
        scope=3,
        roots=(EmissionType.buildings__construction_and_renovation,),
        additional=True,
    ),
)

_VALID_ROOM_TYPES: frozenset[str] = frozenset(
    {
        "office",
        "laboratories",
        "archives",
        "libraries",
        "auditoriums",
        "miscellaneous",
    }
)

_NON_HEATING_ENERGIES: tuple[str, ...] = ("lighting", "cooling", "ventilation")

_HEATING_LEAF_BY_ENERGY: dict[str, str] = {
    "electric": "heating_electric",
    "thermal": "heating_thermal",
}

BUILDING_ENERGY_TYPES: frozenset[str] = frozenset(_HEATING_LEAF_BY_ENERGY)


def _heating_leaf_for_factor(factor: FactorLike | None) -> str | None:
    if factor is None:
        return None
    energy_type = factor.classification.get("energy_type")
    heating_leaf = _HEATING_LEAF_BY_ENERGY.get((energy_type or "").lower())
    if heating_leaf is None:
        raise ValueError(
            f"Building factor {factor.id} has invalid energy_type "
            f"{energy_type!r}; expected one of {sorted(BUILDING_ENERGY_TYPES)}."
        )
    return heating_leaf


def resolve_building_rooms(
    data: dict,
    factor: FactorLike | None,
) -> list[EmissionType]:
    energies = list(_NON_HEATING_ENERGIES)
    heating_leaf = _heating_leaf_for_factor(factor)
    if heating_leaf is not None:
        energies.append(heating_leaf)

    room_type = (data.get("room_type") or "").lower()
    suffix = f"__{room_type}" if room_type in _VALID_ROOM_TYPES else ""

    result = []
    for energy in energies:
        parent = f"buildings__rooms__{energy}"
        try:
            result.append(EmissionType[f"{parent}{suffix}"])
        except KeyError:
            result.append(EmissionType[parent])
    return result


def resolve_combustion(data: dict) -> list[EmissionType]:
    name = (data.get("name") or "").lower().replace(" ", "_")
    emission_type_name = f"{EmissionType.buildings__combustion.name}__{name}"
    try:
        return [EmissionType[emission_type_name]]
    except KeyError:
        return [EmissionType.buildings__combustion]
