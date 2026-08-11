from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.emissions import EmissionType
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

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


def _validate_non_negative_float(v: float | None, field_name: str) -> float | None:
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
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")


class HeadcountBaseFactor:
    """Fields shared by all headcount factor DTOs."""

    headcount_category: str
    headcount_class: str
    headcount_subclass: str | None
    number_of_unit_per_fte: float
    ef_kg_co2eq_per_unit: float
    unit: str


class HeadcountFactorCreate(
    _HeadcountFactorValidationMixin, FactorCreate, HeadcountBaseFactor
):
    """Schema for creating a headcount factor."""

    headcount_subclass: str | None = None


class HeadcountFactorUpdate(
    _HeadcountFactorValidationMixin, FactorUpdate, HeadcountBaseFactor
):
    """Schema for updating a headcount factor."""

    headcount_category: str | None = None
    headcount_class: str | None = None
    headcount_subclass: str | None = None
    number_of_unit_per_fte: float | None = None
    ef_kg_co2eq_per_unit: float | None = None
    unit: str | None = None


class HeadcountFactorResponse(FactorResponseGen, HeadcountBaseFactor):
    """Response schema for headcount factors."""

    headcount_subclass: str | None = None


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
