from typing import Optional

from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.factor import (
    BaseFactorHandler,
    EmissionType,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


external_clouds_classification_fields: list[str] = [
    "service_type",
    "provider",
    "currency",
]
external_clouds_value_fields: list[str] = [
    "ef_kg_co2eq_per_currency",
]


class _ExternalCloudFactorValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_currency",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        valid_currencies = [
            "chf",
            "eur",
            "usd",
        ]
        if not v:
            raise ValueError("")
        if v.lower() not in valid_currencies:
            raise ValueError("Invalid currency")
        return v


class ExternalCloudBaseFactor:
    service_type: str
    provider: str
    currency: str
    ef_kg_co2eq_per_currency: float


class ExternalCloudFactorCreate(
    _ExternalCloudFactorValidationMixin, FactorCreate, ExternalCloudBaseFactor
):
    pass


class ExternalCloudFactorUpdate(
    _ExternalCloudFactorValidationMixin, FactorUpdate, ExternalCloudBaseFactor
):
    pass


class ExternalCloudFactorResponse(FactorResponseGen, ExternalCloudBaseFactor):
    pass


class ExternalCloudFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.external_clouds,
    ]
    emission_type: EmissionType = EmissionType.external__clouds

    create_dto = ExternalCloudFactorCreate
    update_dto = ExternalCloudFactorUpdate
    response_dto = ExternalCloudFactorResponse

    classification_fields: list[str] = external_clouds_classification_fields
    value_fields: list[str] = external_clouds_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)


class ExternalAIFactorResponse(FactorResponseGen):
    provider: str
    usage_type: str
    ef_kg_co2eq_per_request: float


class ExternalAIFactorCreate(FactorCreate):
    provider: str
    usage_type: str
    ef_kg_co2eq_per_request: float

    @field_validator("ef_kg_co2eq_per_request", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_request must be non-negative")
        return v


class ExternalAIFactorUpdate(FactorUpdate):
    provider: Optional[str] = None
    usage_type: Optional[str] = None
    ef_kg_co2eq_per_request: Optional[float] = None

    @field_validator("ef_kg_co2eq_per_request", mode="after")
    @classmethod
    def validate_ef(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_request must be non-negative")
        return v


class ExternalAIFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    # todo: resolver at runtime based on provider/use
    emission_type: EmissionType = EmissionType.external__ai

    create_dto = ExternalAIFactorCreate
    update_dto = ExternalAIFactorUpdate
    response_dto = ExternalAIFactorResponse

    classification_fields: list[str] = ["provider", "usage_type"]
    value_fields: list[str] = ["ef_kg_co2eq_per_request"]

    # instead of having a complex resolve emission_type for factors we could do it here
    def _prepare_payload(self, payload: dict) -> dict:
        prepared = dict(payload)
        if "emission_type_id" not in prepared:
            provider = prepared.get("provider", "")
            emission_key = str(provider).lower().strip().replace(" ", "_")
            emission_type = EmissionType[emission_key]
            prepared["emission_type_id"] = emission_type.value
        return super()._prepare_payload(prepared)
