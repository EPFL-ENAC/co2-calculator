from pydantic import Field, field_validator

from app.modules_planner.purchase.emissions import PLANNER_PURCHASE_EMISSIONS
from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.utils.currencies import SUPPORTED_CURRENCIES

PURCHASE_SUBMODULE_CATEGORIES = frozenset(PLANNER_PURCHASE_EMISSIONS)


def _validate_category(v: str) -> str:
    if v not in PURCHASE_SUBMODULE_CATEGORIES:
        allowed = ", ".join(sorted(PURCHASE_SUBMODULE_CATEGORIES))
        raise ValueError(f"purchase_category must be one of: {allowed}")
    return v


def _validate_currency(v: str | None) -> str | None:
    if v is None:
        return None
    normalized = v.strip().lower()
    if not normalized:
        return None
    if normalized not in SUPPORTED_CURRENCIES:
        allowed = ", ".join(sorted(SUPPORTED_CURRENCIES))
        raise ValueError(f"currency must be one of: {allowed}")
    return normalized


class PlannerPurchaseResponse(DataEntryResponseGen):
    purchase_category: str
    amount_eur: float
    note: str | None = None
    kg_co2eq: float | None = None


class PlannerPurchaseCreate(DataEntryCreate):
    purchase_category: str
    amount_eur: float = Field(ge=0)
    # Transport-only: the currency the submitted amount is denominated in.
    # The workflow converts the amount to EUR and never stores this field.
    currency: str | None = None
    note: str | None = None

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _validate_category(v)

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        return _validate_currency(v)


class PlannerPurchaseUpdate(DataEntryUpdate):
    purchase_category: str | None = None
    amount_eur: float | None = Field(default=None, ge=0)
    currency: str | None = None
    note: str | None = None

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_category(v)

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        return _validate_currency(v)


class PlannerPurchaseBudgetResponse(DataEntryResponseGen):
    amount_eur: float
    note: str | None = None
    kg_co2eq: float | None = None


class PlannerPurchaseBudgetCreate(DataEntryCreate):
    amount_eur: float = Field(ge=0)
    currency: str | None = None
    note: str | None = None

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        return _validate_currency(v)


class PlannerPurchaseBudgetUpdate(DataEntryUpdate):
    amount_eur: float | None = Field(default=None, ge=0)
    currency: str | None = None
    note: str | None = None

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        return _validate_currency(v)
