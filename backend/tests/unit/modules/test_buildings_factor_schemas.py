"""Regression tests for #2586: grey energy factor category must be
rejected at import time, not only when the stored row is read back.
"""

import pytest
from pydantic import ValidationError

from app.modules.buildings.factors import (
    EMBODIED_ENERGY_CATEGORIES,
    BuildingEmbodiedEnergyFactorCreate,
    BuildingEmbodiedEnergyFactorResponse,
    BuildingEmbodiedEnergyFactorUpdate,
)


def _create_payload(**overrides: object) -> dict:
    payload: dict = {
        "emission_type_id": 1,
        "data_entry_type_id": 1,
        "building_name": "BC",
        "category": "new-tech",
        "ef_kgco2eq_per_m2": 12.5,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("category", sorted(EMBODIED_ENERGY_CATEGORIES))
def test_create_accepts_every_allowed_category(category: str) -> None:
    dto = BuildingEmbodiedEnergyFactorCreate(**_create_payload(category=category))
    assert dto.category == category


def test_create_strips_whitespace_around_category() -> None:
    dto = BuildingEmbodiedEnergyFactorCreate(**_create_payload(category=" demolition "))
    assert dto.category == "demolition"


def test_create_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError, match="must be one of"):
        BuildingEmbodiedEnergyFactorCreate(**_create_payload(category="new-teck"))


def test_create_rejects_blank_category() -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        BuildingEmbodiedEnergyFactorCreate(**_create_payload(category="   "))


def test_update_keeps_category_optional() -> None:
    dto = BuildingEmbodiedEnergyFactorUpdate()
    assert dto.category is None


def test_update_validates_category_when_given() -> None:
    dto = BuildingEmbodiedEnergyFactorUpdate(category="ren-env")
    assert dto.category == "ren-env"
    with pytest.raises(ValidationError, match="must be one of"):
        BuildingEmbodiedEnergyFactorUpdate(category="renovation")


def test_response_still_validates_category() -> None:
    with pytest.raises(ValidationError, match="must be one of"):
        BuildingEmbodiedEnergyFactorResponse(**_create_payload(id=1, category="typo"))
