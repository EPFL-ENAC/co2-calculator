from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.services.factor_service import FactorService

logger = get_logger(__name__)

# ============ DTO INPUT ================================= #


class DataEntryPayloadMixin(BaseModel):
    @classmethod
    def numeric_fields(cls) -> set[str]:
        numeric = set()
        for name, field in cls.model_fields.items():
            anno = field.annotation
            if anno is None:
                continue
            origin = get_origin(anno)
            args = get_args(anno)
            if origin is None:
                if anno in (int, float):
                    numeric.add(name)
                continue
            if any(a in (int, float) for a in args):
                numeric.add(name)
        return numeric

    @model_validator(mode="before")
    @classmethod
    def unflatten_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if "data" in values:
            return values
        meta_fields = {"data_entry_type_id", "carbon_report_module_id", "id"}
        new_payload = dict(values)
        new_payload["data"] = {k: v for k, v in values.items() if k not in meta_fields}
        return new_payload

    @model_validator(mode="before")
    @classmethod
    def coerce_numeric_strings(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        numeric_keys = cls.numeric_fields()

        def _coerce(payload: dict) -> dict:
            for key in numeric_keys:
                if key in payload and isinstance(payload[key], str):
                    try:
                        payload[key] = float(payload[key])
                    except ValueError:
                        logger.debug(
                            f"Could not coerce field {key} "
                            f"value '{payload[key]}' to float"
                        )
            return payload

        if "data" in values and isinstance(values["data"], dict):
            values["data"] = _coerce(values["data"])
        else:
            values = _coerce(values)
        return values


class DataEntryCreate(DataEntryPayloadMixin, DataEntryBase):
    """Base factor schema."""

    data: dict


class DataEntryUpdate(DataEntryPayloadMixin, DataEntryBase):
    """Schema for updating a DataEntry item."""

    data: dict


# ============ DTO OUTPUT ================================= #
class DataEntryResponse(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data: dict


class DataEntryResponseGen(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int


# == =========== DTO BASE ================================= #

T = TypeVar("T", bound=BaseModel, contravariant=True)


class ModuleHandler(Protocol[T]):
    # Type info
    module_type: ModuleTypeEnum
    data_entry_type: Optional[DataEntryTypeEnum] = None

    # DTOs
    create_dto: Type[DataEntryCreate]
    update_dto: Type[DataEntryUpdate]
    response_dto: Type[DataEntryResponseGen]
    sort_map: Dict[str, Any]

    def to_response(self, data_entry: T) -> DataEntryResponseGen: ...
    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict: ...
    def validate_create(self, payload: dict) -> BaseModel: ...
    def validate_update(self, payload: dict) -> DataEntryUpdate: ...


# ----------- ModuleHandlers --------------------------------- #


MODULE_HANDLERS: dict[DataEntryTypeEnum, ModuleHandler] = {}


class ModuleHandlerMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # not BaseModuleHandler itself
        if name != "BaseModuleHandler" and bases:
            # Try registration_keys first (for multiple registrations)
            keys = getattr(cls, "registration_keys", None)

            # Fall back to data_entry_type (for single registration)
            if keys is None and hasattr(cls, "data_entry_type"):
                if cls.data_entry_type is not None:
                    keys = [cls.data_entry_type]

            # Register for all keys
            if keys:
                for key in keys:
                    MODULE_HANDLERS[key] = cls()

        return cls


class BaseModuleHandler(metaclass=ModuleHandlerMeta):
    """base ModuleHandler with common logic"""

    # kind/subkind resolution can be implemented here if needed
    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
    data_entry_type: Optional[DataEntryTypeEnum] = None

    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict:
        if self.kind_field is None or self.subkind_field is None:
            return payload
        # payload can be flattened or with "data"
        data = payload.copy()

        # Merge in existing values for fields not in the payload
        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value

        kind = data.get(self.kind_field) or ""
        subkind = data.get(self.subkind_field)
        # Retrieve the factor
        factor_service = FactorService(db)

        factor = await factor_service.get_by_classification(
            data_entry_type=data_entry_type_id, kind=kind, subkind=subkind
        )
        payload["primary_factor_id"] = factor.id if factor else None
        return payload


# ---- Specific ModuleHandler Responses DTO ------------------ #


class EquipmentHandlerResponse(DataEntryResponseGen):
    name: str
    active_usage_hours: int
    passive_usage_hours: int
    primary_factor_id: Optional[int]
    kg_co2eq: Optional[float]
    active_power_w: Optional[int]
    standby_power_w: Optional[int]
    equipment_class: Optional[str]
    sub_class: Optional[str]


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    service_type: str
    cloud_provider: Optional[str]
    spending: float
    kg_co2eq: Optional[float]


class ExternalAIHandlerResponse(DataEntryResponseGen):
    # ai_provider,ai_use,frequency_use_per_day,user_count
    ai_provider: str
    ai_use: str
    frequency_use_per_day: int
    user_count: int
    kg_co2eq: Optional[float]


# ---- CREATE DTO --------------------------------- #


class EquipmentHandlerCreate(DataEntryCreate):
    active_usage_hours: int
    passive_usage_hours: int
    name: str
    equipment_class: str
    sub_class: str


class ExternalCloudHandlerCreate(DataEntryCreate):
    service_type: str
    cloud_provider: Optional[str] = None
    spending: float


class ExternalAIHandlerCreate(DataEntryCreate):
    ai_provider: str
    ai_use: str
    frequency_use_per_day: Optional[int] = None
    user_count: int


## UPDATE DTO


class EquipmentHandlerUpdate(DataEntryUpdate):
    active_usage_hours: Optional[int] = None
    passive_usage_hours: Optional[int] = None
    name: Optional[str] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None


class ExternalCloudHandlerUpdate(DataEntryUpdate):
    service_type: Optional[str] = None
    cloud_provider: Optional[str] = None
    spending: Optional[float] = None


class ExternalAIHandlerUpdate(DataEntryUpdate):
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    frequency_use_per_day: Optional[int] = None
    user_count: Optional[int] = None


## END UPDATE DTO


class EquipmentModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment_electric_consumption
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.other,
    ]

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
            "kg_co2eq": data_entry.data.get("kg_co2eq", None),
        }
        return self.response_dto.model_validate(new_entry)

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


class ExternalCloudModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    create_dto = ExternalCloudHandlerCreate
    update_dto = ExternalCloudHandlerUpdate
    response_dto = ExternalCloudHandlerResponse

    kind_field: str = "cloud_provider"
    subkind_field: str = "service_type"

    sort_map = {
        "id": DataEntry.id,
        "service_type": Factor.classification["subkind"].as_string(),
        "cloud_provider": Factor.classification["kind"].as_string(),
        "spending": DataEntry.data["spending"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
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

    def validate_create(self, payload: dict) -> ExternalCloudHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ExternalCloudHandlerUpdate:
        return self.update_dto.model_validate(payload)


class ExternalAIModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    create_dto = ExternalAIHandlerCreate
    update_dto = ExternalAIHandlerUpdate
    response_dto = ExternalAIHandlerResponse

    kind_field: str = "ai_provider"
    subkind_field: str = "ai_use"

    sort_map = {
        "id": DataEntry.id,
        "ai_provider": Factor.classification["kind"].as_string(),
        "ai_use": Factor.classification["subkind"].as_string(),
        "frequency_use_per_day": DataEntry.data["frequency_use_per_day"].as_float(),
        "user_count": DataEntry.data["user_count"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
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
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


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
