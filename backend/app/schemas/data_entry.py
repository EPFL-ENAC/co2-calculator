import json
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

import yaml
from pydantic import BaseModel, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryBase, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionComputation
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
