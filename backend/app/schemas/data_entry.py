import json
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

import yaml
from pydantic import BaseModel, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryBase, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.taxonomy import TaxonomyNode
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
    note: Optional[str] = None


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
    extra_factor_fields: list[str] = []

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
    async def get_taxonomy(
        self, data_entry_type: DataEntryTypeEnum, db: AsyncSession
    ) -> TaxonomyNode: ...


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

    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
    kind_label_field: Optional[str] = None
    subkind_label_field: Optional[str] = None
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
        if self.kind_field is None:
            return payload
        data = payload.copy()

        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value

        kind = data.get(self.kind_field, "")
        subkind = data.get(self.subkind_field, "")
        # Retrieve the factor
        factor_service = FactorService(db)

        factor = await factor_service.get_by_classification(
            data_entry_type=data_entry_type_id, kind=kind, subkind=subkind
        )
        payload["primary_factor_id"] = factor.id if factor else None
        return payload

    async def get_taxonomy(
        self, data_entry_type: DataEntryTypeEnum, db: AsyncSession
    ) -> TaxonomyNode:
        """Default implementation to get taxonomy based on factors for this handler's
        data entry type. Specific handlers can override this method to implement
        custom taxonomy logic if needed, based on a static file or other source
        instead of factors. This default implementation assumes a two-level taxonomy
        based on kind and subkind fields.
        """
        return await self.get_taxonomy_from_factors(data_entry_type, db)

    async def get_taxonomy_from_file(self, path: Path) -> TaxonomyNode:
        """Implementation to get taxonomy from a static file."""
        if not path.exists():
            raise FileNotFoundError(f"Taxonomy file not found at path: {path}")
        # If path ends with .json
        if path.suffix.lower() == ".json":
            with open(path, "r") as f:
                taxonomy_dict = json.load(f)
            return TaxonomyNode.model_validate(taxonomy_dict)
        # If path ends with .yaml or .yml
        if path.suffix.lower() in [".yaml", ".yml"]:
            with open(path, "r") as f:
                taxonomy_dict = yaml.safe_load(f)
            return TaxonomyNode.model_validate(taxonomy_dict)
        # For other formats, implement the necessary parsing logic here
        raise ValueError(f"Unsupported taxonomy file format: {path.suffix}")

    async def get_taxonomy_from_factors(
        self, data_entry_type: DataEntryTypeEnum, db: AsyncSession
    ) -> TaxonomyNode:
        """Get the taxonomy for this module handler, based on its data entry type.
          This default implementation assumes a two-level taxonomy based on kind
          and subkind fields. Handlers can override this method to implement custom
          taxonomy logic if needed.

        Args:
          data_entry_type: The data entry type for which to get the taxonomy
          db: Database session for retrieving factors if needed
        Returns:
          TaxonomyNode representing the taxonomy for this module handler's
          data entry type
        """
        # Retrieve the factor
        factor_service = FactorService(db)
        factors = await factor_service.list_by_data_entry_type(data_entry_type)
        children: list[TaxonomyNode] = []
        for factor in factors:
            classification = factor.classification or {}
            if self.kind_field is None or self.kind_field not in classification:
                continue  # if no kind/subkind fields defined, skip adding nodes
            kind_value = classification.get(self.kind_field, "")
            if kind_value == "":
                continue  # skip if no kind in classification
            # find the children based on kind or add it
            kind_node = next((c for c in children if c.name == kind_value), None)
            if not kind_node:
                if self.kind_label_field and self.kind_label_field in classification:
                    label = classification.get(self.kind_label_field, kind_value)
                else:
                    label = self.to_label(kind_value)
                kind_node = TaxonomyNode(
                    name=kind_value,
                    label=label,
                )
                children.append(kind_node)
            if self.subkind_field is None or self.subkind_field not in classification:
                continue  # if no subkind field defined, skip adding subkind nodes
            subkind_value = classification.get(self.subkind_field, "")
            if subkind_value == "":
                continue  # skip if no subkind in classification
            if kind_node.children is None:
                kind_node.children = []
            if self.subkind_label_field and self.subkind_label_field in classification:
                subkind_label = classification.get(
                    self.subkind_label_field, subkind_value
                )
            else:
                subkind_label = self.to_label(subkind_value)
            kind_node.children.append(
                TaxonomyNode(
                    name=subkind_value,
                    label=subkind_label,
                )
            )
        return TaxonomyNode(
            name=data_entry_type.name,
            label=self.to_label(data_entry_type.name),
            children=children,
        )

    @staticmethod
    def to_label(name: str) -> str:
        """Convert a name to a label by replacing underscores with spaces and
        capitalizing words.
        """
        # if all capital letters, keep it as is (e.g. for acronyms),
        # otherwise convert to title case
        if name.isupper():
            return name
        # capitalize only the first letter, to preserve any existing
        # capitalization (e.g. for acronyms within the name)
        return name[0].upper() + name[1:].replace("_", " ")


# --- Helpers ------------------------------------------------ #


async def resolve_primary_factor_if_kind_or_subkind_changed(
    handler: ModuleHandler,
    update_payload: dict,
    data_entry_type: DataEntryTypeEnum,
    item_data: dict,
    existing_data: dict | None,
    db: AsyncSession,
) -> dict:
    """
    Resolve primary_factor_id only if kind or subkind fields have changed.

    Args:
        handler: The module handler for this data entry type
        update_payload: The payload to update
        data_entry_type: The data entry type enum
        item_data: The incoming item data from the request
        existing_data: The existing data entry data
        db: Database session

    Returns:
        Updated payload with primary_factor_id resolved if applicable
    """
    handler_kind_field = handler.kind_field or ""
    handler_subkind_field = handler.subkind_field or ""

    if existing_data is None:
        # No existing data, resolve factor based on incoming data
        return await handler.resolve_primary_factor_id(
            update_payload, data_entry_type, db, existing_data=None
        )
    kind_changed = (handler_kind_field in item_data) and (
        item_data[handler_kind_field] != existing_data.get(handler_kind_field)
    )
    subkind_changed = (handler_subkind_field in item_data) and (
        item_data[handler_subkind_field] != existing_data.get(handler_subkind_field)
    )
    extra_changed = any(
        (f in item_data) and (item_data[f] != existing_data.get(f))
        for f in getattr(handler, "extra_factor_fields", [])
    )

    if kind_changed:
        update_payload[handler_subkind_field] = None
        update_payload["primary_factor_id"] = None

    if kind_changed or subkind_changed or extra_changed:
        update_payload = await handler.resolve_primary_factor_id(
            update_payload, data_entry_type, db, existing_data=existing_data
        )

    return update_payload


# ---- Mixins ------------------------------------------------- #
class DepartureDateMixin(BaseModel):
    """Mixin for parsing departure_date from various formats."""

    @field_validator("departure_date", mode="before", check_fields=False)
    @classmethod
    def parse_departure_date(cls, v: Any) -> Optional[date]:
        """Parse departure_date from various formats (date, datetime, string)."""
        if v is None:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            if not v.strip():
                return None
            normalized = v.replace("/", "-")
            try:
                return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date()
            except ValueError:
                return date.fromisoformat(normalized)
        return v


# ---- Specific ModuleHandler Responses DTO ------------------ #
class ProfessionalTravelHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    transport_mode: TransportModeEnum
    cabin_class: Optional[str] = None  # eco, business, first, class_1, class_2
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    is_round_trip: bool = False
    trip_direction: Optional[str] = None  # "outbound" or "return"
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    kg_co2eq: Optional[float] = None


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
    sciper: Optional[str] = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: Optional[float] = None


# ---- CREATE DTO --------------------------------- #


class ProfessionalTravelHandlerCreate(DepartureDateMixin, DataEntryCreate):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    transport_mode: TransportModeEnum
    cabin_class: Optional[str] = None  # eco, business, first, class_1, class_2
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    is_round_trip: bool = False
    trip_direction: Optional[str] = None  # "outbound" or "return"


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
    sciper: Optional[str] = None

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


class ProfessionalTravelHandlerUpdate(DataEntryUpdate):
    traveler_name: Optional[str] = None
    traveler_id: Optional[int] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    transport_mode: Optional[TransportModeEnum] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None


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
        primary_factor = data_entry.data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "service_type": primary_factor.get("subkind")
                or data_entry.data.get("service_type"),
                "cloud_provider": primary_factor.get("kind")
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


# Professional Travel


class ProfessionalTravelModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.professional_travel
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.trips
    create_dto = ProfessionalTravelHandlerCreate
    update_dto = ProfessionalTravelHandlerUpdate
    response_dto = ProfessionalTravelHandlerResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "traveler_name": DataEntry.data["traveler_name"].as_string(),
        "departure_date": DataEntry.data["departure_date"].as_string(),
        "transport_mode": DataEntry.data["transport_mode"].as_string(),
        "cabin_class": DataEntry.data["cabin_class"].as_string(),
        "number_of_trips": DataEntry.data["number_of_trips"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    # async def resolve_primary_factor_id(
    #     self,
    #     payload: dict,
    #     data_entry_type_id: DataEntryTypeEnum,
    #     db: AsyncSession,
    #     existing_data: Optional[dict] = None,
    # ) -> dict:
    #     """
    #     Resolve factor ID if kind/or subkind change
    #     Sets primary_factor_id

    #     distance is computed in emission_service
    #     """
    # # Merge payload with existing data
    # origin_id = payload.get("origin_location_id")
    # dest_id = payload.get("destination_location_id")
    # transport_mode = payload.get("transport_mode")

    # if existing_data:
    #     if origin_id is None:
    #         origin_id = existing_data.get("origin_location_id")
    #     if dest_id is None:
    #         dest_id = existing_data.get("destination_location_id")
    #     if transport_mode is None:
    #         transport_mode = existing_data.get("transport_mode")

    # if not origin_id or not dest_id:
    #     logger.warning("Missing origin or destination location for trip")
    #     return payload

    # if not transport_mode or transport_mode not in
    #   (TransportModeEnum.plane, TransportModeEnum.train):
    #     logger.warning(f"Unknown transport_mode: {transport_mode}")
    #     return payload

    # OriginLoc = aliased(Location, name="origin")
    # DestLoc = aliased(Location, name="dest")

    # stmt = (
    #     sa_select(OriginLoc, DestLoc, Factor)
    #     .select_from(OriginLoc)
    #     .join(DestLoc, col(DestLoc.id) == dest_id)
    #     .outerjoin(
    #         Factor,
    #         and_(
    #             col(Factor.data_entry_type_id) == DataEntryTypeEnum.trips.value,
    #             Factor.classification["kind"].as_string() == transport_mode,
    #         ),
    #     )
    #     .where(col(OriginLoc.id) == origin_id)
    # )

    # result = await db.execute(stmt)
    # rows = result.all()

    # if not rows:
    #     logger.warning("Missing origin or destination location for trip")
    #     return payload

    # origin_loc, dest_loc = rows[0][0], rows[0][1]
    # factors = [row[2] for row in rows if row[2] is not None]

    # payload["origin"] = origin_loc.name
    # payload["destination"] = dest_loc.name

    # if transport_mode == "plane":
    #     distance_km, factor = resolve_flight_factor(origin_loc, dest_loc, factors)
    # else:  # train
    #     distance_km, factor = resolve_train_factor(origin_loc, dest_loc, factors)

    # payload["distance_km"] = distance_km
    # payload["primary_factor_id"] = factor.id if factor else None

    # return payload

    def to_response(self, data_entry: DataEntry) -> ProfessionalTravelHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> ProfessionalTravelHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ProfessionalTravelHandlerUpdate:
        return self.update_dto.model_validate(payload)


# Process Emissions


class ProcessEmissionsHandlerResponse(DataEntryResponseGen):
    emitted_gas: str
    sub_category: Optional[str] = None
    quantity_kg: float
    kg_co2eq: Optional[float] = None


class ProcessEmissionsHandlerCreate(DataEntryCreate):
    emitted_gas: str
    sub_category: Optional[str] = None
    quantity_kg: float

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0.001:
            raise ValueError("Quantity must be >= 0.001 kg")
        return v


class ProcessEmissionsHandlerUpdate(DataEntryUpdate):
    emitted_gas: Optional[str] = None
    sub_category: Optional[str] = None
    quantity_kg: Optional[float] = None

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0.001:
            raise ValueError("Quantity must be >= 0.001 kg")
        return v


class ProcessEmissionsModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.process_emissions
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.process_emissions

    create_dto = ProcessEmissionsHandlerCreate
    update_dto = ProcessEmissionsHandlerUpdate
    response_dto = ProcessEmissionsHandlerResponse

    kind_field: str = "emitted_gas"
    subkind_field: str = "sub_category"
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "emitted_gas": Factor.classification["kind"].as_string(),
        "sub_category": Factor.classification["subkind"].as_string(),
        "quantity_kg": DataEntry.data["quantity_kg"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "emitted_gas": Factor.classification["kind"].as_string(),
        "sub_category": Factor.classification["subkind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ProcessEmissionsHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "emitted_gas": primary_factor.get("kind")
                or data_entry.data.get("emitted_gas"),
                "sub_category": primary_factor.get("subkind")
                or data_entry.data.get("sub_category"),
            }
        )

    def validate_create(self, payload: dict) -> ProcessEmissionsHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ProcessEmissionsHandlerUpdate:
        return self.update_dto.model_validate(payload)


# ============ BUILDING ROOMS ================================= #


class BuildingRoomHandlerResponse(DataEntryResponseGen):
    building_name: str
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None
    heating_kwh_per_m2: Optional[float] = None
    cooling_kwh_per_m2: Optional[float] = None
    ventilation_kwh_per_m2: Optional[float] = None
    lighting_kwh_per_m2: Optional[float] = None
    heating_kwh: Optional[float] = None
    cooling_kwh: Optional[float] = None
    ventilation_kwh: Optional[float] = None
    lighting_kwh: Optional[float] = None
    kg_co2eq: Optional[float] = None


class BuildingRoomHandlerCreate(DataEntryCreate):
    building_name: str
    room_name: str
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None

    @field_validator("room_surface_square_meter", mode="after")
    @classmethod
    def validate_surface(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Surface must be > 0")
        return v


class BuildingRoomHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None

    @field_validator("room_surface_square_meter", mode="after")
    @classmethod
    def validate_surface(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Surface must be > 0")
        return v


class BuildingRoomModuleHandler(BaseModuleHandler):
    """Handler for building rooms submodule.

    Dropdowns use building_name (kind) and room_name (subkind) from archibus.
    room_type drives the actual energy factor lookup (Office, Laboratories, etc.).
    kg_co2eq = surface × sum(kWh/m² from factor) × electricity emission factor.
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.building

    create_dto = BuildingRoomHandlerCreate
    update_dto = BuildingRoomHandlerUpdate
    response_dto = BuildingRoomHandlerResponse

    kind_field: str = "building_name"
    subkind_field: str = "room_name"
    extra_factor_fields: list[str] = ["room_type"]
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "building_name": DataEntry.data["building_name"].as_string(),
        "room_name": DataEntry.data["room_name"].as_string(),
        "room_type": DataEntry.data["room_type"].as_string(),
        "room_surface_square_meter": DataEntry.data[
            "room_surface_square_meter"
        ].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "building_name": DataEntry.data["building_name"].as_string(),
        "room_name": DataEntry.data["room_name"].as_string(),
        "room_type": DataEntry.data["room_type"].as_string(),
    }

    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict:
        """Resolve energy factor by room_type (not by building/room names)."""
        data = payload.copy()
        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value

        room_type = data.get("room_type")
        if not room_type:
            payload["primary_factor_id"] = None
            return payload

        factor_service = FactorService(db)
        factor = await factor_service.get_by_classification(
            data_entry_type=data_entry_type_id,
            kind=room_type,
            subkind=None,
        )
        payload["primary_factor_id"] = factor.id if factor else None
        return payload

    def to_response(self, data_entry: DataEntry) -> BuildingRoomHandlerResponse:
        d = data_entry.data
        pf = d.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "room_type": pf.get("kind") or d.get("room_type"),
                "heating_kwh_per_m2": pf.get("heating_kwh_per_m2"),
                "cooling_kwh_per_m2": pf.get("cooling_kwh_per_m2"),
                "ventilation_kwh_per_m2": pf.get("ventilation_kwh_per_m2"),
                "lighting_kwh_per_m2": pf.get("lighting_kwh_per_m2"),
                "heating_kwh": d.get("heating_kwh"),
                "cooling_kwh": d.get("cooling_kwh"),
                "ventilation_kwh": d.get("ventilation_kwh"),
                "lighting_kwh": d.get("lighting_kwh"),
            }
        )

    def validate_create(self, payload: dict) -> BuildingRoomHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> BuildingRoomHandlerUpdate:
        return self.update_dto.model_validate(payload)


# ============ ENERGY COMBUSTION ================================= #


class EnergyCombustionHandlerResponse(DataEntryResponseGen):
    heating_type: str
    unit: Optional[str] = None
    quantity: float
    kg_co2eq: Optional[float] = None


class EnergyCombustionHandlerCreate(DataEntryCreate):
    heating_type: str
    quantity: float

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be > 0")
        return v


class EnergyCombustionHandlerUpdate(DataEntryUpdate):
    heating_type: Optional[str] = None
    quantity: Optional[float] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Quantity must be > 0")
        return v


class EnergyCombustionModuleHandler(BaseModuleHandler):
    """Handler for energy combustion submodule.

    Unit is derived from the factor (not user input).
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.energy_combustion

    create_dto = EnergyCombustionHandlerCreate
    update_dto = EnergyCombustionHandlerUpdate
    response_dto = EnergyCombustionHandlerResponse

    kind_field: str = "heating_type"
    subkind_field: str | None = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "heating_type": Factor.classification["kind"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "heating_type": Factor.classification["kind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> EnergyCombustionHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        factor_values = primary_factor.get("values", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "heating_type": primary_factor.get("kind")
                or data_entry.data.get("heating_type"),
                "unit": factor_values.get("unit") or data_entry.data.get("unit"),
            }
        )

    def validate_create(self, payload: dict) -> EnergyCombustionHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> EnergyCombustionHandlerUpdate:
        return self.update_dto.model_validate(payload)
