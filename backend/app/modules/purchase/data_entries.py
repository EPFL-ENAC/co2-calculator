from typing import Any, Optional

from pydantic import field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class PurchaseHandlerResponse(DataEntryResponseGen):
    name: str
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: float
    currency: Optional[str] = None
    purchase_institutional_code: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PurchaseCentralizedHandlerResponse(DataEntryResponseGen):
    name: str
    unit: Optional[str] = None
    annual_consumption: float
    coef_to_kg: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PurchaseHandlerCreate(DataEntryCreate):
    name: str
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: float
    currency: Optional[str] = None  # doc say mandatory, but with default -> optional
    purchase_institutional_code: str
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    note: Optional[str] = None
    # __kg_co2eq_override__ is used to override the kg_co2eq calculation

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
                data["currency"] = "chf"
        return data

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("total_spent_amount", mode="after")
    @classmethod
    def validate_total_spent_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Total spend amount must be non-negative")
        return v

    @field_validator("purchase_institutional_code", mode="after")
    @classmethod
    def validate_purchase_institutional_code(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError(
                "Purchase institutional code must be at least 1 character long"
            )
        return v

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> str:
        if v is None:
            return "chf"
        normalized_v = v.strip().lower()
        valid_currencies = [
            "aud",
            "cad",
            "chf",
            "cny",
            "eur",
            "gbp",
            "jpy",
            "sek",
            "usd",
        ]
        if normalized_v not in valid_currencies:
            raise ValueError(f"Currency must be one of: {valid_currencies}")
        return normalized_v


class PurchaseCentralizedHandlerCreate(DataEntryCreate):
    name: str
    unit: str
    annual_consumption: float
    coef_to_kg: float
    note: Optional[str] = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class PurchaseHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: Optional[float] = None
    currency: Optional[str] = None
    purchase_institutional_code: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("total_spent_amount", mode="after")
    @classmethod
    def validate_total_spent_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Total spend amount must be non-negative")
        return v

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized_v = v.strip().lower()
        valid_currencies = [
            "aud",
            "cad",
            "chf",
            "cny",
            "eur",
            "gbp",
            "jpy",
            "sek",
            "usd",
        ]
        if normalized_v not in valid_currencies:
            raise ValueError(f"Currency must be one of: {valid_currencies}")
        return normalized_v

    @model_validator(mode="before")
    @classmethod
    def reject_null_institutional_code(cls, values: Any) -> Any:
        # Key absent = "not updating" (PATCH semantics). An explicit null would
        # silently clear the code, resolve no factor, and delete the entry's
        # emissions. The payload mixin may carry the field top-level and/or
        # under "data", so guard both shapes.
        if not isinstance(values, dict):
            return values
        payloads = [values]
        if isinstance(values.get("data"), dict):
            payloads.append(values["data"])
        for payload in payloads:
            if (
                "purchase_institutional_code" in payload
                and payload["purchase_institutional_code"] is None
            ):
                raise ValueError("purchase_institutional_code cannot be null")
        return values

    @field_validator("purchase_institutional_code", mode="after")
    @classmethod
    def validate_purchase_institutional_code(cls, v: Optional[str]) -> Optional[str]:
        # None here can only be the key-absent default (explicit null is
        # rejected in the before-validator above); a blank/whitespace value
        # provided on purpose must fail loudly here rather than silently
        # resolving to no factor further down the pipeline.
        if v is None:
            return v
        if not v.strip():
            raise ValueError("purchase_institutional_code cannot be empty")
        return v


class PurchaseCentralizedHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    unit: Optional[str] = None
    annual_consumption: Optional[float] = None
    coef_to_kg: Optional[float] = None
    note: Optional[str] = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v
