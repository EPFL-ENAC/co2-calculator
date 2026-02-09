from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, field_validator, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.services.factor_service import FactorService

logger = get_logger(__name__)

# ============ DTO INPUT ================================= #


DATA_ENTRY_META_FIELDS = {"data_entry_type_id", "carbon_report_module_id", "id"}


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
        new_payload = dict(values)
        new_payload["data"] = {
            k: v for k, v in values.items() if k not in DATA_ENTRY_META_FIELDS
        }
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
    require_subkind_for_factor: bool = (
        True  # default to True, can be overridden by specific handlers
    )
    require_factor_to_match: bool = True

    # DTOs
    create_dto: Type[DataEntryCreate]
    update_dto: Type[DataEntryUpdate]
    response_dto: Type[DataEntryResponseGen]
    sort_map: Dict[str, Any]

    # kind/subkind fields
    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None

    def to_response(self, data_entry: T) -> DataEntryResponseGen: ...
    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict: ...
    def validate_create(self, payload: dict) -> DataEntryCreate: ...
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
    require_subkind_for_factor: bool = True
    require_factor_to_match: bool = True

    @classmethod
    def get_by_type(cls, data_entry_type: DataEntryTypeEnum) -> "ModuleHandler":
        """
        Returns the module handler instance for the given data_entry_type.
        """
        handler = MODULE_HANDLERS.get(data_entry_type)
        if handler is None:
            raise ValueError(
                f"No module handler found for data_entry_type={data_entry_type}"
            )
        return handler

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
    active_usage_hours: Optional[int] = None
    passive_usage_hours: Optional[int] = None
    primary_factor_id: Optional[int] = None
    kg_co2eq: Optional[float] = None
    active_power_w: Optional[int] = None
    standby_power_w: Optional[int] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    service_type: Optional[str] = None
    cloud_provider: Optional[str] = None
    spending: Optional[float] = None
    kg_co2eq: Optional[float] = None


class ExternalAIHandlerResponse(DataEntryResponseGen):
    # ai_provider,ai_use,frequency_use_per_day,user_count
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    frequency_use_per_day: Optional[int] = None
    user_count: Optional[int] = None
    kg_co2eq: Optional[float] = None


class HeadcountItemResponse(DataEntryResponseGen):
    name: str
    function: Optional[str] = None
    fte: Optional[float] = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: Optional[float] = None


# ---- CREATE DTO --------------------------------- #


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


class ExternalCloudHandlerCreate(DataEntryCreate):
    service_type: str
    cloud_provider: Optional[str] = None
    spending: float

    @field_validator("spending", mode="after")
    @classmethod
    def validate_spending(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Spending must be non-negative")
        return v


class ExternalAIHandlerCreate(DataEntryCreate):
    ai_provider: str
    ai_use: str
    frequency_use_per_day: Optional[int] = None
    user_count: int

    @field_validator("frequency_use_per_day", "user_count", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class HeadCountCreate(DataEntryCreate):
    name: str
    function: Optional[str] = None
    fte: Optional[float] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


class HeadCountStudentCreate(DataEntryCreate):
    fte: float

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float) -> float:
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


## UPDATE DTO


class HeadCountStudentUpdate(DataEntryUpdate):
    fte: Optional[float] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
        return v


class HeadCountUpdate(DataEntryUpdate):
    name: Optional[str] = None
    function: Optional[str] = None
    fte: Optional[float] = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be non-negative")
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


class ExternalCloudHandlerUpdate(DataEntryUpdate):
    service_type: Optional[str] = None
    cloud_provider: Optional[str] = None
    spending: Optional[float] = None

    @field_validator("spending", mode="after")
    @classmethod
    def validate_spending(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Spending must be non-negative")
        return v


class ExternalAIHandlerUpdate(DataEntryUpdate):
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    frequency_use_per_day: Optional[int] = None
    user_count: Optional[int] = None

    @field_validator("frequency_use_per_day", "user_count", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


## END UPDATE DTO


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

    filter_map = {
        "service_type": Factor.classification["subkind"].as_string(),
        "cloud_provider": Factor.classification["kind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ExternalCloudHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "service_type": data_entry.data["primary_factor"].get("subkind")
                or data_entry.data.get("service_type"),
                "cloud_provider": data_entry.data["primary_factor"].get("kind")
                or data_entry.data.get("cloud_provider"),
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

    filter_map = {
        "ai_provider": Factor.classification["kind"].as_string(),
        "ai_use": Factor.classification["subkind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ExternalAIHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "ai_provider": data_entry.data["primary_factor"].get("kind")
                or data_entry.data.get("ai_provider"),
                "ai_use": data_entry.data["primary_factor"].get("subkind")
                or data_entry.data.get("ai_use"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


# Headcount


class HeadcountMemberModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.member
    create_dto = HeadCountCreate
    update_dto = HeadCountUpdate
    response_dto = HeadcountItemResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False
    filter_map: dict[str, Any] = {
        "name": DataEntry.data["name"].as_string(),
        "function": DataEntry.data["function"].as_string(),
    }
    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "function": DataEntry.data["function"].as_string(),
        "fte": DataEntry.data["fte"].as_float(),
    }

    def to_response(self, data_entry: DataEntry) -> HeadcountItemResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> HeadCountCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> HeadCountUpdate:
        return self.update_dto.model_validate(payload)


class HeadcountStudentModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.student
    create_dto = HeadCountStudentCreate
    update_dto = HeadCountStudentUpdate
    response_dto = HeadCountStudentResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "fte": DataEntry.data["fte"].as_float(),
    }

    filter_map: dict[str, Any] = {}

    def to_response(self, data_entry: DataEntry) -> HeadCountStudentResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> HeadCountStudentCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> HeadCountStudentUpdate:
        return self.update_dto.model_validate(payload)
