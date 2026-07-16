from sqlmodel import func

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.process_emissions.data_entries import (
    ProcessEmissionsHandlerCreate,
    ProcessEmissionsHandlerResponse,
    ProcessEmissionsHandlerUpdate,
)
from app.schemas.data_entry import BaseModuleHandler


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
        "category": func.coalesce(
            Factor.classification[kind_field].as_string(),
            DataEntry.data["category"].as_string(),
        ),
        "subcategory": func.coalesce(
            Factor.classification[subkind_field].as_string(),
            DataEntry.data["subcategory"].as_string(),
        ),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "category": func.coalesce(
            Factor.classification[kind_field].as_string(),
            DataEntry.data["category"].as_string(),
        ),
        "subcategory": func.coalesce(
            Factor.classification[subkind_field].as_string(),
            DataEntry.data["subcategory"].as_string(),
        ),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ProcessEmissionsHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "source": data_entry.source,
                **data,
                "category": primary_factor.get("kind") or data.get("category"),
                "subcategory": primary_factor.get("subkind") or data.get("subcategory"),
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
            quantity_kg = ctx.get("quantity")
            if quantity_kg is None or quantity_kg < 0:
                return None
            gwp = factor_values.get("ef_kg_co2eq_per_unit")
            if gwp is None:
                return None
            return quantity_kg * gwp

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_process_formula,
            )
        ]
