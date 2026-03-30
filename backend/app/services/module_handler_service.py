"""Service for factor-dependent handler operations.

Owns all DB-dependent logic that was previously on BaseModuleHandler,
breaking the circular dependency between schemas and services.
"""

from typing import TYPE_CHECKING, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.taxonomy import TaxonomyNode
from app.services.factor_service import FactorService

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler

logger = get_logger(__name__)


class ModuleHandlerService:
    """Orchestrates factor-dependent operations for module handlers."""

    def __init__(self, session: AsyncSession):
        self.factor_service = FactorService(session)

    async def resolve_primary_factor_id(
        self,
        handler: "ModuleHandler",
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        existing_data: Optional[dict] = None,
    ) -> dict:
        """Resolve and set primary_factor_id on the payload.

        Looks up the factor by classification using the handler's
        kind_field and optional subkind_field.

        Args:
            handler: The module handler for this data entry type
            payload: The data payload to enrich
            data_entry_type_id: The data entry type enum
            existing_data: Existing data entry data for merging on updates
        """
        if handler.kind_field is None:
            return payload

        data = payload.copy()
        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value

        kind = data.get(handler.kind_field, "")
        subkind = data.get(handler.subkind_field, "") if handler.subkind_field else None

        factor = await self.factor_service.get_by_classification(
            data_entry_type=data_entry_type_id,
            kind=kind,
            subkind=subkind if subkind else None,
        )
        payload["primary_factor_id"] = factor.id if factor else None
        return payload

    async def resolve_primary_factor_if_changed(
        self,
        handler: "ModuleHandler",
        update_payload: dict,
        data_entry_type: DataEntryTypeEnum,
        item_data: dict,
        existing_data: dict | None,
    ) -> dict:
        """Resolve primary_factor_id when classification fields change.

        Args:
            handler: The module handler for this data entry type
            update_payload: The payload to update
            data_entry_type: The data entry type enum
            item_data: The incoming item data from the request
            existing_data: The existing data entry data
        """
        handler_kind_field = handler.kind_field or ""
        handler_subkind_field = handler.subkind_field or ""

        if existing_data is None:
            return await self.resolve_primary_factor_id(
                handler, update_payload, data_entry_type, existing_data=None
            )

        kind_changed = (handler_kind_field in item_data) and (
            item_data[handler_kind_field] != existing_data.get(handler_kind_field)
        )
        subkind_changed = (handler_subkind_field in item_data) and (
            item_data[handler_subkind_field] != existing_data.get(handler_subkind_field)
        )

        if kind_changed:
            update_payload[handler_subkind_field] = None
            update_payload["primary_factor_id"] = None

        if kind_changed or subkind_changed:
            update_payload = await self.resolve_primary_factor_id(
                handler,
                update_payload,
                data_entry_type,
                existing_data=existing_data,
            )

        return update_payload

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
