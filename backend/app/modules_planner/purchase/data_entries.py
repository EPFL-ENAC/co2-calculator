from typing import Optional

from pydantic import field_validator

from app.modules_planner.purchase.emissions import PLANNER_PURCHASE_EMISSIONS
from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

PURCHASE_SUBMODULE_CATEGORIES = frozenset(PLANNER_PURCHASE_EMISSIONS)


def _validate_category(v: str) -> str:
    if v not in PURCHASE_SUBMODULE_CATEGORIES:
        allowed = ", ".join(sorted(PURCHASE_SUBMODULE_CATEGORIES))
        raise ValueError(f"purchase_category must be one of: {allowed}")
    return v


def _validate_amount(v: float) -> float:
    if v < 0:
        raise ValueError("amount_chf must be non-negative")
    return v


class PlannerPurchaseResponse(DataEntryResponseGen):
    purchase_category: str
    amount_chf: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PlannerPurchaseCreate(DataEntryCreate):
    purchase_category: str
    amount_chf: float
    note: Optional[str] = None

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _validate_category(v)

    @field_validator("amount_chf", mode="after")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        return _validate_amount(v)


class PlannerPurchaseUpdate(DataEntryUpdate):
    purchase_category: Optional[str] = None
    amount_chf: Optional[float] = None
    note: Optional[str] = None

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_category(v)

    @field_validator("amount_chf", mode="after")
    @classmethod
    def validate_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _validate_amount(v)


class PlannerPurchaseBudgetResponse(DataEntryResponseGen):
    amount_chf: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PlannerPurchaseBudgetCreate(DataEntryCreate):
    amount_chf: float
    note: Optional[str] = None

    @field_validator("amount_chf", mode="after")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        return _validate_amount(v)


class PlannerPurchaseBudgetUpdate(DataEntryUpdate):
    amount_chf: Optional[float] = None
    note: Optional[str] = None

    @field_validator("amount_chf", mode="after")
    @classmethod
    def validate_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _validate_amount(v)
