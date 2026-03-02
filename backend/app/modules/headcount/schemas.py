from typing import Any, Optional

from pydantic import field_validator, model_validator
from sqlalchemy import func

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    EmissionComputation,
    FactorQuery,
)
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.utils.headcount_role_category import POSITION_CATEGORIES

logger = get_logger(__name__)


def _normalize_position_category(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    if normalized not in POSITION_CATEGORIES:
        allowed_categories = ", ".join(sorted(POSITION_CATEGORIES))
        raise ValueError(f"position_category must be one of: {allowed_categories}")
    return normalized


class HeadcountItemResponse(DataEntryResponseGen):
    unit_institutional_id: str
    name: str
    position_title: Optional[str] = None
    position_category: Optional[str] = None
    function: Optional[str] = None
    fte: Optional[float] = None
    user_institutional_id: str
    note: Optional[str] = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: Optional[float] = None


class HeadCountCreate(DataEntryCreate):
    unit_institutional_id: str
    name: str
    position_title: Optional[str] = None
    position_category: Optional[str] = None
    function: Optional[str] = None
    fte: float
    user_institutional_id: str
    note: Optional[str] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float) -> float:
        if v < 0:
            raise ValueError("FTE must be non-negative")
        if v > 1:
            raise ValueError("FTE must be less than or equal to 1")
        return v

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, v: str) -> str:
        normalized = v.strip()
        if normalized == "":
            raise ValueError("name is required")
        return normalized

    @field_validator("position_category", mode="after")
    @classmethod
    def validate_position_category(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_position_category(v)

    @field_validator("unit_institutional_id", mode="after")
    @classmethod
    def validate_unit_institutional_id(cls, v: str) -> str:
        normalized = v.strip()
        if normalized == "":
            raise ValueError("unit_institutional_id is required")
        if not normalized.isdigit():
            raise ValueError("unit_institutional_id must contain digits only")
        return normalized

    @field_validator("user_institutional_id", mode="after")
    @classmethod
    def validate_user_institutional_id(cls, v: str) -> str:
        normalized = v.strip()
        if normalized == "":
            raise ValueError("user_institutional_id is required")
        if not normalized.isdigit():
            raise ValueError("user_institutional_id must contain digits only")
        return normalized

    @field_validator("note", mode="after")
    @classmethod
    def validate_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if normalized == "":
            return None
        return normalized

    @model_validator(mode="after")
    def normalize_position_fields(self) -> "HeadCountCreate":
        if self.position_category is None and self.function is not None:
            self.position_category = _normalize_position_category(self.function)
        if self.function is None and self.position_category is not None:
            self.function = self.position_category
        if self.position_title is not None and self.position_title.strip() == "":
            self.position_title = None
        return self


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
    unit_institutional_id: Optional[str] = None
    name: Optional[str] = None
    position_title: Optional[str] = None
    position_category: Optional[str] = None
    function: Optional[str] = None
    fte: Optional[float] = None
    user_institutional_id: Optional[str] = None
    note: Optional[str] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        if v > 1:
            raise ValueError("FTE must be less than or equal to 1")
        return v

    @field_validator("position_category", mode="after")
    @classmethod
    def validate_position_category(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_position_category(v)

    @field_validator("unit_institutional_id", mode="after")
    @classmethod
    def validate_unit_institutional_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if normalized == "":
            return None
        if not normalized.isdigit():
            raise ValueError("unit_institutional_id must contain digits only")
        return normalized

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if normalized == "":
            return None
        return normalized

    @field_validator("user_institutional_id", mode="after")
    @classmethod
    def validate_user_institutional_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if normalized == "":
            return None
        if not normalized.isdigit():
            raise ValueError("user_institutional_id must contain digits only")
        return normalized

    @field_validator("note", mode="after")
    @classmethod
    def validate_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if normalized == "":
            return None
        return normalized

    @model_validator(mode="after")
    def normalize_position_fields(self) -> "HeadCountUpdate":
        if self.position_category is None and self.function is not None:
            self.position_category = _normalize_position_category(self.function)
        if self.function is None and self.position_category is not None:
            self.function = self.position_category
        if self.position_title is not None and self.position_title.strip() == "":
            self.position_title = None
        return self


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
        "position_title": func.coalesce(
            DataEntry.data["position_title"].as_string(),
            DataEntry.data["position_category"].as_string(),
            DataEntry.data["function"].as_string(),
        ),
    }
    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "position_title": func.coalesce(
            DataEntry.data["position_title"].as_string(),
            DataEntry.data["position_category"].as_string(),
            DataEntry.data["function"].as_string(),
        ),
        "position_category": func.coalesce(
            DataEntry.data["position_category"].as_string(),
            DataEntry.data["function"].as_string(),
        ),
        "function": func.coalesce(
            DataEntry.data["position_category"].as_string(),
            DataEntry.data["function"].as_string(),
        ),
        "fte": DataEntry.data["fte"].as_float(),
    }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.member,
                    kind=emission_type.name,
                    subkind=None,
                ),
                formula_key="kg_co2eq_per_fte",
                quantity_key="fte",
            )
        ]

    def to_response(self, data_entry: DataEntry) -> HeadcountItemResponse:
        data = dict(data_entry.data or {})
        # Backward compatibility with legacy field naming used in existing rows.
        if not data.get("position_category") and data.get("function"):
            data["position_category"] = data["function"]
        if not data.get("position_title") and data.get("position_category"):
            data["position_title"] = data["position_category"]
        if not data.get("function") and data.get("position_category"):
            data["function"] = data["position_category"]
        if not data.get("unit_institutional_id"):
            data["unit_institutional_id"] = ""
        if not data.get("user_institutional_id"):
            data["user_institutional_id"] = ""

        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
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
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.student,
                    kind=emission_type.name,
                    subkind=None,
                ),
                formula_key="kg_co2eq_per_fte",
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
