from typing import Any

from pydantic import field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.schemas.fields import (
    ClassificationKey,
    CurrencyCode,
    OptionalClassificationKey,
)
from app.utils.currencies import SUPPORTED_CURRENCIES


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
    name: ClassificationKey
    supplier: str | None = None
    quantity: float | None = None
    total_spent_amount: float
    currency: CurrencyCode | None = None  # doc say mandatory, but with default
    purchase_institutional_code: ClassificationKey
    purchase_institutional_description: str | None = None
    purchase_additional_code: OptionalClassificationKey = None
    note: str | None = None
    # __kg_co2eq_override__ is used to override the kg_co2eq calculation

    @model_validator(mode="before")
    @classmethod
    def ensure_default_currency(cls, data: Any) -> Any:
        """Apply the default currency when input has null or blank currency."""
        if isinstance(data, dict):
            currency = data.get("currency")
            if currency is None or (
                isinstance(currency, str) and currency.strip() == ""
            ):
                # Copy: mutating the caller's dict leaks the default upstream.
                return {**data, "currency": "chf"}
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

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str:
        if v is None:
            return "chf"
        if v not in SUPPORTED_CURRENCIES:
            allowed = ", ".join(sorted(SUPPORTED_CURRENCIES))
            raise ValueError(f"Currency must be one of: {allowed}")
        return v


class PurchaseCentralizedHandlerCreate(DataEntryCreate):
    name: ClassificationKey
    unit: ClassificationKey
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
    name: ClassificationKey | None = None
    supplier: str | None = None
    quantity: float | None = None
    total_spent_amount: float | None = None
    currency: CurrencyCode | None = None
    # ClassificationKey (not Optional…): a blank/whitespace code provided on
    # purpose must fail loudly rather than silently resolving to no factor
    # further down the pipeline; None stays the key-absent PATCH default.
    purchase_institutional_code: ClassificationKey | None = None
    purchase_additional_code: OptionalClassificationKey = None
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
        if v not in SUPPORTED_CURRENCIES:
            allowed = ", ".join(sorted(SUPPORTED_CURRENCIES))
            raise ValueError(f"Currency must be one of: {allowed}")
        return v

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


class PurchaseCentralizedHandlerUpdate(DataEntryUpdate):
    name: ClassificationKey | None = None
    unit: ClassificationKey | None = None
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
