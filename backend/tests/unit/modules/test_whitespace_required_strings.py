"""Whitespace-only values in required string fields are rejected (#1489, audit F-10).

Equipment, headcount and common research facilities already rejected
`"   "` in required strings while process emissions, purchase, buildings,
cloud/AI and travel accepted it — a whitespace category then fails factor
matching downstream, silently. These tests pin the rule on every module
that gained it, on create and (present-value) update alike.
"""

import pytest
from pydantic import ValidationError

from app.modules.buildings import (
    BuildingRoomHandlerCreate,
    EnergyCombustionHandlerCreate,
)
from app.modules.external_cloud_and_ai import (
    ExternalAIHandlerCreate,
    ExternalCloudHandlerCreate,
)
from app.modules.process_emissions import (
    ProcessEmissionsHandlerCreate,
    ProcessEmissionsHandlerUpdate,
)
from app.modules.professional_travel import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
)
from app.modules.purchase import (
    PurchaseCentralizedHandlerCreate,
    PurchaseHandlerCreate,
)

_META = {"data_entry_type_id": 50, "carbon_report_module_id": 1}

# (dto, valid base payload, fields that must reject "   ")
_CASES = [
    (
        ProcessEmissionsHandlerCreate,
        {"category": "CH4", "quantity_kg": 1.0},
        ["category"],
    ),
    (
        PurchaseHandlerCreate,
        {"name": "p", "total_spent_amount": 1.0, "purchase_institutional_code": "1234"},
        ["name"],
    ),
    (
        PurchaseCentralizedHandlerCreate,
        {"name": "p", "unit": "kg", "annual_consumption": 1.0, "coef_to_kg": 1.0},
        ["name", "unit"],
    ),
    (
        BuildingRoomHandlerCreate,
        {"building_name": "B", "room_name": "R", "room_type": "office"},
        ["building_name", "room_name"],
    ),
    (
        EnergyCombustionHandlerCreate,
        {"name": "natural_gas", "quantity": 1.0},
        ["name"],
    ),
    (
        ExternalCloudHandlerCreate,
        {"service_type": "storage", "provider": "AWS", "spent_amount": 1.0},
        ["service_type", "provider"],
    ),
    (
        ExternalAIHandlerCreate,
        {
            "provider": "Google",
            "usage_type": "chat",
            "requests_per_user_per_day": "1_5",
            "fte_count": 1.0,
        },
        ["provider", "usage_type"],
    ),
    (
        ProfessionalTravelPlaneHandlerCreate,
        {
            "origin_iata": "GVA",
            "destination_iata": "JFK",
            "user_institutional_id": None,
            "number_of_trips": 1,
            "cabin_class": "economy",
        },
        ["origin_iata", "destination_iata"],
    ),
    (
        ProfessionalTravelTrainHandlerCreate,
        {
            "origin_name": "Lausanne",
            "origin_country_code": "CH",
            "destination_name": "Paris",
            "destination_country_code": "FR",
            "user_institutional_id": None,
            "number_of_trips": 1,
            "cabin_class": "first",
        },
        [
            "origin_name",
            "destination_name",
            "origin_country_code",
            "destination_country_code",
        ],
    ),
]


@pytest.mark.parametrize(
    ("dto", "base", "field"),
    [(dto, base, f) for dto, base, fields in _CASES for f in fields],
    ids=lambda v: v if isinstance(v, str) else getattr(v, "__name__", ""),
)
def test_whitespace_only_required_string_rejected(dto, base, field) -> None:
    dto.model_validate({**_META, **base})  # the base payload itself is valid
    with pytest.raises(ValidationError, match="cannot be empty"):
        dto.model_validate({**_META, **base, field: "   "})


def test_update_rejects_whitespace_but_allows_absent() -> None:
    assert (
        ProcessEmissionsHandlerUpdate.model_validate(
            {**_META, "quantity_kg": 2.0}
        ).category
        is None
    )
    with pytest.raises(ValidationError, match="cannot be empty"):
        ProcessEmissionsHandlerUpdate.model_validate({**_META, "category": " "})
