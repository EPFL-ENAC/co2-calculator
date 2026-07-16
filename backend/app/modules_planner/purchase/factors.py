from typing import Optional

from pydantic import field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.modules_planner.purchase.data_entries import _validate_category
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


def _validate_ef(v: Optional[float]) -> Optional[float]:
    if v is not None and v < 0:
        raise ValueError("ef_kg_co2eq_per_chf must be non-negative")
    return v


class PlannerPurchaseFactorCreate(FactorCreate):
    purchase_category: str
    ef_kg_co2eq_per_chf: float

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _validate_category(v)

    @field_validator("ef_kg_co2eq_per_chf", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        _validate_ef(v)
        return v


class PlannerPurchaseFactorUpdate(FactorUpdate):
    purchase_category: Optional[str] = None
    ef_kg_co2eq_per_chf: Optional[float] = None

    @field_validator("ef_kg_co2eq_per_chf", mode="after")
    @classmethod
    def validate_ef(cls, v: Optional[float]) -> Optional[float]:
        return _validate_ef(v)


class PlannerPurchaseFactorResponse(FactorResponseGen):
    purchase_category: str
    ef_kg_co2eq_per_chf: float


class PlannerPurchaseFactorHandler(BaseFactorHandler):
    """Average EF (kg CO2e per CHF) per purchase submodule."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.planner_purchase]
    emission_type = None  # resolved from purchase_category at entry level

    create_dto = PlannerPurchaseFactorCreate
    update_dto = PlannerPurchaseFactorUpdate
    response_dto = PlannerPurchaseFactorResponse

    classification_fields: list[str] = ["purchase_category"]
    value_fields: list[str] = ["ef_kg_co2eq_per_chf"]


class PlannerPurchaseBudgetFactorCreate(FactorCreate):
    ef_kg_co2eq_per_chf: float

    @field_validator("ef_kg_co2eq_per_chf", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        _validate_ef(v)
        return v


class PlannerPurchaseBudgetFactorUpdate(FactorUpdate):
    ef_kg_co2eq_per_chf: Optional[float] = None

    @field_validator("ef_kg_co2eq_per_chf", mode="after")
    @classmethod
    def validate_ef(cls, v: Optional[float]) -> Optional[float]:
        return _validate_ef(v)


class PlannerPurchaseBudgetFactorResponse(FactorResponseGen):
    ef_kg_co2eq_per_chf: float


class PlannerPurchaseBudgetFactorHandler(BaseFactorHandler):
    """Average EF (kg CO2e per CHF) for a global research budget."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.planner_purchase_budget]
    emission_type = EmissionType.purchases__goods_and_services

    create_dto = PlannerPurchaseBudgetFactorCreate
    update_dto = PlannerPurchaseBudgetFactorUpdate
    response_dto = PlannerPurchaseBudgetFactorResponse

    classification_fields: list[str] = []
    value_fields: list[str] = ["ef_kg_co2eq_per_chf"]
