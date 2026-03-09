from typing import Optional

from pydantic import field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

logger = get_logger(__name__)


class ProcessEmissionsHandlerResponse(DataEntryResponseGen):
    category: str
    subcategory: Optional[str] = None
    quantity: float
    kg_co2eq: Optional[float] = None


class ProcessEmissionsHandlerCreate(DataEntryCreate):
    category: str
    subcategory: Optional[str] = None
    quantity: float

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0.001:
            raise ValueError("Quantity must be >= 0.001 kg")
        return v


class ProcessEmissionsHandlerUpdate(DataEntryUpdate):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: Optional[float] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0.001:
            raise ValueError("Quantity must be >= 0.001 kg")
        return v


class ProcessEmissionsModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.process_emissions
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.process_emissions

    create_dto = ProcessEmissionsHandlerCreate
    update_dto = ProcessEmissionsHandlerUpdate
    response_dto = ProcessEmissionsHandlerResponse

    kind_field: str = "category"
    subkind_field: str = "subcategory"
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "category": Factor.classification["kind"].as_string(),
        "subcategory": Factor.classification["subkind"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "category": Factor.classification["kind"].as_string(),
        "subcategory": Factor.classification["subkind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ProcessEmissionsHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "category": primary_factor.get("kind")
                or data_entry.data.get("category"),
                "subcategory": primary_factor.get("subkind")
                or data_entry.data.get("subcategory"),
            }
        )

    def validate_create(self, payload: dict) -> ProcessEmissionsHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ProcessEmissionsHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _process_formula(ctx: dict, factor_values: dict):
            quantity_kg = ctx.get("quantity", 0)
            if quantity_kg < 0:
                return None
            gwp = factor_values.get("gwp_kg_co2eq_per_kg", 0)
            return quantity_kg * gwp

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_process_formula,
            )
        ]
