from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.seed.seed_helper import lookup_data_entry_type_by_kind
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
)

logger = get_logger(__name__)


# Module types whose CSV ingest INFERS the per-row ``data_entry_type_id``
# from a matched Factor (the row carries a kind/sub-kind, not a DET name,
# so the resolver looks up the factor table to disambiguate which DET
# the row belongs to).  An empty factors_map for these modules means
# every row's resolution will fail with "no matching factor found in
# factors map" — the operator gains nothing from grinding through
# 50 000 rows of the same error; refuse the ingest up front.
#
# Other modules (e.g. ``buildings``, ``professional_travel``,
# ``headcount``) carry the DET in a category column that maps directly
# to ``DataEntryTypeEnum`` names, so an empty factors_map is a
# legitimate state (they ingest rows with ``primary_factor_id=None``).
_FACTOR_INFERRED_MODULES: set[ModuleTypeEnum] = {
    ModuleTypeEnum.equipment_electric_consumption,
    ModuleTypeEnum.purchase,
}


class ModulePerYearCSVProvider(BaseCSVProvider):
    """
    CSV provider for MODULE_PER_YEAR entity type.

    Handles module-level data like travel or headcount per year.
    Determines data_entry_type from the factor (kind/subkind) found in the row.
    """

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """
        Setup handlers and factors for MODULE_PER_YEAR.

        Loads handlers/factors for all valid data_entry_types of the
        module (or just the configured one), then assembles the shared
        setup dict. unit_institutional_id is the only required column —
        per-row type resolution is flexible (config, category column, or
        factor inference).
        """
        if self.job is None or self.job.module_type_id is None:
            raise Exception(
                "module_type_id must be set for MODULE_PER_YEAR entity type"
            )

        module_type = ModuleTypeEnum(self.job.module_type_id)
        valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

        if not valid_entry_types:
            raise Exception(
                f"No data entry types defined for module type: {module_type}"
            )

        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is not None:
            configured_data_entry_type = DataEntryTypeEnum(
                int(configured_data_entry_type_id)
            )
            if configured_data_entry_type not in valid_entry_types:
                raise Exception(
                    f"data_entry_type {configured_data_entry_type} "
                    f"not valid for module type {module_type}"
                )
            entry_types = [configured_data_entry_type]
        else:
            entry_types = list(valid_entry_types)

        handlers, factors_map = await self._load_handlers_and_factors(entry_types)

        # Fail fast for "common" uploads — modules that infer the per-row
        # data_entry_type_id by looking up the row's kind/sub-kind in the
        # factors map (equipment, purchase).  An empty factors_map
        # guarantees every row will fail with "no matching factor found";
        # surfacing that as one terminal error beats 50 000 row-level
        # errors that all point at the same missing-factors fix.  Other
        # modules (whose category column maps directly to DET names) are
        # legitimately allowed an empty map and are covered by the
        # narrower ``_guard_factors_required`` check in
        # ``_assemble_setup_result``.
        if module_type in _FACTOR_INFERRED_MODULES and not factors_map:
            year_str = (
                f"year={self.year}" if self.year is not None else "the configured year"
            )
            raise ValueError(
                f"No factors available for module={module_type.name} {year_str}. "
                "This module infers the per-row data_entry_type from a matched "
                "Factor, so an empty factors table guarantees every row will "
                "fail. Upload factors for this module/year before ingesting data."
            )

        # unit_institutional_id required for MODULE_PER_YEAR
        return self._assemble_setup_result(
            handlers=handlers,
            factors_map=factors_map,
            module_label=module_type.name,
            required_columns={"unit_institutional_id"},
        )

    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None", str | None]:
        """
        Resolve handler and validate for MODULE_PER_YEAR.

        Logic:
        - Priority 1/2 (configured data_entry_type_id, then the handler's
          category column) via the shared base resolver
        - Priority 3: infer the type from the factors map (kind/subkind)
        - Note: factor validation is handled by ModuleHandlerService
          when it queries the database in _process_row
        """
        handlers = setup_result["handlers"]

        data_entry_type, handler = self._resolve_type_from_config_or_category(
            filtered_row, handlers, row_idx, stats, max_row_errors
        )

        if data_entry_type is None:
            # Priority 3: infer from the factors map already loaded at
            # setup (NOT per-row DB queries)
            if self.job is None or self.job.module_type_id is None:
                error_msg = "module_type_id must be set for MODULE_PER_YEAR"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            module_type = ModuleTypeEnum(self.job.module_type_id)
            valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

            original_map = setup_result["factors_map"]
            factors_maps_by_type: Dict[DataEntryTypeEnum, Dict[str, Any]] = {}
            for entry_type in valid_entry_types:
                # Factor-map keys are prefixed "{type_value}:" — split the
                # merged map back per type for the lookup helper
                prefix = f"{entry_type.value}:"
                factors_maps_by_type[entry_type] = {
                    key: factor
                    for key, factor in original_map.items()
                    if key.startswith(prefix)
                }

            kind_value, subkind_value = self._extract_kind_subkind_values(
                filtered_row, handlers
            )

            data_entry_type = lookup_data_entry_type_by_kind(
                kind=kind_value,
                subkind=subkind_value,
                factors_maps_by_type=factors_maps_by_type,
            )

            if data_entry_type is None:
                error_msg = (
                    "Missing data_entry_type_id in job config, category field,"
                    " or factor and no matching factor found in factors map"
                    f" (kind={kind_value}, subkind={subkind_value})"
                )
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

        if handler is None:
            handler = BaseModuleHandler.get_by_type(data_entry_type)

        if not handler:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        return data_entry_type, handler, None
