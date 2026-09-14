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
from app.schemas.fields import OptionalClassificationKey

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

# Closed vocabularies (#2588): the values the shipped headcount factor CSVs
# carry. An unknown value fails the upload instead of creating a factor no
# computation can name. Extend the lists here when the data manager adds one.
HEADCOUNT_CATEGORIES: list[str] = ["commuting", "food", "waste"]
HEADCOUNT_CLASSES: list[str] = [
    "biogas",
    "car",
    "composting",
    "cycling",
    "incineration",
    "non_vegetarian",
    "powered_two_wheeler",
    "public_transport",
    "recycling",
    "vegetarian",
    "walking",
]
HEADCOUNT_UNITS: list[str] = ["kg", "km"]

_VOCABULARY_BY_FIELD: dict[str, list[str]] = {
    "headcount_category": HEADCOUNT_CATEGORIES,
    "headcount_class": HEADCOUNT_CLASSES,
    "unit": HEADCOUNT_UNITS,
}


def _validate_non_negative_float(v: float | None, field_name: str) -> float | None:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


def _validate_closed_vocabulary(v: str | None, field_name: str) -> str | None:
    if v is None:
        return None
    # strip + lower: the join key must match the entry-side casing (#1489)
    normalized = v.strip().lower()
    allowed = _VOCABULARY_BY_FIELD[field_name]
    if normalized not in allowed:
        raise ValueError(f"{field_name} must be one of: {', '.join(allowed)}")
    return normalized


class _HeadcountFactorValidationMixin:
    """Shared validators for headcount factor DTOs."""

    @field_validator("number_of_unit_per_fte", "ef_kg_co2eq_per_unit", mode="after")
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("headcount_category", "headcount_class", "unit", mode="after")
    @classmethod
    def validate_closed_vocabulary(
        cls, v: str | None, info: ValidationInfo
    ) -> str | None:
        return _validate_closed_vocabulary(v, info.field_name or "")


class HeadcountBaseFactor:
    """Fields shared by all headcount factor DTOs."""

    headcount_category: str
    headcount_class: str
    headcount_subclass: OptionalClassificationKey
    number_of_unit_per_fte: float
    ef_kg_co2eq_per_unit: float
    unit: str


class HeadcountFactorCreate(
    _HeadcountFactorValidationMixin, FactorCreate, HeadcountBaseFactor
):
    """Schema for creating a headcount factor."""

    headcount_subclass: OptionalClassificationKey = None


class HeadcountFactorUpdate(
    _HeadcountFactorValidationMixin, FactorUpdate, HeadcountBaseFactor
):
    """Schema for updating a headcount factor."""

    headcount_category: str | None = None
    headcount_class: str | None = None
    headcount_subclass: OptionalClassificationKey = None
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
