from typing import Optional

from pydantic import Field, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.modules_planner.purchase.data_entries import _validate_category
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


class PlannerPurchaseFactorCreate(FactorCreate):
    purchase_category: str
    ef_kg_co2eq_per_eur: float = Field(ge=0)

    @field_validator("purchase_category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _validate_category(v)


class PlannerPurchaseFactorUpdate(FactorUpdate):
    purchase_category: Optional[str] = None
    ef_kg_co2eq_per_eur: Optional[float] = Field(default=None, ge=0)


class PlannerPurchaseFactorResponse(FactorResponseGen):
    purchase_category: str
    ef_kg_co2eq_per_eur: float


class PlannerPurchaseFactorHandler(BaseFactorHandler):
    """Average EF (kg CO2e per EUR) per purchase submodule."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.planner_purchase]
    emission_type = None  # resolved from purchase_category at entry level

    create_dto = PlannerPurchaseFactorCreate
    update_dto = PlannerPurchaseFactorUpdate
    response_dto = PlannerPurchaseFactorResponse

    classification_fields: list[str] = ["purchase_category"]
    value_fields: list[str] = ["ef_kg_co2eq_per_eur"]


class PlannerPurchaseBudgetFactorCreate(FactorCreate):
    ef_kg_co2eq_per_eur: float = Field(ge=0)


class PlannerPurchaseBudgetFactorUpdate(FactorUpdate):
    ef_kg_co2eq_per_eur: Optional[float] = Field(default=None, ge=0)


class PlannerPurchaseBudgetFactorResponse(FactorResponseGen):
    ef_kg_co2eq_per_eur: float


class PlannerPurchaseBudgetFactorHandler(BaseFactorHandler):
    """Average EF (kg CO2e per EUR) for a global research budget."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.planner_purchase_budget]
    emission_type = EmissionType.purchases__goods_and_services

    create_dto = PlannerPurchaseBudgetFactorCreate
    update_dto = PlannerPurchaseBudgetFactorUpdate
    response_dto = PlannerPurchaseBudgetFactorResponse

    classification_fields: list[str] = []
    value_fields: list[str] = ["ef_kg_co2eq_per_eur"]
