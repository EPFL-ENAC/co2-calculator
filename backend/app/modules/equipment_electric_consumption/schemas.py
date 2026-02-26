from typing import Optional

from pydantic import field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
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
    active_usage_hours: Optional[int] = None
    passive_usage_hours: Optional[int] = None
    primary_factor_id: Optional[int] = None
    kg_co2eq: Optional[float] = None
    active_power_w: Optional[int] = None
    standby_power_w: Optional[int] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None


class EquipmentHandlerCreate(DataEntryCreate):
    active_usage_hours: Optional[int] = None
    passive_usage_hours: Optional[int] = None
    name: str
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None

    @field_validator("active_usage_hours", "passive_usage_hours", mode="after")
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
    active_usage_hours: Optional[int] = None
    passive_usage_hours: Optional[int] = None
    name: Optional[str] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None

    @field_validator("active_usage_hours", "passive_usage_hours", mode="after")
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
        "active_usage_hours": DataEntry.data["active_usage_hours"].as_float(),
        "passive_usage_hours": DataEntry.data["passive_usage_hours"].as_float(),
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
