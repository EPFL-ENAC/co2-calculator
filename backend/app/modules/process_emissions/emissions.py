"""Emission resolution for process emissions."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
)

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(
        key="process_emissions", scope=1, roots=(EmissionType.process_emissions,)
    ),
)

_PROCESS_GAS_MAP: dict[str, EmissionType] = {
    # Short codes: data-entry rows (processemissions_data.csv `category`,
    # e.g. "CO2", "CH4") use these directly.
    "ch4": EmissionType.process_emissions__ch4,
    "co2": EmissionType.process_emissions__co2,
    "n2o": EmissionType.process_emissions__n2o,
    "refrigerants": EmissionType.process_emissions__refrigerants,
    "refrigerant": EmissionType.process_emissions__refrigerants,
    # Descriptive names: factor rows (processemissions_factors.csv
    # `category`) spell the gas out, one leaf per gas family (#2091).
    "carbon dioxide (co2)": EmissionType.process_emissions__co2,
    "methane (ch4)": EmissionType.process_emissions__ch4,
    "nitrous oxide (n2o)": EmissionType.process_emissions__n2o,
    "sulfur hexafluoride (sf6)": EmissionType.process_emissions__sf6,
    "nitrogen trifluoride (nf3)": EmissionType.process_emissions__nf3,
    "hydrofluorocarbons (hfcs)": EmissionType.process_emissions__hfcs,
    "perfluorinated compounds": (
        EmissionType.process_emissions__perfluorinated_compounds
    ),
    "fluorinated ethers": EmissionType.process_emissions__fluorinated_ethers,
    "perfluoropolyethers": EmissionType.process_emissions__perfluoropolyethers,
}


def resolve_process_emissions(data: dict) -> list[EmissionType]:
    gas = data.get("category", (data.get("kind", "") or "")).lower()
    emission_type = _PROCESS_GAS_MAP.get(gas)
    if emission_type is None:
        raise EmissionTypeResolutionError(
            f"No emission type for process-emissions category {gas!r} — "
            f"expected one of {sorted(_PROCESS_GAS_MAP)}"
        )
    return [emission_type]
