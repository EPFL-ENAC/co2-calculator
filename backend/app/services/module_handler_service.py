"""Service for factor-dependent handler operations.

Owns all DB-dependent logic that was previously on BaseModuleHandler,
breaking the circular dependency between schemas and services.
"""

from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.factor_taxonomy_cache import (
    TaxonomyCacheEntry,
    compute_taxonomy_etag,
    taxonomy_cache,
)
from app.models.classification_translation import (
    DEFAULT_LANG,
    normalize_lang,
)
from app.models.data_entry import DataEntryTypeEnum
from app.repositories.classification_translation_repo import (
    ClassificationTranslationRepository,
)
from app.repositories.factor_repo import FactorRepository
from app.schemas.taxonomy import FactorOption, TaxonomyNode
from app.services.factor_service import FactorService

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler


def _display_meta(handler: ModuleHandler, factor) -> dict | None:
    """Whitelisted display metadata for the node this factor row builds.

    Only the fields the handler declares in ``taxonomy_meta_fields`` travel —
    a factor's other values are emission coefficients and stay server-side
    (#2396). ``None`` when the handler declares none, so
    ``response_model_exclude_none`` keeps unaffected payloads unchanged.
    """
    fields = handler.taxonomy_meta_fields
    if not fields:
        return None
    source = {**(factor.classification or {}), **(factor.values or {})}
    meta = {field: source[field] for field in fields if field in source}
    return meta or None


class ModuleHandlerService:
    """Orchestrates factor-dependent operations for module handlers."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.factor_service = FactorService(session)
        self.translation_repo = ClassificationTranslationRepository(session)

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
        for field in getattr(handler, "kind_dependent_fields", ()):
            if field not in item_data:
                update_payload[field] = None
        return update_payload

    async def search_factor_options(
        self,
        handler: ModuleHandler,
        data_entry_type: DataEntryTypeEnum,
        year: int,
        query: str,
        lang: str,
        limit: int,
    ) -> list[FactorOption]:
        """Server-side typeahead over one det's classification values
        (#2391 decision 4).

        Matches the stored value, the English text, and its translated
        label; each option's label resolves like the taxonomy builder does
        (translated -> English text -> bare value). Deliberately uncached:
        the endpoint exists so clients stop downloading a whole tree.
        """
        kind_field = handler.kind_field
        if kind_field is None:
            raise ValueError(
                f"{data_entry_type} has no searchable classification field"
            )
        lang = normalize_lang(lang)
        rows = await FactorRepository(self.session).search_classification_options(
            data_entry_type,
            year,
            kind_field,
            handler.kind_label_field,
            query,
            lang,
            limit,
        )
        translations: dict[str, str] = {}
        if lang != DEFAULT_LANG:
            texts = [text for _, text in rows if text]
            translations = await self.translation_repo.get_labels_for_values(
                handler.kind_label_field or kind_field, texts, lang
            )
        options: list[FactorOption] = []
        seen: set[str] = set()
        for value, english_text in rows:
            # The same value can sit on several factor rows (purchase keeps
            # one row per additional code) — first hit wins, order is the
            # repo's relevance order.
            if value in seen:
                continue
            seen.add(value)
            english = english_text if english_text else value
            options.append(
                FactorOption(name=value, label=translations.get(english, english))
            )
        return options

    async def get_taxonomy(
        self,
        handler: ModuleHandler,
        data_entry_type: DataEntryTypeEnum,
        year: int,
        lang: str = DEFAULT_LANG,
    ) -> TaxonomyNode:
        """Build taxonomy tree from factors for the given handler.

        Thin wrapper around ``get_taxonomy_with_etag`` for the many callers
        that only need the tree, not its cache entry's ETag (#2391
        decision 2).
        """
        entry = await self.get_taxonomy_with_etag(handler, data_entry_type, year, lang)
        return entry.tree

    async def get_taxonomy_with_etag(
        self,
        handler: ModuleHandler,
        data_entry_type: DataEntryTypeEnum,
        year: int,
        lang: str = DEFAULT_LANG,
    ) -> TaxonomyCacheEntry:
        """Build (or fetch cached) the taxonomy tree and its ETag.

        Builds a two-level taxonomy based on the handler's kind and
        subkind fields by querying factors from the database. The ETag is
        computed once here, at build time, and cached alongside the tree
        (#2391 decision 2) so every pod serving this entry from cache
        reuses it instead of recomputing per request.

        Args:
            handler: The module handler providing field config
            data_entry_type: The data entry type to build taxonomy for
            year: The year for which to retrieve factors
            lang: Request locale (``"fr-CH"``, ``"fr"``, ...). Normalized to
                a short code; anything not in ``TRANSLATABLE_LANGS`` falls
                back to English (#2401).
        """
        lang = normalize_lang(lang)
        # Cache key omits `handler` on purpose: both call sites (taxonomies.py)
        # derive it as `BaseModuleHandler.get_by_type(data_entry_type)`, so it's
        # a pure function of `data_entry_type` and never varies independently —
        # if a future caller passes a different handler for the same
        # (data_entry_type, year), the key must include it too. `lang` is
        # part of the key because the built labels differ by language;
        # `taxonomy_cache.clear()` (write-time invalidation) drops the whole
        # cache regardless of key shape, so adding this dimension is safe.
        cache_key = (data_entry_type, year, lang)
        cached = taxonomy_cache.get(cache_key)
        if cached is not None:
            return cached

        factors = await self.factor_service.list_by_data_entry_type(
            data_entry_type, year
        )
        # English is the classification value itself (`to_label` below) —
        # no DB round trip needed. One query for every other language, never
        # per node (#2401). Covers both shapes a handler can take: a
        # self-labeling field (equipment's `equipment_class`, its own value
        # is the English label) keys on `kind_field`/`subkind_field`; a
        # code + separate description field (purchase's
        # `purchase_institutional_code` + `kind_label_field ==
        # "purchase_institutional_description"`) keys on the label field
        # instead, since that's where the human-readable text — and its
        # `_fr` counterpart — actually live.
        translations: dict[tuple[str, str], str] = {}
        if lang != DEFAULT_LANG:
            field_names = {
                f
                for f in (
                    handler.kind_field,
                    handler.subkind_field,
                    handler.kind_label_field,
                    handler.subkind_label_field,
                )
                if f is not None
            }
            translations = await self.translation_repo.get_labels(field_names, lang)
        children: list[TaxonomyNode] = []

        for factor in factors:
            classification = factor.classification or {}

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
                    # The label field can be present but blank (real purchase
                    # codes ship without a description) — the code is then the
                    # only text there is.
                    english_label = classification.get(handler.kind_label_field)
                    if english_label is None or english_label == "":
                        english_label = kind_value
                    label = translations.get(
                        (handler.kind_label_field, english_label), english_label
                    )
                else:
                    label = translations.get(
                        (kind_field, kind_value), handler.to_label(kind_value)
                    )
                kind_node = TaxonomyNode(
                    name=kind_value,
                    label=label,
                    translation_key=kind_value,
                    meta=_display_meta(handler, factor),
                )
                children.append(kind_node)

            # Lookup subkind
            subkind_field = handler.subkind_field
            if subkind_field not in classification:
                if "subkind" in classification:
                    subkind_field = "subkind"
                else:
                    continue  # if no subkind field defined, skip adding subkind nodes
            subkind_value = classification.get(subkind_field, "")
            if subkind_value is None or subkind_value == "":
                continue  # skip if no subkind in classification
            # Build subkind node as a child of kind node
            if kind_node.children is None:
                kind_node.children = []
            if (
                handler.subkind_label_field
                and handler.subkind_label_field in classification
            ):
                # Same blank-label fallback as the kind branch above.
                english_subkind_label = classification.get(handler.subkind_label_field)
                if english_subkind_label is None or english_subkind_label == "":
                    english_subkind_label = subkind_value
                subkind_label = translations.get(
                    (handler.subkind_label_field, english_subkind_label),
                    english_subkind_label,
                )
            else:
                subkind_label = translations.get(
                    (subkind_field, subkind_value),
                    handler.to_label(subkind_value),
                )
            kind_node.children.append(
                TaxonomyNode(
                    name=subkind_value,
                    label=subkind_label,
                    translation_key=subkind_value,
                    # Per-row, not per-kind: an animal facility carries one
                    # metric unit per housing type, so the subkind node must
                    # take its own factor's meta rather than the kind's.
                    meta=_display_meta(handler, factor),
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
        entry = TaxonomyCacheEntry(tree=node, etag=compute_taxonomy_etag(node))
        taxonomy_cache.set(cache_key, entry)
        return entry
