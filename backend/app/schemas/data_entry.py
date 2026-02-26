from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryBase, DataEntryTypeEnum
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

    if kind_changed:
        # If the kind field is being updated, we need to reset subkind and
        # primary_factor_id to ensure data integrity
        update_payload[handler_subkind_field] = None
        update_payload["primary_factor_id"] = None

    # Only resolve primary_factor_id if kind or subkind changed
    if kind_changed or subkind_changed:
        update_payload = await handler.resolve_primary_factor_id(
            update_payload, data_entry_type, db, existing_data=existing_data
        )

    return update_payload
