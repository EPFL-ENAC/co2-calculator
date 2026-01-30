from typing import Any, Dict, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel

from app.models.data_entry import DataEntry, DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum

# == =========== DTO BASE ================================= #

T = TypeVar("T", bound=BaseModel, contravariant=True)


class ModuleHandler(Protocol[T]):
    # Type info
    module_type: ModuleTypeEnum
    data_entry_type: Optional[DataEntryTypeEnum] = None

    # DTOs
    create_dto: Type[BaseModel]
    update_dto: Type[BaseModel]
    response_dto: Type[BaseModel]
    sort_map: Dict[str, Any]

    def to_response(self, data_entry: T) -> BaseModel: ...
    def validate_create(self, payload: dict) -> BaseModel: ...
    def validate_update(self, payload: dict) -> BaseModel: ...


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
    primary_factor_id: int
    kg_co2eq: Optional[float]
    active_power_w: int
    standby_power_w: int
    equipment_class: Optional[str]
    sub_class: Optional[str]


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    service_type: str
    cloud_provider: str
    region: str
    spending: float
    kg_co2eq: Optional[float]


class ExternalAIHandlerResponse(DataEntryResponseGen):
    # ai_provider,ai_use,frequency_use_per_day,user_count
    ai_provider: str
    ai_use: str
    frequency_use_per_day: int
    user_count: int
    kg_co2eq: Optional[float]


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
        "equipment_class": Factor.classification["kind"].as_string(),
        "sub_class": Factor.classification["subkind"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
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
            "equipment_class": data_entry.data.get("primary_factor", {}).get("class"),
            "sub_class": data_entry.data.get("primary_factor", {}).get("sub_class"),
            "kg_co2eq": 0,
        }
        return self.response_dto.model_validate(new_entry)

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(unflatten_data_entry_payload(payload))

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(unflatten_data_entry_payload(payload))


@register_module_handler(DataEntryTypeEnum.external_clouds)
class ExternalCloudModuleHandler(ModuleHandler[DataEntry]):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    create_dto = DataEntryCreate
    update_dto = DataEntryUpdate
    response_dto = ExternalCloudHandlerResponse

    sort_map = {
        "id": DataEntry.id,
    }

    def to_response(self, data_entry: DataEntry) -> ExternalCloudHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "service_type": data_entry.data["primary_factor"].get("subkind"),
                "cloud_provider": data_entry.data["primary_factor"].get("kind"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(unflatten_data_entry_payload(payload))

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(unflatten_data_entry_payload(payload))


@register_module_handler(DataEntryTypeEnum.external_ai)
class ExternalAIModuleHandler(ModuleHandler[DataEntry]):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    create_dto = DataEntryCreate
    update_dto = DataEntryUpdate
    response_dto = ExternalAIHandlerResponse

    sort_map = {
        "id": DataEntry.id,
    }

    def to_response(self, data_entry: DataEntry) -> ExternalAIHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "ai_provider": data_entry.data["primary_factor"].get("kind"),
                "ai_use": data_entry.data["primary_factor"].get("subkind"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(unflatten_data_entry_payload(payload))

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(unflatten_data_entry_payload(payload))


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
