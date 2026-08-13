from typing import Any

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionComputation, FactorQuery
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.headcount.data_entries import (
    HeadCountCreate,
    HeadcountItemResponse,
    HeadCountStudentCreate,
    HeadCountStudentResponse,
    HeadCountStudentUpdate,
    HeadCountUpdate,
)
from app.schemas.data_entry import BaseModuleHandler


class HeadcountMemberModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.member
    create_dto = HeadCountCreate
    update_dto = HeadCountUpdate
    response_dto = HeadcountItemResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False
    default_where: list = []
    filter_map: dict[str, Any] = {
        "name": DataEntry.data["name"].as_string(),
        "sius_code": DataEntry.data["sius_code"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "sius_code": DataEntry.data["sius_code"].as_string(),
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
    ) -> HeadcountItemResponse:
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

    def validate_create(self, payload: dict) -> HeadCountCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> HeadCountUpdate:
        return self.update_dto.model_validate(payload)


class HeadcountStudentModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.student
    create_dto = HeadCountStudentCreate
    update_dto = HeadCountStudentUpdate
    response_dto = HeadCountStudentResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "fte": DataEntry.data["fte"].as_float(),
    }

    filter_map: dict[str, Any] = {}

    def resolve_computations(
        self, data_entry: DataEntry, emission_type: EmissionType, ctx: dict
    ) -> list:

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.student,
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
    ) -> HeadCountStudentResponse:
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

    def validate_create(self, payload: dict) -> HeadCountStudentCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> HeadCountStudentUpdate:
        return self.update_dto.model_validate(payload)
