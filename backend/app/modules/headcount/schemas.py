from typing import Any, Optional

from pydantic import field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    EmissionComputation,
    EmissionType,
    FactorQuery,
)
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

logger = get_logger(__name__)


class HeadcountItemResponse(DataEntryResponseGen):
    name: str
    function: Optional[str] = None
    fte: Optional[float] = None
    sciper: Optional[str] = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: Optional[float] = None


class HeadCountCreate(DataEntryCreate):
    name: str
    function: Optional[str] = None
    fte: Optional[float] = None
    sciper: Optional[str] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


class HeadCountStudentCreate(DataEntryCreate):
    fte: float

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float) -> float:
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


class HeadCountStudentUpdate(DataEntryUpdate):
    fte: Optional[float] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


class HeadCountUpdate(DataEntryUpdate):
    name: Optional[str] = None
    function: Optional[str] = None
    fte: Optional[float] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


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
    filter_map: dict[str, Any] = {
        "name": DataEntry.data["name"].as_string(),
        "function": DataEntry.data["function"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "function": DataEntry.data["function"].as_string(),
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
                formula_key="ef_kg_co2eq_per_fte",
                quantity_key="fte",
            )
        ]

    def to_response(self, data_entry: DataEntry) -> HeadcountItemResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
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
                formula_key="ef_kg_co2eq_per_fte",
                quantity_key="fte",
            )
        ]

    def to_response(self, data_entry: DataEntry) -> HeadCountStudentResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> HeadCountStudentCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> HeadCountStudentUpdate:
        return self.update_dto.model_validate(payload)
