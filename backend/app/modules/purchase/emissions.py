"""Emission resolution for purchases."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(key="purchases", scope=3, roots=(EmissionType.purchases,)),
)

_CENTRALIZED_PURCHASES_MAP: dict[str, EmissionType] = {
    "ln2": EmissionType.purchases__centralized__ln2,
}


def resolve_purchases_centralized(data: dict) -> list[EmissionType]:
    name = (data.get("name") or "").lower().replace(" ", "_")
    emission_type = _CENTRALIZED_PURCHASES_MAP.get(name)
    if emission_type:
        return [emission_type]
    return [EmissionType.purchases__centralized]
