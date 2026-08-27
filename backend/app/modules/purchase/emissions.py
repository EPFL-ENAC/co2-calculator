"""Emission resolution for purchases."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
    canonical_token,
)

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(key="purchases", scope=3, roots=(EmissionType.purchases,)),
)

_CENTRALIZED_PURCHASES_MAP: dict[str, EmissionType] = {
    "ln2": EmissionType.purchases__centralized__ln2,
    # The shipped purchases_centralized_factors.csv spells it out; without
    # this the row degraded onto the parent node (#2091).
    "liquid_nitrogen": EmissionType.purchases__centralized__ln2,
}


def resolve_purchases_centralized(data: dict) -> list[EmissionType]:
    name = canonical_token(data.get("name"))
    emission_type = _CENTRALIZED_PURCHASES_MAP.get(name)
    if emission_type is None:
        raise EmissionTypeResolutionError(
            f"No emission type for centralized purchase {name!r} — "
            f"expected one of {sorted(_CENTRALIZED_PURCHASES_MAP)}"
        )
    return [emission_type]
