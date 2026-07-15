from typing import Any, Optional

from pydantic import field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

REQUESTS_FREQUENCY_OPTIONS: list[str] = [
    "1_5",
    "5_20",
    "20_100",
    "gt_100",
]

REQUESTS_FREQUENCY_MAP: dict[str, float] = {
    "1_5": 3.0,
    "5_20": 12.5,
    "20_100": 60.0,
    "gt_100": 100.0,
}


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
    requests_per_user_per_day: str
    fte_count: float
    note: Optional[str] = None
    #  __kg_co2eq_override__ for kg_co2eq

    @field_validator("requests_per_user_per_day", mode="after")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        normalized = v.strip()
        if normalized not in REQUESTS_FREQUENCY_OPTIONS:
            raise ValueError(
                "requests_per_user_per_day must be one of:"
                f" {REQUESTS_FREQUENCY_OPTIONS}"
            )
        return normalized

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
        normalized = v.strip()
        if normalized not in REQUESTS_FREQUENCY_OPTIONS:
            raise ValueError(
                "requests_per_user_per_day must be one of:"
                f" {REQUESTS_FREQUENCY_OPTIONS}"
            )
        return normalized

    @field_validator("fte_count", mode="after")
    @classmethod
    def validate_fte_count(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0.1:
            raise ValueError("fte_count must be at least 0.1")
        return v
