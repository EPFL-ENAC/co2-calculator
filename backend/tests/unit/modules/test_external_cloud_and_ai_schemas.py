"""External AI handler validation — requests_per_user_per_day."""

import pytest
from pydantic import ValidationError

from app.models.data_entry import DataEntryTypeEnum
from app.modules.external_cloud_and_ai.schemas import ExternalAIHandlerCreate

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
