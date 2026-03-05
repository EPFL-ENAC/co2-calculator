from typing import Optional

from pydantic import field_validator

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

logger = get_logger(__name__)


class EquipmentHandlerResponse(DataEntryResponseGen):
    name: str
    equipment_class: str = None
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    primary_factor_id: Optional[int] = None
    kg_co2eq: Optional[float] = None
    active_power_w: Optional[int] = None
    standby_power_w: Optional[int] = None


class EquipmentHandlerCreate(DataEntryCreate):
    name: str
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    note: Optional[str] = None

    @field_validator(
        "active_usage_hours_per_week", "standby_usage_hours_per_week", mode="after"
    )
    @classmethod
    def validate_usage_hours(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Usage hours must be non-negative")
        if v > 168:
            raise ValueError("Usage hours cannot exceed 168 hours per week")
        return v


class EquipmentHandlerUpdate(DataEntryUpdate):
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    name: Optional[str] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None

    @field_validator(
        "active_usage_hours_per_week", "standby_usage_hours_per_week", mode="after"
    )
    @classmethod
    def validate_usage_hours(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Usage hours must be non-negative")
        if v > 168:
            raise ValueError("Usage hours cannot exceed 168 hours per week")
        return v


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
        "equipment_class": Factor.classification["kind"].as_string(),
        "sub_class": Factor.classification["subkind"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "equipment_class": Factor.classification["kind"].as_string(),
        "sub_class": Factor.classification["subkind"].as_string(),
    }

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        settings = get_settings()

        def _equipment_formula(ctx: dict, factor_values: dict) -> Optional[float]:
            active_hours = ctx.get("active_usage_hours_per_week")
            if active_hours is None:
                return None
            passive_hours = ctx.get("standby_usage_hours_per_week")
            if passive_hours is None:
                return None
            active_w = factor_values.get("active_power_w")
            if active_w is None:
                return None
            standby_w = factor_values.get("standby_power_w")
            if standby_w is None:
                return None
            ef = factor_values.get("ef_kg_co2eq_per_kwh")
            if any(
                v is None
                for v in [active_hours, passive_hours, active_w, standby_w, ef]
            ):
                return None
            active_w = float(active_hours) * active_w
            standby_w = float(passive_hours) * standby_w
            weekly_wh = active_w + standby_w
            annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000
            return annual_kwh * ef

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
