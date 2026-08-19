"""Unit tests for process-emissions gas → EmissionType resolution.

Regression for the `make bootstrap-years` failures logged while
investigating #2174: `processemissions_factors.csv` spells gases out
("Carbon dioxide (CO2)") while `processemissions_data.csv` uses short
codes ("CO2") — the resolver must accept both.
"""

from app.modules.emissions.taxonomy import EmissionType
from app.modules.process_emissions.emissions import resolve_process_emissions


def test_resolve_process_emissions_accepts_short_code() -> None:
    assert resolve_process_emissions({"category": "CH4"}) == [
        EmissionType.process_emissions__ch4
    ]


def test_resolve_process_emissions_accepts_descriptive_factor_category() -> None:
    assert resolve_process_emissions({"category": "Carbon dioxide (CO2)"}) == [
        EmissionType.process_emissions__co2
    ]


def test_resolve_process_emissions_maps_fluorinated_gases_to_refrigerants() -> None:
    for category in (
        "Sulfur hexafluoride (SF6)",
        "Nitrogen trifluoride (NF3)",
        "Hydrofluorocarbons (HFCs)",
        "Perfluorinated compounds",
        "Fluorinated ethers",
        "Perfluoropolyethers",
    ):
        assert resolve_process_emissions({"category": category}) == [
            EmissionType.process_emissions__refrigerants
        ], f"category={category!r}"


def test_resolve_process_emissions_unknown_category_returns_none() -> None:
    assert resolve_process_emissions({"category": "Unobtainium"}) is None
