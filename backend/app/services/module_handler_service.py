"""Service for factor-dependent handler operations.

Owns all DB-dependent logic that was previously on BaseModuleHandler,
breaking the circular dependency between schemas and services.
"""

from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.factor_taxonomy_cache import taxonomy_cache
from app.models.data_entry import DataEntryTypeEnum
from app.schemas.taxonomy import TaxonomyNode
from app.services.factor_service import FactorService

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler


class ModuleHandlerService:
    """Orchestrates factor-dependent operations for module handlers."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.factor_service = FactorService(session)

    @staticmethod
    def clear_dependent_fields_on_kind_change(
        handler: ModuleHandler,
        update_payload: dict,
        item_data: dict,
        existing_data: dict | None,
    ) -> dict:
        """Clear classification fields that depended on the old kind.

        Pure payload normalization — no factor resolution happens on the
        update path any more (emission compute resolves on its own; factor
        defaults are derived at compute/display time). When the kind
        changes, the stored subkind and override code belonged to the old
        kind and are cleared unless the request supplies new ones.
        """
        kind_field = handler.kind_field or ""
        if existing_data is None or kind_field not in item_data:
            return update_payload
        if item_data[kind_field] == existing_data.get(kind_field):
            return update_payload

        subkind_field = handler.subkind_field or ""
        if subkind_field and subkind_field not in item_data:
            update_payload[subkind_field] = None
        override_field = getattr(handler, "kind_field_override", None) or ""
        if override_field and override_field not in item_data:
            update_payload[override_field] = None
        return update_payload

    async def get_taxonomy(
        self,
        handler: ModuleHandler,
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
        # Cache key omits `handler` on purpose: both call sites (taxonomies.py)
        # derive it as `BaseModuleHandler.get_by_type(data_entry_type)`, so it's
        # a pure function of `data_entry_type` and never varies independently —
        # if a future caller passes a different handler for the same
        # (data_entry_type, year), the key must include it too.
        cache_key = (data_entry_type, year)
        cached = taxonomy_cache.get(cache_key)
        if cached is not None:
            return cached

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

        # Return root node with children grouped by kind and subkind.
        # Callers (see taxonomies.py) only ever wrap this node as a `children`
        # entry of a parent — they never mutate it — so sharing the cached
        # instance across requests is safe.
        node = TaxonomyNode(
            name=data_entry_type.name,
            label=handler.to_label(data_entry_type.name),
            children=children,
        )
        taxonomy_cache.set(cache_key, node)
        return node
