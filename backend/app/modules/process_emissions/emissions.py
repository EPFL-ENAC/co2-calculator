"""Emission resolution for process emissions."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

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
    # `category`) spell the gas out. The taxonomy has no leaf per
    # fluorinated gas, so every synthetic/F-gas here — SF6, NF3, HFCs,
    # PFCs, fluorinated ethers, perfluoropolyethers — rolls into the
    # existing "refrigerants" bucket (#2091: finer-grained buckets are a
    # taxonomy decision for the lead, not made here).
    "carbon dioxide (co2)": EmissionType.process_emissions__co2,
    "methane (ch4)": EmissionType.process_emissions__ch4,
    "nitrous oxide (n2o)": EmissionType.process_emissions__n2o,
    "sulfur hexafluoride (sf6)": EmissionType.process_emissions__refrigerants,
    "nitrogen trifluoride (nf3)": EmissionType.process_emissions__refrigerants,
    "hydrofluorocarbons (hfcs)": EmissionType.process_emissions__refrigerants,
    "perfluorinated compounds": EmissionType.process_emissions__refrigerants,
    "fluorinated ethers": EmissionType.process_emissions__refrigerants,
    "perfluoropolyethers": EmissionType.process_emissions__refrigerants,
}


def resolve_process_emissions(data: dict) -> list[EmissionType] | None:
    gas = data.get("category", (data.get("kind", "") or "")).lower()
    emission_type = _PROCESS_GAS_MAP.get(gas)
    return [emission_type] if emission_type else None
