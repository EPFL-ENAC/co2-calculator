from typing import Optional

from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


process_emissions_classification_fields: list[str] = [
    "category",
    "subcategory",
    "unit",
]
process_emissions_value_fields: list[str] = [
    "ef_kg_co2eq_per_unit",
]


class _ProcessEmissionsFactorValidationMixin:
    @field_validator("ef_kg_co2eq_per_unit", mode="after")
    @classmethod
    def validate_ef_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")


class ProcessEmissionsFactorCreate(
    _ProcessEmissionsFactorValidationMixin, FactorCreate
):
    category: str
    subcategory: Optional[str] = None
    unit: str
    ef_kg_co2eq_per_unit: float


class ProcessEmissionsFactorUpdate(
    _ProcessEmissionsFactorValidationMixin, FactorUpdate
):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    unit: Optional[str] = None
    ef_kg_co2eq_per_unit: Optional[float] = None


class ProcessEmissionsFactorResponse(FactorResponseGen):
    category: str
    subcategory: Optional[str] = None
    unit: str
    ef_kg_co2eq_per_unit: float


class ProcessEmissionsFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.process_emissions]
    emission_type = None  # resolved dynamically from category

    create_dto = ProcessEmissionsFactorCreate
    update_dto = ProcessEmissionsFactorUpdate
    response_dto = ProcessEmissionsFactorResponse

    classification_fields: list[str] = process_emissions_classification_fields
    value_fields: list[str] = process_emissions_value_fields
