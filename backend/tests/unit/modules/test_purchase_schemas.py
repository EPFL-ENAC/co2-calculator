"""Tests for purchase factor DTO validation."""

import pytest
from pydantic import ValidationError

from app.modules.purchase.schemas import PurchaseCommonFactorCreate


def _factor_payload(**overrides):
    payload = {
        "emission_type_id": 1,
        "data_entry_type_id": 1,
        "currency": "eur",
        "purchase_institutional_code": "51100000",
        "purchase_additional_code": "LA05",
        "ef_kg_co2eq_per_currency": 0.41,
    }
    payload.update(overrides)
    return payload


def test_factor_with_both_codes_is_valid():
    factor = PurchaseCommonFactorCreate.model_validate(_factor_payload())
    assert factor.purchase_institutional_code == "51100000"


def test_factor_average_row_without_additional_code_is_valid():
    factor = PurchaseCommonFactorCreate.model_validate(
        _factor_payload(purchase_additional_code="")
    )
    assert factor.purchase_additional_code == ""


@pytest.mark.parametrize("bad_code", ["", "   "])
def test_factor_empty_institutional_code_rejected(bad_code):
    with pytest.raises(ValidationError, match="purchase_institutional_code"):
        PurchaseCommonFactorCreate.model_validate(
            _factor_payload(purchase_institutional_code=bad_code)
        )


def test_factor_missing_institutional_code_rejected():
    payload = _factor_payload()
    del payload["purchase_institutional_code"]
    with pytest.raises(ValidationError, match="purchase_institutional_code"):
        PurchaseCommonFactorCreate.model_validate(payload)
