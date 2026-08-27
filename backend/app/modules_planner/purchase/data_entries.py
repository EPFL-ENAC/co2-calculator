from pydantic import Field, field_validator, model_validator

from app.modules_planner.purchase.emissions import (
    PLANNER_PURCHASE_EMISSIONS,
    planner_purchase_quantity_key,
)
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


def _check_quantity_field(category: str | None, amount_eur, quantity_kg):
    """A category row carries exactly the quantity its factors are priced in."""
    if amount_eur is not None and quantity_kg is not None:
        raise ValueError("amount_eur and quantity_kg are mutually exclusive")
    if category is None:
        return
    expected = planner_purchase_quantity_key(category)
    other = "quantity_kg" if expected == "amount_eur" else "amount_eur"
    given = {"amount_eur": amount_eur, "quantity_kg": quantity_kg}
    if given[other] is not None:
        raise ValueError(f"{category} takes {expected}, not {other}")


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
    amount_eur: float | None = None
    quantity_kg: float | None = None
    note: str | None = None
    kg_co2eq: float | None = None


class PlannerPurchaseCreate(DataEntryCreate):
    purchase_category: str
    amount_eur: float | None = Field(default=None, ge=0)
    quantity_kg: float | None = Field(default=None, ge=0)
    # Transport-only: the currency the submitted amount is denominated in.
    # The workflow converts the amount to EUR and never stores this field.
    currency: str | None = None
    note: str | None = None

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _validate_category(v)

    @model_validator(mode="after")
    def validate_quantity_field(self):
        _check_quantity_field(self.purchase_category, self.amount_eur, self.quantity_kg)
        if self.amount_eur is None and self.quantity_kg is None:
            raise ValueError(
                f"{planner_purchase_quantity_key(self.purchase_category)} is required"
            )
        return self

    @field_validator("currency", mode="after")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        return _validate_currency(v)


class PlannerPurchaseUpdate(DataEntryUpdate):
    purchase_category: str | None = None
    amount_eur: float | None = Field(default=None, ge=0)
    quantity_kg: float | None = Field(default=None, ge=0)
    currency: str | None = None
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def drop_foreign_quantity(cls, values):
        """Updates are validated on the merged persisted+incoming payload, so a
        row that predates its category's unit still carries the other key.
        """
        if not isinstance(values, dict):
            return values
        scopes = [values] + (
            [values["data"]] if isinstance(values.get("data"), dict) else []
        )
        for scope in scopes:
            category = scope.get("purchase_category")
            if category is None:
                continue
            expected = planner_purchase_quantity_key(category)
            other = "quantity_kg" if expected == "amount_eur" else "amount_eur"
            if scope.get(expected) is not None:
                scope.pop(other, None)
        return values

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_category(v)

    @model_validator(mode="after")
    def validate_quantity_field(self):
        _check_quantity_field(self.purchase_category, self.amount_eur, self.quantity_kg)
        return self

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
