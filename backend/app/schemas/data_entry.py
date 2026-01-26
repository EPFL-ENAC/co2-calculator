from typing import Any, Dict, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel

from app.models.data_entry import DataEntry, DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum

# == =========== DTO BASE ================================= #

T = TypeVar("T", bound=BaseModel)  # Base DTO (SQLModel)
C = TypeVar("C", bound=BaseModel)  # Create DTO
U = TypeVar("U", bound=BaseModel)  # Update DTO
R = TypeVar("R", bound=BaseModel)  # Response DTO


class ModuleHandler(Protocol[T]):
    # Type info
    module_type: ModuleTypeEnum
    data_entry_type: Optional[DataEntryTypeEnum] = None

    # DTOs
    create_dto: Type[C]
    update_dto: Type[U]
    response_dto: Type[R]

    # Sort map for this type
    sort_map: Optional[Dict[str, Any]] = None

    def is_for(self, data_entry: T) -> bool: ...
    def to_response(self, data_entry: T) -> R: ...
    def validate_create(self, payload: dict) -> C: ...
    def validate_update(self, payload: dict) -> U: ...


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


# ---- Specific ModuleHandler Responses DTO ------------------ #


class EquipmentHandlerResponse(DataEntryResponseGen):
    active_usage_hours: int
    passive_usage_hours: int
    name: str
    power_factor_id: int
    kg_co2eq: float
    active_power_w: int
    standby_power_w: int
    equipment_class: Optional[str]
    sub_class: Optional[str]


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    name: str
    usage_hours: int
    kg_co2eq: float


class ExternalAIHandlerResponse(DataEntryResponseGen):
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


# ----------- ModuleHandlers --------------------------------- #


MODULE_HANDLERS: dict[DataEntryTypeEnum, ModuleHandler] = {}


def register_module_handler(key: DataEntryTypeEnum):
    def decorator(cls):
        MODULE_HANDLERS[key] = cls()
        return cls

    return decorator


@register_module_handler(DataEntryTypeEnum.it)
@register_module_handler(DataEntryTypeEnum.scientific)
@register_module_handler(DataEntryTypeEnum.other)
class EquipmentModuleHandler(ModuleHandler[DataEntry]):
    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment_electric_consumption
    data_entry_type: DataEntryTypeEnum | None = None
    create_dto = DataEntryCreate
    update_dto = DataEntryUpdate
    response_dto = EquipmentHandlerResponse

    # Add the sort_map here
    sort_map = {
        "id": DataEntry.id,
        "active_usage_hours": DataEntry.data["active_usage_hours"].as_float(),
        "passive_usage_hours": DataEntry.data["passive_usage_hours"].as_float(),
        "name": DataEntry.data["name"].as_string(),
        "active_power_w": Factor.values["active_power_w"].as_float(),
        "standby_power_w": Factor.values["standby_power_w"].as_float(),
        "equipment_class": Factor.classification["class"].as_string(),
        "sub_class": Factor.classification["sub_class"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    def is_for(self, data_entry: DataEntry) -> bool:
        return data_entry.data_entry_type_id in {
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.other,
        }

    # rename to process or transform? we don't know what __call__ does
    def to_response(self, data_entry: DataEntry) -> response_dto:
        return self.response_dto.model_validate(
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

    def validate_create(self, payload: dict) -> C:
        return self.create_dto.model_validate(unflatten_data_entry_payload(payload))

    def validate_update(self, payload: dict) -> U:
        return self.update_dto.model_validate(unflatten_data_entry_payload(payload))


@register_module_handler(DataEntryTypeEnum.external_clouds)
class ExternalCloudModuleHandler(ModuleHandler[DataEntry]):
    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment_electric_consumption
    data_entry_type: DataEntryTypeEnum | None = None
    create_dto = DataEntryCreate
    update_dto = DataEntryUpdate
    response_dto = ExternalCloudHandlerResponse

    sort_map = {
        "id": DataEntry.id,
    }

    def is_for(self, data_entry: DataEntry) -> bool:
        return data_entry.data_entry_type_id in {
            DataEntryTypeEnum.external_clouds,
        }

    def __call__(self, data_entry: DataEntry) -> ExternalCloudHandlerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
            }
        )


@register_module_handler(DataEntryTypeEnum.external_ai)
class ExternalAIModuleHandler(ModuleHandler[DataEntry]):
    dto = ExternalAIHandlerResponse

    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai

    sort_map = {
        "id": DataEntry.id,
    }

    def is_for(self, data_entry: DataEntry) -> bool:
        return DataEntryTypeEnum(data_entry.data_entry_type_id) in {
            DataEntryTypeEnum.external_ai,
        }

    def __call__(self, data_entry: DataEntry) -> ExternalAIHandlerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
            }
        )


def get_data_entry_handler(data_entry: DataEntry) -> ModuleHandler:
    """
    Returns the first module handler instance that matches the data_entry.
    """
    for handler in MODULE_HANDLERS.values():
        if handler.is_for(data_entry):
            return handler
    raise ValueError(
        f"""No module handler found for
        data_entry_type_id={getattr(data_entry, "data_entry_type_id", None)}"""
    )


def get_data_entry_handler_by_type(
    data_entry_type: DataEntryTypeEnum,
) -> ModuleHandler:
    """
    Returns the module handler instance for the given data_entry_type.
    """
    handler = MODULE_HANDLERS.get(data_entry_type)
    if handler is None:
        raise ValueError(
            f"No module handler found for data_entry_type={data_entry_type}"
        )
    return handler


## CREATE/UPDATE DTO above

# # Optionally, you can create a registry for these DTOs as well:
# CREATE_DTOS = {
#     ModuleTypeEnum.equipment_electric_consumption: EquipmentCreate,
#     ModuleTypeEnum.external_cloud_and_ai: ExternalCloudCreate,
#  # or ExternalAICreate as needed
#     # Add more as needed
# }

# UPDATE_DTOS = {
#     ModuleTypeEnum.equipment_electric_consumption: EquipmentUpdate,
#     ModuleTypeEnum.external_cloud_and_ai: ExternalCloudUpdate,
# # or ExternalAIUpdate as needed
#     # Add more as needed
# }
