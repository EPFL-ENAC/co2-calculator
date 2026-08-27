from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.equipment.data_entries import (
    _EquipmentUsageHoursValidationMixin,
    _validate_non_negative_float,
)
from app.schemas.factor import (
    BaseFactorHandler,
    EmissionType,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


class _EquipmentFactorValidationMixin(_EquipmentUsageHoursValidationMixin):
    @field_validator(
        "active_power_w", "standby_power_w", "ef_kg_co2eq_per_kwh", mode="after"
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")


classification_fields: list[str] = ["equipment_class", "sub_class"]
value_fields: list[str] = [
    "active_power_w",
    "standby_power_w",
    "active_usage_hours_per_week",
    "standby_usage_hours_per_week",
    "ef_kg_co2eq_per_kwh",
]


class EquipmentFactorCreate(_EquipmentFactorValidationMixin, FactorCreate):
    equipment_class: str
    sub_class: str | None = None
    active_usage_hours_per_week: int  # make it mandatory
    standby_usage_hours_per_week: int  # make it mandatory
    active_power_w: float
    standby_power_w: float
    ef_kg_co2eq_per_kwh: float
    # equipment_category: str  # only for upload Mandatory (checked in csv upload)
    # equipment_category is the routing column (picks scientific/it/other).
    # It is consumed in the factor CSV provider, not carried on this DTO —
    # its presence + case-sensitive {scientific,it,other} enum is enforced
    # there (see base_factor_csv_provider._resolve_data_entry_type).


class EquipmentFactorUpdate(_EquipmentFactorValidationMixin, FactorUpdate):
    equipment_class: str | None = None
    sub_class: str | None = None
    active_power_w: float | None = None
    standby_power_w: float | None = None
    active_usage_hours_per_week: int | None = None
    standby_usage_hours_per_week: int | None = None
    ef_kg_co2eq_per_kwh: float | None = None


class EquipmentFactorResponse(FactorResponseGen):
    equipment_class: str
    sub_class: str | None = None
    active_power_w: float
    standby_power_w: float


class EquipmentFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.other,
    ]
    category_field: str = "equipment_category"
    emission_type: EmissionType = EmissionType.equipment

    create_dto = EquipmentFactorCreate
    update_dto = EquipmentFactorUpdate
    response_dto = EquipmentFactorResponse

    classification_fields: list[str] = classification_fields
    value_fields: list[str] = value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)
