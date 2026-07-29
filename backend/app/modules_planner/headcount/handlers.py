from typing import Any

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionComputation, FactorQuery
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules_planner.headcount.data_entries import (
    PlannerHeadCountCreate,
    PlannerHeadCountResponse,
    PlannerHeadCountUpdate,
)
from app.schemas.data_entry import BaseModuleHandler


class PlannerHeadcountModuleHandler(BaseModuleHandler):
    """Manual FTE/year per SIUS category (Simulator Plan headcount).

    Emissions reuse the Calculator's generic member factors
    (``FactorQuery(data_entry_type=member)``) — the SIUS category is a
    breakdown dimension, not a factor key, exactly as in the Calculator.
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.planner_headcount
    create_dto = PlannerHeadCountCreate
    update_dto = PlannerHeadCountUpdate
    response_dto = PlannerHeadCountResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False
    filter_map: dict[str, Any] = {
        "sius_code": DataEntry.data["sius_code"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "sius_code": DataEntry.data["sius_code"].as_string(),
        "fte": DataEntry.data["fte"].as_float(),
    }

    def resolve_computations(
        self, data_entry: DataEntry, emission_type: EmissionType, ctx: dict
    ) -> list:

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.member,
                    emission_type=emission_type,
                    kind=None,
                    subkind=None,
                ),
                formula_key="ef_kg_co2eq_per_unit",
                quantity_key="fte",
                multiplier_key="number_of_unit_per_fte",
            )
        ]

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> PlannerHeadCountResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
            }
        )

    def validate_create(self, payload: dict) -> PlannerHeadCountCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> PlannerHeadCountUpdate:
        return self.update_dto.model_validate(payload)
