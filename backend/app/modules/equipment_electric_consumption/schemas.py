from typing import Optional, Self

from pydantic import ValidationInfo, field_validator, model_validator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
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
    EmissionType,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

logger = get_logger(__name__)

MAX_WEEKLY_USAGE_HOURS = 168


def _validate_weekly_usage_hours(v: Optional[int]) -> Optional[int]:
    if v is None:
        return v
    if v < 0:
        raise ValueError("Usage hours must be non-negative")
    if v > MAX_WEEKLY_USAGE_HOURS:
        raise ValueError(
            f"Usage hours cannot exceed {MAX_WEEKLY_USAGE_HOURS} hours per week"
        )
    return v


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class _EquipmentUsageHoursValidationMixin:
    active_usage_hours_per_week: Optional[int]
    standby_usage_hours_per_week: Optional[int]

    @field_validator(
        "active_usage_hours_per_week", "standby_usage_hours_per_week", mode="after"
    )
    @classmethod
    def validate_usage_hours(cls, v: Optional[int]) -> Optional[int]:
        return _validate_weekly_usage_hours(v)

    @model_validator(mode="after")
    def validate_total_usage_hours(self) -> Self:
        active_hours = self.active_usage_hours_per_week
        standby_hours = self.standby_usage_hours_per_week
        if active_hours is not None and standby_hours is not None:
            if active_hours + standby_hours > MAX_WEEKLY_USAGE_HOURS:
                raise ValueError(
                    "The sum of active_usage_hours_per_week and "
                    "standby_usage_hours_per_week must be <= 168"
                )
        return self


class _EquipmentFactorValidationMixin(_EquipmentUsageHoursValidationMixin):
    @field_validator(
        "active_power_w", "standby_power_w", "ef_kg_co2eq_per_kwh", mode="after"
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")


## DATA-ENTRY-SPECIFIC SCHEMAS AND HANDLER FOR EQUIPMENT ELECTRIC CONSUMPTION MODULE


# https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description/#equipment
class EquipmentHandlerResponse(DataEntryResponseGen):
    name: str
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    primary_factor_id: Optional[int] = None
    kg_co2eq: Optional[float] = None
    active_power_w: Optional[int] = None
    standby_power_w: Optional[int] = None


class EquipmentHandlerCreate(_EquipmentUsageHoursValidationMixin, DataEntryCreate):
    # unit_institutional_id: str #only for data.csv
    name: str
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    note: Optional[str] = None


class EquipmentHandlerUpdate(_EquipmentUsageHoursValidationMixin, DataEntryUpdate):
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    name: Optional[str] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None
    note: Optional[str] = None


class EquipmentModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment_electric_consumption
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.other,
    ]
    # Allow subkind to be optional for equipment
    require_subkind_for_factor = False

    create_dto = EquipmentHandlerCreate
    update_dto = EquipmentHandlerUpdate
    response_dto = EquipmentHandlerResponse

    kind_field: str = "equipment_class"
    subkind_field: str = "sub_class"
    factor_value_fields: list[str] = [
        "active_usage_hours_per_week",
        "standby_usage_hours_per_week",
    ]

    # Add the sort_map here
    sort_map = {
        "id": DataEntry.id,
        "active_usage_hours_per_week": DataEntry.data[
            "active_usage_hours_per_week"
        ].as_float(),
        "standby_usage_hours_per_week": DataEntry.data[
            "standby_usage_hours_per_week"
        ].as_float(),
        "name": DataEntry.data["name"].as_string(),
        "active_power_w": Factor.values["active_power_w"].as_float(),
        "standby_power_w": Factor.values["standby_power_w"].as_float(),
        "equipment_class": Factor.classification["equipment_class"].as_string(),
        "sub_class": Factor.classification["sub_class"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "equipment_class": Factor.classification["equipment_class"].as_string(),
        "sub_class": Factor.classification["sub_class"].as_string(),
    }

    async def pre_compute(self, data_entry, session) -> dict:
        """Validate usage hours constraints (user data only)."""
        data = data_entry.data if hasattr(data_entry, "data") else {}

        active_hours = data.get("active_usage_hours_per_week")
        standby_hours = data.get("standby_usage_hours_per_week")

        if active_hours is None or standby_hours is None:
            return {}

        total_hours = float(active_hours) + float(standby_hours)
        if total_hours > MAX_WEEKLY_USAGE_HOURS:
            raise ValueError(
                "The sum of active_usage_hours_per_week and "
                "standby_usage_hours_per_week must be <= 168"
            )

        return {}

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _equipment_formula(ctx: dict, factor_values: dict) -> Optional[float]:
            active_hours = ctx.get("active_usage_hours_per_week")
            standby_hours = ctx.get("standby_usage_hours_per_week")
            if active_hours is None or standby_hours is None:
                return None

            active_power_w = factor_values.get("active_power_w")
            standby_power_w = factor_values.get("standby_power_w")
            ef = factor_values.get("ef_kg_co2eq_per_kwh")
            if active_power_w is None or standby_power_w is None or ef is None:
                return None

            weekly_wh = (float(active_hours) * float(active_power_w)) + (
                float(standby_hours) * float(standby_power_w)
            )
            annual_kwh = (weekly_wh * get_settings().WEEKS_PER_YEAR) / 1000
            return annual_kwh * float(ef)

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_equipment_formula,
            )
        ]

    def to_response(self, data_entry: DataEntry) -> EquipmentHandlerResponse:
        new_entry = {
            "id": data_entry.id,
            "data_entry_type_id": data_entry.data_entry_type_id,
            "carbon_report_module_id": data_entry.carbon_report_module_id,
            **data_entry.data,
            "active_power_w": data_entry.data.get("primary_factor", {}).get(
                "active_power_w", None
            ),
            "standby_power_w": data_entry.data.get("primary_factor", {}).get(
                "standby_power_w", None
            ),
            "equipment_class": data_entry.data.get("primary_factor", {}).get("class")
            or data_entry.data.get("equipment_class"),
            "sub_class": data_entry.data.get("primary_factor", {}).get("sub_class")
            or data_entry.data.get("sub_class"),
            "kg_co2eq": data_entry.data.get("kg_co2eq", None),
        }
        return self.response_dto.model_validate(new_entry)

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


## FACTORS for equipment electric consumption


classification_fields: list[str] = ["equipment_class", "sub_class"]
value_fields: list[str] = [
    "active_power_w",
    "standby_power_w",
    "active_usage_hours_per_week",
    "standby_usage_hours_per_week",
    "ef_kg_co2eq_per_kwh",
]


class EquipmentFactorCreate(_EquipmentFactorValidationMixin, FactorCreate):
    # data_entry_type: str #only for upload in datamanagement
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: int
    standby_usage_hours_per_week: int
    active_power_w: float
    standby_power_w: float
    ef_kg_co2eq_per_kwh: float


class EquipmentFactorUpdate(_EquipmentFactorValidationMixin, FactorUpdate):
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None
    active_power_w: Optional[float] = None
    standby_power_w: Optional[float] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    ef_kg_co2eq_per_kwh: Optional[float] = None


class EquipmentFactorResponse(FactorResponseGen):
    equipment_class: str
    sub_class: Optional[str] = None
    active_power_w: float
    standby_power_w: float


class EquipmentFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.other,
    ]
    emission_type: EmissionType = EmissionType.equipment

    create_dto = EquipmentFactorCreate
    update_dto = EquipmentFactorUpdate
    response_dto = EquipmentFactorResponse

    classification_fields: list[str] = classification_fields
    value_fields: list[str] = value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)
