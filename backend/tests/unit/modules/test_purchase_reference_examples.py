"""Centralized-purchase reference examples (#2771):
annual_consumption × coef_to_kg × ef.

Rows: back-office doc, "test calculation purchases_centralized". Factor:
purchases_centralized_factors.csv, Liquid Nitrogen ef_kg_co2eq_per_kg 0.1.

Common purchases are not covered: the doc's expected values do not follow
the code's formula (see the #2771 plan).
"""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.purchase import PurchaseCentralizedModuleHandler
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq


@pytest.mark.parametrize(
    ("annual_consumption", "coef_to_kg", "expected_kg"),
    [
        pytest.param(500, 0.808, 40.40, id="500-liters"),
        pytest.param(250, 0.808, 20.20, id="250-liters"),
        pytest.param(100, 1.0, 10.00, id="100-kg"),
        pytest.param(750, 0.808, 60.60, id="750-liters"),
        pytest.param(80, 1.0, 8.00, id="80-kg"),
    ],
)
def test_purchase_centralized_reference_example(
    annual_consumption: float, coef_to_kg: float, expected_kg: float
) -> None:
    ctx = {
        "name": "liquid nitrogen",
        "annual_consumption": annual_consumption,
        "coef_to_kg": coef_to_kg,
    }
    kg = compute_kg_co2eq(
        PurchaseCentralizedModuleHandler(),
        DataEntryTypeEnum.purchases_centralized,
        ctx,
        {"ef_kg_co2eq_per_kg": 0.1},
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)
