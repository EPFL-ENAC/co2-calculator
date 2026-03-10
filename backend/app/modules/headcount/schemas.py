import re
from typing import Any, Optional

from pydantic import ValidationInfo, field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    EmissionComputation,
    EmissionType,
    FactorQuery,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

logger = get_logger(__name__)


POSITION_CATEGORY_VALUES = {
    "professor",
    "scientific_collaborator",
    "postdoctoral_assistant",
    "doctoral_assistant",
    "trainee",
    "technical_administrative_staff",
    "student",
    "other",
}


class HeadcountItemResponse(DataEntryResponseGen):
    name: str
    position_title: Optional[str] = None
    position_category: Optional[str] = None
    fte: Optional[float] = None
    user_institutional_id: Optional[str] = None
    note: Optional[str] = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: Optional[float] = None


class HeadCountCreate(DataEntryCreate):
    name: str
    position_title: Optional[str] = None
    position_category: Optional[str] = None
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
        return v

    @field_validator("position_category", mode="after")
    @classmethod
    def validate_position_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in POSITION_CATEGORY_VALUES:
            allowed_values = ", ".join(sorted(POSITION_CATEGORY_VALUES))
            raise ValueError(f"position_category must be one of: {allowed_values}")
        return v

    @field_validator("user_institutional_id", mode="after")
    @classmethod
    def validate_user_institutional_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip()
        if not re.fullmatch(r"\d+", normalized):
            raise ValueError("user_institutional_id must contain only digits")
        return normalized


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
    position_title: Optional[str] = None
    position_category: Optional[str] = None
    fte: Optional[float] = None
    note: Optional[str] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v

    @field_validator("position_category", mode="after")
    @classmethod
    def validate_position_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in POSITION_CATEGORY_VALUES:
            allowed_values = ", ".join(sorted(POSITION_CATEGORY_VALUES))
            raise ValueError(f"position_category must be one of: {allowed_values}")
        return v


class HeadcountMemberDropdownItem(BaseModel):
    """Lightweight member record used to populate traveler dropdowns."""

    institutional_id: int
    name: str


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
        "position_title": DataEntry.data["position_title"].as_string(),
        "position_category": DataEntry.data["position_category"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "position_title": DataEntry.data["position_title"].as_string(),
        "position_category": DataEntry.data["position_category"].as_string(),
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
                formula_key="ef_kg_co2eq_per_unit",
                quantity_key="fte",
                multiplier_key="number_of_unit_per_fte",
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


# =============================================================================
# Headcount Factor Handlers (member & student)
# =============================================================================

headcount_classification_fields: list[str] = [
    "headcount_category",
    "headcount_class",
    "headcount_subclass",
    "unit",
]
headcount_value_fields: list[str] = [
    "number_of_unit_per_fte",
    "ef_kg_co2eq_per_unit",
]


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class _HeadcountFactorValidationMixin:
    """Shared validators for headcount factor DTOs."""

    @field_validator("number_of_unit_per_fte", "ef_kg_co2eq_per_unit", mode="after")
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")


class HeadcountBaseFactor:
    """Fields shared by all headcount factor DTOs."""

    headcount_category: str
    headcount_class: str
    headcount_subclass: Optional[str]
    number_of_unit_per_fte: float
    ef_kg_co2eq_per_unit: float
    unit: str


class HeadcountFactorCreate(
    _HeadcountFactorValidationMixin, FactorCreate, HeadcountBaseFactor
):
    """Schema for creating a headcount factor."""

    headcount_subclass: Optional[str] = None


class HeadcountFactorUpdate(
    _HeadcountFactorValidationMixin, FactorUpdate, HeadcountBaseFactor
):
    """Schema for updating a headcount factor."""

    headcount_category: Optional[str] = None  # type: ignore[assignment]
    headcount_class: Optional[str] = None  # type: ignore[assignment]
    headcount_subclass: Optional[str] = None
    number_of_unit_per_fte: Optional[float] = None  # type: ignore[assignment]
    ef_kg_co2eq_per_unit: Optional[float] = None  # type: ignore[assignment]
    unit: Optional[str] = None  # type: ignore[assignment]


class HeadcountFactorResponse(FactorResponseGen, HeadcountBaseFactor):
    """Response schema for headcount factors."""

    headcount_subclass: Optional[str] = None


class HeadcountMemberFactorHandler(BaseFactorHandler):
    """Factor handler for headcount member factors."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.member]
    emission_type: EmissionType = EmissionType.food

    create_dto = HeadcountFactorCreate
    update_dto = HeadcountFactorUpdate
    response_dto = HeadcountFactorResponse

    classification_fields: list[str] = headcount_classification_fields
    value_fields: list[str] = headcount_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        """Convert a Factor model to a response DTO."""
        return self.response_dto.model_validate(factor.model_dump)


class HeadcountStudentFactorHandler(BaseFactorHandler):
    """Factor handler for headcount student factors."""

    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.student]
    emission_type: EmissionType = EmissionType.food

    create_dto = HeadcountFactorCreate
    update_dto = HeadcountFactorUpdate
    response_dto = HeadcountFactorResponse

    classification_fields: list[str] = headcount_classification_fields
    value_fields: list[str] = headcount_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        """Convert a Factor model to a response DTO."""
        return self.response_dto.model_validate(factor.model_dump)
