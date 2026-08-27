from typing import Any

from pydantic import BaseModel

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionComputation, FactorQuery
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules_planner.purchase.data_entries import (
    PlannerPurchaseBudgetCreate,
    PlannerPurchaseBudgetResponse,
    PlannerPurchaseBudgetUpdate,
    PlannerPurchaseCreate,
    PlannerPurchaseResponse,
    PlannerPurchaseUpdate,
)
from app.modules_planner.purchase.emissions import (
    planner_purchase_ef_key,
    planner_purchase_quantity_key,
)
from app.schemas.data_entry import BaseModuleHandler


class _PlannerPurchaseBase(BaseModuleHandler):
    """Shared behavior of the two planner purchase kinds.

    Emissions are ``amount_eur × ef_kg_co2eq_per_eur`` from factors keyed
    on the planner kind itself — averages of the Calculator's purchase
    factors, derived when those are uploaded (see ``derived_factors``).
    Centralized purchases are the exception: the Calculator prices them per
    kg of product, so the planner row is ``quantity_kg × ef_kg_co2eq_per_kg``.
    Entries without a matching factor carry no kg_co2eq.
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.purchase
    require_subkind_for_factor = False
    require_factor_to_match = False
    subkind_field = None

    # Set by the two concrete kinds below (always non-None there).
    data_entry_type: DataEntryTypeEnum
    create_dto: type[BaseModel]
    update_dto: type[BaseModel]
    response_dto: type[BaseModel]

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ):
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "source": data_entry.source,
                **data,
            }
        )

    def validate_create(self, payload: dict):
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict):
        return self.update_dto.model_validate(payload)

    def resolve_computations(
        self, data_entry: DataEntry, emission_type: EmissionType, ctx: dict
    ) -> list:
        # kind = the row's category for the submodule kind, None for the
        # single global budget (both driven by ``kind_field``).
        kind = data_entry.data.get(self.kind_field) if self.kind_field else None
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=self.data_entry_type,
                    emission_type=emission_type,
                    kind=kind,
                    subkind=None,
                ),
                formula_key=planner_purchase_ef_key(kind),
                quantity_key=planner_purchase_quantity_key(kind),
            )
        ]


class PlannerPurchaseModuleHandler(_PlannerPurchaseBase):
    """Manual EUR total per purchase submodule."""

    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.planner_purchase
    create_dto = PlannerPurchaseCreate
    update_dto = PlannerPurchaseUpdate
    response_dto = PlannerPurchaseResponse

    kind_field = "purchase_category"
    filter_map: dict[str, Any] = {
        "purchase_category": DataEntry.data["purchase_category"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "purchase_category": DataEntry.data["purchase_category"].as_string(),
        "amount_eur": DataEntry.data["amount_eur"].as_float(),
        "quantity_kg": DataEntry.data["quantity_kg"].as_float(),
    }


class PlannerPurchaseBudgetModuleHandler(_PlannerPurchaseBase):
    """Single global EUR budget (mutually exclusive with submodule totals)."""

    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.planner_purchase_budget
    create_dto = PlannerPurchaseBudgetCreate
    update_dto = PlannerPurchaseBudgetUpdate
    response_dto = PlannerPurchaseBudgetResponse

    kind_field = None
    filter_map: dict[str, Any] = {}
    sort_map = {
        "id": DataEntry.id,
        "amount_eur": DataEntry.data["amount_eur"].as_float(),
    }
