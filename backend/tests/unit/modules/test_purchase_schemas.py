"""Tests for purchase factor DTO validation."""

import pytest
from pydantic import ValidationError

from app.modules.purchase import (
    PurchaseCommonFactorCreate,
    PurchaseHandlerUpdate,
)


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


# ---------------------------------------------------------------------------
# PurchaseHandlerUpdate.purchase_institutional_code
#
# Regression: the old resolver raised loudly on ANY falsy kind ("" or null),
# so a PATCH clearing purchase_institutional_code surfaced as HTTP 400. The
# new resolver returns None for a missing kind (correct recalc semantics),
# which means rejection must now happen at the DTO validation layer.
# PATCH semantics: key ABSENT = "not updating" (accepted); key PRESENT with
# blank/whitespace/null = rejected.
# ---------------------------------------------------------------------------


def _update_payload(**overrides):
    payload = {
        "data_entry_type_id": 1,
        "carbon_report_module_id": 1,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "bad_code", ["", "   ", None], ids=["empty", "whitespace", "explicit-null"]
)
def test_update_falsy_institutional_code_rejected(bad_code):
    with pytest.raises(ValidationError, match="purchase_institutional_code"):
        PurchaseHandlerUpdate.model_validate(
            _update_payload(purchase_institutional_code=bad_code)
        )


def test_update_null_institutional_code_under_data_rejected():
    # The payload mixin can carry fields nested under "data"; explicit null
    # must be rejected in that shape too.
    with pytest.raises(ValidationError, match="purchase_institutional_code"):
        PurchaseHandlerUpdate.model_validate(
            _update_payload(data={"purchase_institutional_code": None})
        )


def test_update_missing_institutional_code_accepted():
    # Key absent from the PATCH means "not updating this field".
    dto = PurchaseHandlerUpdate.model_validate(_update_payload())
    assert dto.purchase_institutional_code is None


def test_update_valid_institutional_code_accepted():
    dto = PurchaseHandlerUpdate.model_validate(
        _update_payload(purchase_institutional_code="51100000")
    )
    assert dto.purchase_institutional_code == "51100000"
