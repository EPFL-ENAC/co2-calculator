"""Unit tests for process-emissions gas → EmissionType resolution.

Regression for the `make bootstrap-years` failures logged while
investigating #2174: `processemissions_factors.csv` spells gases out
("Carbon dioxide (CO2)") while `processemissions_data.csv` uses short
codes ("CO2") — the resolver must accept both.
"""

import pytest

from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
)
from app.modules.process_emissions.emissions import resolve_process_emissions


def test_resolve_process_emissions_accepts_short_code() -> None:
    assert resolve_process_emissions({"category": "CH4"}) == [
        EmissionType.process_emissions__ch4
    ]


def test_resolve_process_emissions_accepts_descriptive_factor_category() -> None:
    assert resolve_process_emissions({"category": "Carbon dioxide (CO2)"}) == [
        EmissionType.process_emissions__co2
    ]


def test_resolve_process_emissions_unknown_category_raises() -> None:
    # #2091: returning None let the factor-CSV provider skip the row and
    # finish WARNING, so the module silently lost a whole gas category.
    with pytest.raises(EmissionTypeResolutionError, match="unobtainium"):
        resolve_process_emissions({"category": "Unobtainium"})


def test_resolve_process_emissions_splits_fluorinated_families() -> None:
    # #2091: these four used to share process_emissions__refrigerants.
    assert resolve_process_emissions({"category": "Hydrofluorocarbons (HFCs)"}) == [
        EmissionType.process_emissions__hfcs
    ]
    assert resolve_process_emissions({"category": "Perfluorinated compounds"}) == [
        EmissionType.process_emissions__perfluorinated_compounds
    ]
    assert resolve_process_emissions({"category": "Fluorinated ethers"}) == [
        EmissionType.process_emissions__fluorinated_ethers
    ]
    assert resolve_process_emissions({"category": "Perfluoropolyethers"}) == [
        EmissionType.process_emissions__perfluoropolyethers
    ]
