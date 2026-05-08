from typing import Any, Optional

from pydantic import ValidationInfo, field_validator, model_validator
from sqlalchemy import case
from sqlalchemy.sql.elements import ColumnElement

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.schemas.factor import (
    BaseFactorHandler,
    EmissionType,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)
from app.services.exchange_rates_service import ExchangeRatesService

logger = get_logger(__name__)

REQUESTS_FREQUENCY_OPTIONS: list[str] = [
    "1-5 times per day",
    "5-20 times per day",
    "20-100 times per day",
    ">100 times per day",
]

REQUESTS_FREQUENCY_MAP: dict[str, float] = {
    "1-5 times per day": 3.0,
    "5-20 times per day": 12.5,
    "20-100 times per day": 60.0,
    ">100 times per day": 100.0,
}


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    service_type: Optional[str] = None
    provider: Optional[str] = None
    spent_amount: Optional[float] = None
    currency: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ExternalAIHandlerResponse(DataEntryResponseGen):
    provider: Optional[str] = None
    usage_type: Optional[str] = None
    requests_per_user_per_day: Optional[str] = None
    fte_count: Optional[float] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ExternalCloudHandlerCreate(DataEntryCreate):
    service_type: str
    provider: str
    spent_amount: float
    currency: Optional[str] = None
    note: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def ensure_default_currency(cls, data: Any) -> Any:
        """Ensure default currency is applied when input has null or empty currency."""
        if isinstance(data, dict):
            currency = data.get("currency")
            # Apply default when currency is None, empty string, or whitespace-only
            if currency is None or (
                isinstance(currency, str) and currency.strip() == ""
            ):
                data["currency"] = "eur"
        return data

    @field_validator("spent_amount", mode="after")
    @classmethod
    def validate_spent_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Spent amount must be non-negative")
        return v

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> str:
        if v is None:
            return "eur"
        normalized_v = v.strip().lower()
        valid_currencies = ["chf", "eur", "usd"]
        if normalized_v not in valid_currencies:
            raise ValueError(f"Currency must be one of: {valid_currencies}")
        return normalized_v


class ExternalAIHandlerCreate(DataEntryCreate):
    provider: str
    usage_type: str
    requests_per_user_per_day: Optional[str] = None
    fte_count: float
    note: Optional[str] = None

    @field_validator("requests_per_user_per_day", mode="after")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in REQUESTS_FREQUENCY_OPTIONS:
            raise ValueError(
                "requests_per_user_per_day must be one of:"
                f" {REQUESTS_FREQUENCY_OPTIONS}"
            )
        return v

    @field_validator("fte_count", mode="after")
    @classmethod
    def validate_fte_count(cls, v: float) -> float:
        if v < 0.1:
            raise ValueError("fte_count must be at least 0.1")
        return v


class ExternalCloudHandlerUpdate(DataEntryUpdate):
    service_type: Optional[str] = None
    provider: Optional[str] = None
    spent_amount: Optional[float] = None
    currency: Optional[str] = None
    note: Optional[str] = None

    @field_validator("spent_amount", mode="after")
    @classmethod
    def validate_spent_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Spent amount must be non-negative")
        return v

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized_v = v.strip().lower()
        valid_currencies = ["chf", "eur", "usd"]
        if normalized_v not in valid_currencies:
            raise ValueError(f"Currency must be one of: {valid_currencies}")
        return normalized_v


class ExternalAIHandlerUpdate(DataEntryUpdate):
    provider: Optional[str] = None
    usage_type: Optional[str] = None
    requests_per_user_per_day: Optional[str] = None
    fte_count: Optional[float] = None
    note: Optional[str] = None

    @field_validator("requests_per_user_per_day", mode="after")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in REQUESTS_FREQUENCY_OPTIONS:
            raise ValueError(
                "requests_per_user_per_day must be one of:"
                f" {REQUESTS_FREQUENCY_OPTIONS}"
            )
        return v

    @field_validator("fte_count", mode="after")
    @classmethod
    def validate_fte_count(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0.1:
            raise ValueError("fte_count must be at least 0.1")
        return v


class ExternalCloudModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    create_dto = ExternalCloudHandlerCreate
    update_dto = ExternalCloudHandlerUpdate
    response_dto = ExternalCloudHandlerResponse

    kind_field: str = "provider"
    subkind_field: str = "service_type"

    sort_map = {
        "id": DataEntry.id,
        "service_type": Factor.classification[subkind_field].as_string(),
        "provider": Factor.classification[kind_field].as_string(),
        "spent_amount": DataEntry.data["spent_amount"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "service_type": Factor.classification[subkind_field].as_string(),
        "provider": Factor.classification[kind_field].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ExternalCloudHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
                "service_type": primary_factor.get("subkind")
                or data.get("service_type"),
                "provider": primary_factor.get("kind") or data.get("provider"),
            }
        )

    def validate_create(self, payload: dict) -> ExternalCloudHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ExternalCloudHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _cloud_formula(ctx: dict, factor_values: dict) -> Optional[float]:
            # Get the year to ensure we get the correct exchange rate for the year
            # of the purchase
            year = ctx.get("_year")
            if year is None:
                return None

            spent_amount = ctx.get("spent_amount")
            entry_currency = (ctx.get("currency", "") or "eur").lower()
            ef = factor_values.get("ef_kg_co2eq_per_currency")
            ef_currency = (factor_values.get("currency", "eur") or "eur").lower()
            if spent_amount is None or ef is None:
                return None

            spent_amount_eur = spent_amount
            if entry_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, entry_currency
                )
                spent_amount_eur = spent_amount * exchange_rate
            ef_eur = ef
            if ef_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, ef_currency
                )
                ef_eur = ef * exchange_rate

            return spent_amount_eur * ef_eur

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_cloud_formula,
            )
        ]


## BUILDINGS FACTOR HANDLER


## FACTORS for BUILDINGS

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


def _requests_frequency_sort_expr() -> ColumnElement[int]:
    """Return a SQLAlchemy CASE expression mapping frequency strings to ordinals."""
    freq_col = DataEntry.data["requests_per_user_per_day"].as_string()
    return case(
        (freq_col == "1-5 times per day", 1),
        (freq_col == "5-20 times per day", 2),
        (freq_col == "20-100 times per day", 3),
        (freq_col == ">100 times per day", 4),
        else_=0,
    )


class ExternalAIModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    create_dto = ExternalAIHandlerCreate
    update_dto = ExternalAIHandlerUpdate
    response_dto = ExternalAIHandlerResponse

    kind_field: str = "provider"
    subkind_field: str = "usage_type"
    sort_map = {
        "id": DataEntry.id,
        "provider": Factor.classification["provider"].as_string(),
        "usage_type": Factor.classification["usage_type"].as_string(),
        "requests_per_user_per_day": _requests_frequency_sort_expr(),
        "fte_count": DataEntry.data["fte_count"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "provider": Factor.classification["provider"].as_string(),
        "usage_type": Factor.classification["usage_type"].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ExternalAIHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
                "provider": primary_factor.get("provider") or data.get("provider"),
                "usage_type": primary_factor.get("usage_type")
                or data.get("usage_type"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _ai_formula(ctx: dict, factor_values: dict):
            frequency_str = ctx.get("requests_per_user_per_day")
            frequency = REQUESTS_FREQUENCY_MAP.get(frequency_str or "")
            if frequency is None:
                return None
            fte_count = ctx.get("fte_count")
            if fte_count is None:
                return None
            factor_g = factor_values.get("ef_kg_co2eq_per_request")
            if factor_g is None:
                return None
            return (frequency * 5 * 46 * fte_count * factor_g) / 1000

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_ai_formula,
            )
        ]


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
