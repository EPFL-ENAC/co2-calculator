from typing import Any

from pydantic import field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class PurchaseHandlerResponse(DataEntryResponseGen):
    name: str
    supplier: str | None = None
    quantity: float | None = None
    total_spent_amount: float
    currency: str | None = None
    purchase_institutional_code: str | None = None
    note: str | None = None
    kg_co2eq: float | None = None


class PurchaseCentralizedHandlerResponse(DataEntryResponseGen):
    name: str
    unit: str | None = None
    annual_consumption: float
    coef_to_kg: float
    note: str | None = None
    kg_co2eq: float | None = None


class PurchaseHandlerCreate(DataEntryCreate):
    name: str
    supplier: str | None = None
    quantity: float | None = None
    total_spent_amount: float
    currency: str | None = None  # doc say mandatory, but with default -> optional
    purchase_institutional_code: str
    purchase_institutional_description: str | None = None
    purchase_additional_code: str | None = None
    note: str | None = None
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
    def validate_quantity(cls, v: float | None) -> float | None:
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
    def validate_currency(cls, v: str | None) -> str:
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
    note: str | None = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class PurchaseHandlerUpdate(DataEntryUpdate):
    name: str | None = None
    supplier: str | None = None
    quantity: float | None = None
    total_spent_amount: float | None = None
    currency: str | None = None
    purchase_institutional_code: str | None = None
    purchase_additional_code: str | None = None
    note: str | None = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("total_spent_amount", mode="after")
    @classmethod
    def validate_total_spent_amount(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Total spend amount must be non-negative")
        return v

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
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
    def validate_purchase_institutional_code(cls, v: str | None) -> str | None:
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
    name: str | None = None
    unit: str | None = None
    annual_consumption: float | None = None
    coef_to_kg: float | None = None
    note: str | None = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v
