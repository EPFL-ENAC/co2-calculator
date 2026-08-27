"""Unit tests for the research-facilities create/update DTOs (#1489, audit F-7).

The animal Create DTO shipped with zero validators, so ``use = -5`` and
whitespace-only identifiers were accepted while the common DTO rejected
them — the same documented rules ("use >= 0", non-empty ids) must hold on
both handlers and on update as well as create.
"""

import pytest
from pydantic import ValidationError

from app.modules.research_facilities import (
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesAnimalHandlerUpdate,
    ResearchFacilitiesCommonHandlerCreate,
    ResearchFacilitiesCommonHandlerUpdate,
)

_BASE = {"data_entry_type_id": 71, "carbon_report_module_id": 1}


def _animal_create(**overrides) -> ResearchFacilitiesAnimalHandlerCreate:
    payload = {
        **_BASE,
        "researchfacility_id": "F1",
        "researchfacility_name": "Animal facility",
        "researchfacility_type": "mice",
        "use": 10.0,
        "use_unit": "chf",
        **overrides,
    }
    return ResearchFacilitiesAnimalHandlerCreate.model_validate(payload)


def test_animal_create_valid() -> None:
    dto = _animal_create()
    assert dto.data["use"] == 10.0


def test_animal_create_rejects_negative_use() -> None:
    with pytest.raises(ValidationError, match="positive number or zero"):
        _animal_create(use=-5)


def test_animal_create_rejects_non_numeric_use() -> None:
    with pytest.raises(ValidationError, match="must be a number"):
        _animal_create(use="abc")


def test_animal_create_rejects_whitespace_only_strings() -> None:
    for field in (
        "researchfacility_id",
        "researchfacility_name",
        "researchfacility_type",
        "use_unit",
    ):
        with pytest.raises(ValidationError, match="cannot be empty"):
            _animal_create(**{field: "   "})


def test_animal_create_rejects_null_id() -> None:
    with pytest.raises(ValidationError, match="researchfacility_id is required"):
        _animal_create(researchfacility_id=None)


def test_animal_update_rejects_negative_use_but_allows_absent() -> None:
    assert ResearchFacilitiesAnimalHandlerUpdate.model_validate(_BASE).use is None
    with pytest.raises(ValidationError, match="positive number or zero"):
        ResearchFacilitiesAnimalHandlerUpdate.model_validate({**_BASE, "use": -1})


def test_animal_update_rejects_whitespace_only_type() -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        ResearchFacilitiesAnimalHandlerUpdate.model_validate(
            {**_BASE, "researchfacility_type": " "}
        )


def test_common_create_rejects_whitespace_only_use_unit() -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        ResearchFacilitiesCommonHandlerCreate.model_validate(
            {
                **_BASE,
                "researchfacility_id": "F1",
                "researchfacility_name": "Facility",
                "use": 1.0,
                "use_unit": "  ",
            }
        )


def test_common_update_rejects_negative_use_but_allows_absent() -> None:
    assert ResearchFacilitiesCommonHandlerUpdate.model_validate(_BASE).use is None
    with pytest.raises(ValidationError, match="positive number or zero"):
        ResearchFacilitiesCommonHandlerUpdate.model_validate({**_BASE, "use": -1})
