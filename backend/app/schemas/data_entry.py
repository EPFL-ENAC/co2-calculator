from typing import Any, Optional, Protocol, TypeVar

from pydantic import BaseModel

from app.models.data_entry import DataEntry, DataEntryBase, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum

# == =========== DTO BASE ================================= #

T = TypeVar("T", bound=BaseModel)


class Flattener(Protocol[T]):
    def is_for(self, data_entry: T) -> bool: ...

    dto: type[T]

    def __call__(self, data_entry: T) -> T: ...


# ============ DTO INPUT ================================= #


class DataEntryCreate(DataEntryBase):
    """Base factor schema."""

    data: dict


class DataEntryUpdate(DataEntryBase):
    """Schema for updating a DataEntry item."""

    data_entry_type_id: Optional[int] = None
    carbon_report_module_id: int
    data: dict[Any, Any]


# ============ DTO OUTPUT ================================= #
class DataEntryResponse(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data_entry_type_id: Optional[int]
    carbon_report_module_id: int
    data: dict[Any, Any]


class DataEntryResponseGen(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data_entry_type_id: Optional[int]
    carbon_report_module_id: int


# ---- Specific Flattener Responses DTO ------------------ #


class EquipmentFlattenerResponse(DataEntryResponseGen):
    active_usage_hours: int
    passive_usage_hours: int
    name: str
    power_factor_id: int
    kg_co2eq: float
    active_power_w: int
    standby_power_w: int
    equipment_class: Optional[str]
    sub_class: Optional[str]


class ExternalCloudFlattenerResponse(DataEntryResponseGen):
    name: str
    usage_hours: int
    kg_co2eq: float


class ExternalAIFlattenerResponse(DataEntryResponseGen):
    name: str
    usage_hours: int
    model_name: str
    kg_co2eq: float


# ---- Unflatteners DTO --------------------------------- #


def unflatten_data_entry_payload(payload: dict) -> dict:
    """Move non-meta fields into 'data' for DataEntry updates."""
    meta_fields = {"data_entry_type_id", "carbon_report_module_id", "id"}
    result = {k: v for k, v in payload.items() if k in meta_fields}
    # Everything else goes into 'data'
    data_fields = {k: v for k, v in payload.items() if k not in meta_fields}
    result["data"] = data_fields
    return result


# ----------- Flatteners --------------------------------- #


FLATTENERS: dict[DataEntryTypeEnum, Flattener] = {}


def register_flattener(key: DataEntryTypeEnum):
    def decorator(cls):
        FLATTENERS[key] = cls()
        return cls

    return decorator


@register_flattener(DataEntryTypeEnum.it)
@register_flattener(DataEntryTypeEnum.scientific)
@register_flattener(DataEntryTypeEnum.other)
class EquipmentFlattener:
    dto = EquipmentFlattenerResponse

    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment_electric_consumption

    def is_for(self, data_entry: DataEntry) -> bool:
        return data_entry.data_entry_type_id in {
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.other,
        }

    # rename to process or transform? we don't know what __call__ does
    def __call__(self, data_entry: DataEntry) -> EquipmentFlattenerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "active_power_w": data_entry.data["primary_factor"]["active_power_w"],
                "standby_power_w": data_entry.data["primary_factor"]["standby_power_w"],
                "equipment_class": data_entry.data["primary_factor"].get("class"),
                "sub_class": data_entry.data["primary_factor"].get("sub_class"),
            }
        )


@register_flattener(DataEntryTypeEnum.external_clouds)
class ExternalCloudFlattener:
    dto = ExternalCloudFlattenerResponse

    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds

    def is_for(self, data_entry: DataEntry) -> bool:
        return data_entry.data_entry_type_id in {
            DataEntryTypeEnum.external_clouds,
        }

    def __call__(self, data_entry: DataEntry) -> ExternalCloudFlattenerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
            }
        )


@register_flattener(DataEntryTypeEnum.external_ai)
class ExternalAIFlattener:
    dto = ExternalAIFlattenerResponse

    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai

    def is_for(self, data_entry: DataEntry) -> bool:
        return data_entry.data_entry_type_id in {
            DataEntryTypeEnum.external_ai,
        }

    def __call__(self, data_entry: DataEntry) -> ExternalAIFlattenerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
            }
        )


def get_flattener_for_data_entry(data_entry: DataEntry) -> Flattener:
    """
    Returns the first flattener instance that matches the data_entry.
    """
    for flattener in FLATTENERS.values():
        if flattener.is_for(data_entry):
            return flattener
    raise ValueError(
        f"""No flattener found for
        data_entry_type_id={getattr(data_entry, "data_entry_type_id", None)}"""
    )
