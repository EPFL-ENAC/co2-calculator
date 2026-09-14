"""Headcount factor DTOs: closed vocabularies for the join keys (#2588).

``headcount_category``, ``headcount_class`` and ``unit`` are pinned to the
values the shipped factor CSVs carry (strip + lower first, like every other
closed vocabulary since #1489). A typo in a factor CSV must fail the upload,
not create a factor no computation can name.
"""

import pytest
from pydantic import ValidationError

from app.modules.headcount.factors import (
    HEADCOUNT_CATEGORIES,
    HEADCOUNT_CLASSES,
    HEADCOUNT_UNITS,
    HeadcountFactorCreate,
    HeadcountFactorUpdate,
)


def _payload(**overrides):
    payload = {
        "emission_type_id": 1,
        "data_entry_type_id": 1,
        "headcount_category": " Commuting ",
        "headcount_class": "CAR ",
        "headcount_subclass": "   ",
        "number_of_unit_per_fte": 1.0,
        "ef_kg_co2eq_per_unit": 0.1,
        "unit": " KM",
    }
    payload.update(overrides)
    return payload


def test_create_normalizes_vocabulary_keys_and_blank_subclass() -> None:
    factor = HeadcountFactorCreate.model_validate(_payload())
    assert factor.headcount_category == "commuting"
    assert factor.headcount_class == "car"
    assert factor.headcount_subclass is None
    assert factor.unit == "km"


@pytest.mark.parametrize(
    ("field", "allowed"),
    [
        ("headcount_category", HEADCOUNT_CATEGORIES),
        ("headcount_class", HEADCOUNT_CLASSES),
        ("unit", HEADCOUNT_UNITS),
    ],
)
def test_create_accepts_every_shipped_value(field: str, allowed: list[str]) -> None:
    for value in allowed:
        HeadcountFactorCreate.model_validate(_payload(**{field: value.upper()}))


@pytest.mark.parametrize("field", ["headcount_category", "headcount_class", "unit"])
def test_create_rejects_unknown_value_with_the_list(field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must be one of"):
        HeadcountFactorCreate.model_validate(_payload(**{field: "teleport"}))


def test_update_omitted_keys_untouched_and_present_keys_checked() -> None:
    update = HeadcountFactorUpdate.model_validate({"unit": " Kg "})
    assert update.unit == "kg"
    assert update.headcount_category is None
    with pytest.raises(ValidationError, match="headcount_class must be one of"):
        HeadcountFactorUpdate.model_validate({"headcount_class": "jetpack"})
