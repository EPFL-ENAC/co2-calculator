"""Traveler sentinel validation for Professional Travel DTOs (#1153).

user_institutional_id is a free-text SCIPER string inside DataEntry.data —
no FK, no enum. "-1" (Internal other) and null (External other) must
validate on both the Create DTOs (frontend form submission, PR #1153/#2117)
and the Response DTOs (existing rows read back from the DB must not fail
serialization now that External-other rows persist a real null).
"""

import pytest
from pydantic import ValidationError

from app.modules.professional_travel.data_entries import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelPlaneHandlerResponse,
    ProfessionalTravelTrainHandlerCreate,
    ProfessionalTravelTrainHandlerResponse,
)

_PLANE_META = {
    "data_entry_type_id": 1,
    "carbon_report_module_id": 1,
    "data": {},
    "origin_iata": "GVA",
    "destination_iata": "ZRH",
    "cabin_class": "economy",
}
_TRAIN_META = {
    "data_entry_type_id": 2,
    "carbon_report_module_id": 1,
    "data": {},
    "origin_name": "Lausanne",
    "destination_name": "Geneva",
    "origin_country_code": "CH",
    "destination_country_code": "CH",
    "cabin_class": "second",
}


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_plane_create_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelPlaneHandlerCreate.model_validate(
        {**_PLANE_META, "user_institutional_id": sciper}
    )
    assert item.user_institutional_id == sciper


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_train_create_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelTrainHandlerCreate.model_validate(
        {**_TRAIN_META, "user_institutional_id": sciper}
    )
    assert item.user_institutional_id == sciper


def test_plane_create_still_requires_the_field() -> None:
    payload = {k: v for k, v in _PLANE_META.items()}
    with pytest.raises(ValidationError):
        ProfessionalTravelPlaneHandlerCreate.model_validate(payload)


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_plane_response_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelPlaneHandlerResponse.model_validate(
        {
            "id": 1,
            "data_entry_type_id": 1,
            "carbon_report_module_id": 1,
            "source": None,
            "user_institutional_id": sciper,
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
        }
    )
    assert item.user_institutional_id == sciper


@pytest.mark.parametrize("sciper", ["123456", "-1", None])
def test_train_response_accepts_sentinel_and_real_sciper(sciper) -> None:
    item = ProfessionalTravelTrainHandlerResponse.model_validate(
        {
            "id": 1,
            "data_entry_type_id": 2,
            "carbon_report_module_id": 1,
            "source": None,
            "user_institutional_id": sciper,
            "origin_name": "Lausanne",
            "destination_name": "Geneva",
        }
    )
    assert item.user_institutional_id == sciper
