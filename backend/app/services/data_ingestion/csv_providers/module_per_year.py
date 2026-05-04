from typing import Any, Dict, List

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.seed.seed_helper import load_factors_map
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
    _get_expected_columns_from_handlers,
)

logger = get_logger(__name__)


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

        Requirements:
        - Multiple handlers for all valid data_entry_types of the module
        - Loads factors for all data_entry_types
        - No required_columns (flexible validation)
        - Uses factor lookup to determine data_entry_type per row
        """
        # Get module type from job
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

        factors_map: Dict[str, Any] = {}
        # Load handlers and factors based on configuration
        if configured_data_entry_type_id is not None:
            # Single data_entry_type specified
            configured_data_entry_type = DataEntryTypeEnum(
                configured_data_entry_type_id
            )

            # Validate it's valid for this module
            if configured_data_entry_type not in valid_entry_types:
                raise Exception(
                    f"data_entry_type {configured_data_entry_type} "
                    f"not valid for module type {module_type}"
                )

            handler = BaseModuleHandler.get_by_type(configured_data_entry_type)
            handlers = [handler]

            type_factors = await load_factors_map(
                self.data_session, configured_data_entry_type
            )
            factors_map.update(type_factors)

            logger.info(
                f"Setup for MODULE_PER_YEAR with specific data_entry_type: "
                f"{configured_data_entry_type}"
            )
        else:
            # Multiple data_entry_types - load all for this module
            # Deduplicate handlers by class type to avoid multiple identical instances
            # (e.g., EquipmentModuleHandler registered for it/scientific/other)
            handlers = []
            seen_handler_classes: set[type[Any]] = set()
            for entry_type in valid_entry_types:
                handler = BaseModuleHandler.get_by_type(entry_type)
                handler_class: type[Any] = type(handler)
                if handler_class not in seen_handler_classes:
                    handlers.append(handler)
                    seen_handler_classes.add(handler_class)

            # Load factors for all entry types
            for entry_type in valid_entry_types:
                type_factors = await load_factors_map(self.data_session, entry_type)
                factors_map.update(type_factors)

            logger.info(
                f"Setup for MODULE_PER_YEAR with multiple data_entry_types: "
                f"{valid_entry_types}"
            )

        # Get expected and required columns
        expected_columns = _get_expected_columns_from_handlers(handlers)
        # unit_institutional_id required for MODULE_PER_YEAR
        required_columns: set[str] = {"unit_institutional_id"}

        # Create factor_id_to_factor mapping for O(1) lookup during row processing
        # This avoids O(n) loop through factors_map for each row
        factor_id_to_factor: Dict[int, Any] = {}
        for factor in factors_map.values():
            factor_id = getattr(factor, "id", None)
            if factor_id is not None:
                factor_id_to_factor[factor_id] = factor

        logger.info(
            f"Setup complete for MODULE_PER_YEAR: "
            f"handlers={len(handlers)}, "
            f"factors={len(factors_map)}, "
            f"factor_id_to_factor={len(factor_id_to_factor)}, "
            f"expected_columns={len(expected_columns)}"
        )

        return {
            "handlers": handlers,
            "factors_map": factors_map,
            "factor_id_to_factor": factor_id_to_factor,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
        }

    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """
        Extract kind and subkind for MODULE_PER_YEAR.

        Tries to find kind/subkind across all handlers:
        1. Check each handler's kind_field/subkind_field
        2. Fallback to common field names
        3. Return empty if nothing found
        """
        # Try to find kind/subkind using each handler's fields
        for handler in handlers:
            if handler.kind_field and handler.kind_field in filtered_row:
                kind_value = filtered_row.get(handler.kind_field, "")
                subkind_value = (
                    filtered_row.get(handler.subkind_field)
                    if handler.subkind_field
                    else None
                )
                return kind_value, subkind_value

        # Fallback: try common field names
        for handler in handlers:
            subkind_value = None
            # Check if this handler has subkind_field and it exists in row
            if handler.subkind_field and handler.subkind_field in filtered_row:
                subkind_value = filtered_row.get(handler.subkind_field)

            # Try common kind field names
            for kind_field_name in ("kind", "Kind", "KIND"):
                if kind_field_name in filtered_row:
                    kind_value = filtered_row.get(kind_field_name, "")
                    return kind_value, subkind_value

        # Last resort: return empty if nothing found
        return "", None

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
        - Use configured data_entry_type_id if present
        - Otherwise, resolve from handler's category_field (e.g., equipment_category)
        - Otherwise, determine from factor
        - Validate factor requirement if handlers require it
        - Validate factor data_entry_type matches resolved type
        """
        handlers = setup_result["handlers"]
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        # Determine data_entry_type
        data_entry_type: DataEntryTypeEnum | None = None
        handler: ModuleHandler | None = None

        if configured_data_entry_type_id is not None:
            # Priority 1: Configured type from job config
            data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
            handler = handlers[0] if handlers else None
        else:
            # Priority 2: Resolve from handler's category_field
            handler = handlers[0] if len(handlers) == 1 else None
            if handler:
                data_entry_type = self._resolve_data_entry_type_from_category(
                    filtered_row, handler, row_idx, stats, max_row_errors
                )

            # Priority 3: Determine from factors_map using new helper function
            if data_entry_type is None:
                # Get module type to determine valid entry types
                if self.job is None or self.job.module_type_id is None:
                    error_msg = "module_type_id must be set for MODULE_PER_YEAR"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, None, error_msg

                module_type = ModuleTypeEnum(self.job.module_type_id)
                valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

                # Use factors_map already loaded in setup_result
                # (NOT per-row DB queries)
                # Build factors_maps_by_type from existing setup_result["factors_map"]
                # Assuming setup_result["factors_map"] is your large dictionary
                original_map = setup_result["factors_map"]

                factors_maps_by_type: Dict[DataEntryTypeEnum, Dict[str, Any]] = {}

                for entry_type in valid_entry_types:
                    # Convert enum value to string (e.g., "10") to match the key prefix
                    prefix = f"{entry_type.value}:"

                    # Filter the original map for keys that start with this prefix
                    factors_maps_by_type[entry_type] = {
                        key: factor
                        for key, factor in original_map.items()
                        if key.startswith(prefix)
                    }
                # Extract kind/subkind from row
                kind_value, subkind_value = self._extract_kind_subkind_values(
                    filtered_row, handlers
                )

                # Use new helper to infer data_entry_type from kind/subkind
                from app.seed.seed_helper import lookup_data_entry_type_by_kind

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

        # Validate we resolved a type and handler
        if data_entry_type is None:
            error_msg = (
                "Missing data_entry_type_id in job config, category field, or factor"
                " and no matching factor found in factors map"
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

        # Note: Factor validation is now handled by ModuleHandlerService
        # when it queries the database in _process_row

        return data_entry_type, handler, None
