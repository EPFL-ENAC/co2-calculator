from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionComputation
from app.models.module_type import ModuleTypeEnum

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
    def validate_create(self, payload: dict) -> DataEntryCreate: ...
    def validate_update(self, payload: dict) -> DataEntryUpdate: ...
    async def pre_compute(
        self,
        data_entry: Any,
        session: AsyncSession,
    ) -> dict: ...
    def resolve_computations(
        self,
        data_entry: Any,
        emission_type: Any,
        ctx: dict,
    ) -> list[EmissionComputation]: ...


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

    async def pre_compute(
        self,
        data_entry: Any,
        session: AsyncSession,
    ) -> dict:
        """Pre-computation hook called before factor retrieval.

        Override in subclasses to enrich the context dict with values that
        require DB access or non-trivial arithmetic (e.g. distance_km for
        plane travel, annual_kwh for equipment).

        The returned dict is merged into the context that is passed to both
        ``resolve_computations`` and ``_apply_formula``.

        Args:
            data_entry: Fully hydrated DataEntry or DataEntryResponse.
            session: Async DB session.

        Returns:
            Dict of additional context keys (empty by default).
        """
        return {}

    def resolve_computations(
        self,
        data_entry: Any,
        emission_type: Any,
        ctx: dict,
    ) -> list:
        """Resolve emission computations for a given emission type.

        Override in subclasses to return one ``EmissionComputation`` per factor
        that must be applied for this emission type.

        The default implementation looks for a ``primary_factor_id`` in *ctx*
        (Strategy A).  Handlers that use classification queries (Strategy B)
        must override this method.

        Args:
            data_entry: The data entry being processed.
            emission_type: The ``EmissionType`` leaf being computed.
            ctx: Merged dict of ``data_entry.data`` + ``pre_compute()`` output.

        Returns:
            List of ``EmissionComputation`` objects (may be empty).
        """

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
            )
        ]

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
