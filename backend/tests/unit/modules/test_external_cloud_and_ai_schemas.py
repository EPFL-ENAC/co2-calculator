"""External AI handler validation — requests_per_user_per_day."""

import pytest
from pydantic import ValidationError

from app.models.data_entry import DataEntryTypeEnum
from app.modules.external_cloud_and_ai import (
    ExternalAIHandlerCreate,
    ExternalCloudFactorCreate,
    ExternalCloudHandlerCreate,
    ExternalCloudHandlerUpdate,
)

_META = {
    "data_entry_type_id": DataEntryTypeEnum.external_ai.value,
    "carbon_report_module_id": 1,
}


@pytest.mark.parametrize(
    "frequency",
    [
        "1_5",
        "5_20",
        "20_100",
        "gt_100",
    ],
)
def test_external_ai_create_accepts_frequency_codes(frequency: str) -> None:
    payload = ExternalAIHandlerCreate.model_validate(
        {
            **_META,
            "provider": "Gemini (Google)",
            "usage_type": "text",
            "requests_per_user_per_day": frequency,
            "fte_count": 0.8,
        }
    )
    assert payload.requests_per_user_per_day == frequency


def test_external_ai_create_rejects_legacy_frequency_labels() -> None:
    with pytest.raises(ValidationError):
        ExternalAIHandlerCreate.model_validate(
            {
                **_META,
                "provider": "Gemini (Google)",
                "usage_type": "text",
                "requests_per_user_per_day": "1-5 times per day",
                "fte_count": 0.8,
            }
        )


def test_external_ai_create_rejects_unknown_frequency() -> None:
    with pytest.raises(ValidationError):
        ExternalAIHandlerCreate.model_validate(
            {
                **_META,
                "provider": "Gemini (Google)",
                "usage_type": "text",
                "requests_per_user_per_day": "daily",
                "fte_count": 0.8,
            }
        )


# ---------------------------------------------------------------------------
# Currency handling on cloud DTOs (#1489)
# ---------------------------------------------------------------------------

_CLOUD_META = {
    "data_entry_type_id": DataEntryTypeEnum.external_clouds.value,
    "carbon_report_module_id": 1,
}


def _cloud_entry_payload(**overrides):
    payload = {
        **_CLOUD_META,
        "service_type": "storage",
        "provider": "AWS",
        "spent_amount": 10.0,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("missing", [{}, {"currency": None}, {"currency": "  "}])
def test_cloud_entry_defaults_currency_to_eur(missing):
    dto = ExternalCloudHandlerCreate.model_validate(_cloud_entry_payload(**missing))
    assert dto.currency == "eur"
    assert dto.data["currency"] == "eur"


def test_cloud_entry_default_does_not_mutate_caller_payload():
    # Regression: ensure_default_currency used to write the default into the
    # caller's dict, leaking it upstream of validation (#1489).
    payload = _cloud_entry_payload()
    ExternalCloudHandlerCreate.model_validate(payload)
    assert "currency" not in payload


def test_cloud_entry_unknown_currency_rejected():
    with pytest.raises(ValidationError, match="Currency must be one of"):
        ExternalCloudHandlerCreate.model_validate(_cloud_entry_payload(currency="btc"))


def test_cloud_entry_update_currency_vocabulary():
    assert (
        ExternalCloudHandlerUpdate.model_validate(
            {**_CLOUD_META, "currency": "CHF"}
        ).currency
        == "chf"
    )
    with pytest.raises(ValidationError, match="Currency must be one of"):
        ExternalCloudHandlerUpdate.model_validate({**_CLOUD_META, "currency": "btc"})


def _cloud_factor_payload(**overrides):
    payload = {
        "emission_type_id": 1,
        "data_entry_type_id": DataEntryTypeEnum.external_clouds.value,
        "service_type": "storage",
        "provider": "AWS",
        "currency": "CHF",
        "ef_kg_co2eq_per_currency": 0.5,
    }
    payload.update(overrides)
    return payload


def test_cloud_factor_currency_normalized_then_vocabulary_checked():
    factor = ExternalCloudFactorCreate.model_validate(_cloud_factor_payload())
    assert factor.currency == "chf"


def test_cloud_factor_unknown_currency_rejected():
    with pytest.raises(ValidationError, match="Invalid currency"):
        ExternalCloudFactorCreate.model_validate(_cloud_factor_payload(currency="btc"))
