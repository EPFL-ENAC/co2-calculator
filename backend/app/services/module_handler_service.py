"""Service for factor-dependent handler operations.

Owns all DB-dependent logic that was previously on BaseModuleHandler,
breaking the circular dependency between schemas and services.
"""

from typing import TYPE_CHECKING, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.models.taxonomy import TaxonomyNode
from app.services.factor_resolver import FactorResolver
from app.services.factor_service import FactorService

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler

logger = get_logger(__name__)


class ModuleHandlerService:
    """Orchestrates factor-dependent operations for module handlers."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.factor_service = FactorService(session)
        self.factor_resolver = FactorResolver(session)

    async def resolve_factor(
        self,
        handler: "ModuleHandler",
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
        existing_data: Optional[dict] = None,
    ) -> Optional[Factor]:
        """Resolve the Factor matching the payload's classification fields.

        Looks up the factor via ``FactorResolver`` using the handler's
        kind_field / subkind_field (or kind_field_override) rules. The
        payload itself is never mutated: existing_data is merged into a
        copy so partial updates still resolve against the full persisted
        classification.

        Args:
            handler: The module handler for this data entry type
            payload: The data payload to resolve against
            data_entry_type_id: The data entry type enum
            year: Carbon-report year. Required — without it the factor lookup
                  spans all years and raises MultipleResultsFound when the same
                  classification exists in more than one year.
            existing_data: Existing data entry data for merging on updates
        """
        data = payload.copy()
        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value

        return await self.factor_resolver.resolve(
            handler, data, data_entry_type_id, year
        )

    async def populate_defaults(
        self,
        handler: "ModuleHandler",
        data: dict,
        factor: Factor,
    ) -> dict:
        if (
            factor
            and hasattr(handler, "factor_value_fields")
            and handler.factor_value_fields
        ):
            for field_name in handler.factor_value_fields:
                if field_name not in data or data[field_name] in (None, "", 0):
                    default_value = factor.values.get(field_name)
                    if default_value is not None:
                        data[field_name] = default_value
                        logger.debug(
                            f"{field_name}={default_value} from factor populated"
                        )

        return data

    async def resolve_factor_if_changed(
        self,
        handler: "ModuleHandler",
        update_payload: dict,
        data_entry_type: DataEntryTypeEnum,
        item_data: dict,
        existing_data: dict | None,
        year: int,
    ) -> tuple[dict, Optional[Factor]]:
        """Resolve the matching Factor when classification fields change.

        Args:
            handler: The module handler for this data entry type
            update_payload: The payload to update
            data_entry_type: The data entry type enum
            item_data: The incoming item data from the request
            existing_data: The existing data entry data
            year: Carbon-report year passed through to resolve_factor.
        """
        handler_kind_field = handler.kind_field or ""
        handler_subkind_field = handler.subkind_field or ""
        if existing_data is None:
            factor = await self.resolve_factor(
                handler, update_payload, data_entry_type, existing_data=None, year=year
            )
            return update_payload, factor

        kind_changed = (handler_kind_field in item_data) and (
            item_data[handler_kind_field] != existing_data.get(handler_kind_field)
        )
        subkind_changed = (handler_subkind_field in item_data) and (
            item_data[handler_subkind_field] != existing_data.get(handler_subkind_field)
        )
        override_field = getattr(handler, "kind_field_override", None) or ""
        override_changed = (override_field in item_data) and (
            item_data[override_field] != existing_data.get(override_field)
        )

        if kind_changed:
            if handler_subkind_field:
                update_payload[handler_subkind_field] = None
            # The stored override code belonged to the old kind; unless the
            # request supplies a new one, clear it so resolution follows the
            # new kind instead of the stale, more-specific code.
            if override_field and override_field not in item_data:
                update_payload[override_field] = None

        factor = None
        if kind_changed or subkind_changed or override_changed:
            factor = await self.resolve_factor(
                handler,
                update_payload,
                data_entry_type,
                existing_data=existing_data,
                year=year,
            )
            # kind_changed or subkind_changed for some module handlers we need default
            # it's done already in the base_csv_provider do the same here
            if factor is not None:
                update_payload = await self.populate_defaults(
                    handler, update_payload, factor
                )

        return update_payload, factor

    async def get_taxonomy(
        self,
        handler: "ModuleHandler",
        data_entry_type: DataEntryTypeEnum,
        year: int,
    ) -> TaxonomyNode:
        """Build taxonomy tree from factors for the given handler.

        Builds a two-level taxonomy based on the handler's kind and
        subkind fields by querying factors from the database.

        Args:
            handler: The module handler providing field config
            data_entry_type: The data entry type to build taxonomy for
            year: The year for which to retrieve factors
        """

        factors = await self.factor_service.list_by_data_entry_type(
            data_entry_type, year
        )
        children: list[TaxonomyNode] = []

        for factor in factors:
            classification = factor.classification or {}
            values = factor.values or {}

            # Lookup kind
            kind_field = handler.kind_field
            if kind_field not in classification:
                if "kind" in classification:
                    kind_field = "kind"
                else:
                    # if no kind/subkind fields defined, skip adding nodes
                    continue
            kind_value = classification.get(kind_field, "")
            if kind_value is None or kind_value == "":
                continue  # skip if no kind in classification
            # find the children based on kind or add it
            kind_node = next((c for c in children if c.name == kind_value), None)
            if not kind_node:
                if (
                    handler.kind_label_field
                    and handler.kind_label_field in classification
                ):
                    label = classification.get(handler.kind_label_field, kind_value)
                else:
                    label = handler.to_label(kind_value)
                kind_node = TaxonomyNode(
                    name=kind_value,
                    label=label,
                    translation_key=values.get("translation_key") or kind_value,
                )
                children.append(kind_node)

            # Lookup subkind
            subkind_field = handler.subkind_field
            if subkind_field not in classification:
                if "subkind" in classification:
                    subkind_field = "subkind"
                else:
                    # if no subkind field defined,
                    # add classification and values to kind node
                    kind_node.classification = classification
                    kind_node.values = values
                    continue  # if no subkind field defined, skip adding subkind nodes
            subkind_value = classification.get(subkind_field, "")
            if subkind_value is None or subkind_value == "":
                # if no subkind field defined, add classification
                # and values to kind node
                kind_node.classification = classification
                kind_node.values = values
                continue  # skip if no subkind in classification
            # Build subkind node as a child of kind node
            if kind_node.children is None:
                kind_node.children = []
            if (
                handler.subkind_label_field
                and handler.subkind_label_field in classification
            ):
                subkind_label = classification.get(
                    handler.subkind_label_field, subkind_value
                )
            else:
                subkind_label = handler.to_label(subkind_value)
            kind_node.children.append(
                TaxonomyNode(
                    name=subkind_value,
                    label=subkind_label,
                    translation_key=values.get("translation_key") or subkind_value,
                    classification=classification,
                    values=values,
                )
            )

        # Return root node with children grouped by kind and subkind
        return TaxonomyNode(
            name=data_entry_type.name,
            label=handler.to_label(data_entry_type.name),
            children=children,
        )
