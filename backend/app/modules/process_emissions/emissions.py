"""Emission resolution for process emissions."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="process_emissions", scope=1, roots=(EmissionType.process_emissions,)
    ),
)

_PROCESS_GAS_MAP: dict[str, EmissionType] = {
    "ch4": EmissionType.process_emissions__ch4,
    "co2": EmissionType.process_emissions__co2,
    "n2o": EmissionType.process_emissions__n2o,
    "refrigerants": EmissionType.process_emissions__refrigerants,
    "refrigerant": EmissionType.process_emissions__refrigerants,
}


def resolve_process_emissions(data: dict) -> list[EmissionType] | None:
    gas = data.get("category", (data.get("kind", "") or "")).lower()
    emission_type = _PROCESS_GAS_MAP.get(gas)
    return [emission_type] if emission_type else None
