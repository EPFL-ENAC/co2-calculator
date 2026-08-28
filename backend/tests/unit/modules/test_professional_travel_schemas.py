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
from app.modules.professional_travel.emissions import (
    PLANE_CABIN_MAP,
    TRAIN_CLASS_MAP,
)
from app.modules.professional_travel.factors import TravelPlaneFactorCreate

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


# cabin_class validators must accept exactly the emission-map keys —
# "first" (removed in #1567) passed plane validation but could not resolve
# an emission type (found during #2391 decision 6).

_PLANE_FACTOR = {
    "emission_type_id": 1,
    "data_entry_type_id": 1,
    "category": "short_haul",
    "cabin_class": "economy",
    "ef_kg_co2eq_per_km": 0.1,
    "rfi_adjustment": 2.0,
    "min_distance": 0.0,
    "max_distance": 1500.0,
}


@pytest.mark.parametrize("cabin_class", sorted(PLANE_CABIN_MAP))
def test_plane_create_accepts_each_cabin_map_key(cabin_class: str) -> None:
    item = ProfessionalTravelPlaneHandlerCreate.model_validate(
        {**_PLANE_META, "user_institutional_id": None, "cabin_class": cabin_class}
    )
    assert item.cabin_class == cabin_class


@pytest.mark.parametrize("cabin_class", ["first", "eco", "premium"])
def test_plane_create_rejects_classes_outside_cabin_map(cabin_class: str) -> None:
    with pytest.raises(ValidationError, match="cabin class"):
        ProfessionalTravelPlaneHandlerCreate.model_validate(
            {**_PLANE_META, "user_institutional_id": None, "cabin_class": cabin_class}
        )


@pytest.mark.parametrize("cabin_class", sorted(TRAIN_CLASS_MAP))
def test_train_create_accepts_each_class_map_key(cabin_class: str) -> None:
    item = ProfessionalTravelTrainHandlerCreate.model_validate(
        {**_TRAIN_META, "user_institutional_id": None, "cabin_class": cabin_class}
    )
    assert item.cabin_class == cabin_class


@pytest.mark.parametrize("cabin_class", ["economy", "business", "third"])
def test_train_create_rejects_classes_outside_class_map(cabin_class: str) -> None:
    with pytest.raises(ValidationError, match="cabin class"):
        ProfessionalTravelTrainHandlerCreate.model_validate(
            {**_TRAIN_META, "user_institutional_id": None, "cabin_class": cabin_class}
        )


@pytest.mark.parametrize("cabin_class", sorted(PLANE_CABIN_MAP))
def test_plane_factor_create_accepts_each_cabin_map_key(cabin_class: str) -> None:
    item = TravelPlaneFactorCreate.model_validate(
        {**_PLANE_FACTOR, "cabin_class": cabin_class}
    )
    assert item.cabin_class == cabin_class


@pytest.mark.parametrize("cabin_class", ["first", "eco", "premium"])
def test_plane_factor_create_rejects_classes_outside_cabin_map(
    cabin_class: str,
) -> None:
    with pytest.raises(ValidationError, match="cabin class"):
        TravelPlaneFactorCreate.model_validate(
            {**_PLANE_FACTOR, "cabin_class": cabin_class}
        )
