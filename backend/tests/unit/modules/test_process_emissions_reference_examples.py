"""Process-emissions reference examples (#2771): quantity_kg × GWP.

Rows: back-office doc, "test calculation processemissions_factors".
GWPs: processemissions_factors.csv, ``ef_kg_co2eq_per_unit``.
"""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.process_emissions import ProcessEmissionsModuleHandler
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq

_HANDLER = ProcessEmissionsModuleHandler()


@pytest.mark.parametrize(
    ("category", "quantity_kg", "gwp", "expected_kg"),
    [
        pytest.param("Carbon dioxide (CO2)", 100, 1.0, 100, id="CO2"),
        pytest.param("Methane (CH4)", 50, 27.0, 1350, id="CH4"),
        pytest.param("Nitrous oxide (N2O)", 10, 273.0, 2730, id="N2O"),
        pytest.param("Hydrofluorocarbons (HFCs)", 5, 14600.0, 73000, id="HFC-23"),
        pytest.param("Hydrofluorocarbons (HFCs)", 10, 3740.0, 37400, id="HFC-125"),
        pytest.param("Hydrofluorocarbons (HFCs)", 2, 1530.0, 3060, id="HFC-134a"),
        pytest.param("Sulfur hexafluoride (SF6)", 0.5, 24300.0, 12150, id="SF6"),
        pytest.param("Nitrogen trifluoride (NF3)", 1, 17400.0, 17400, id="NF3"),
        pytest.param("Perfluorinated compounds", 3, 7380.0, 22140, id="PFC-14"),
        pytest.param("Fluorinated ethers", 1.5, 6630.0, 9945, id="HFE-134"),
    ],
)
def test_process_emissions_reference_example(
    category: str, quantity_kg: float, gwp: float, expected_kg: float
) -> None:
    kg = compute_kg_co2eq(
        _HANDLER,
        DataEntryTypeEnum.process_emissions,
        {"category": category, "quantity_kg": quantity_kg},
        {"ef_kg_co2eq_per_unit": gwp},
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)
