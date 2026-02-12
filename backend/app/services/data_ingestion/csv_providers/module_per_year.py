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
            handlers = [
                BaseModuleHandler.get_by_type(entry_type)
                for entry_type in valid_entry_types
            ]

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
        # unit_id is required for MODULE_PER_YEAR to resolve carbon_report_module_id
        required_columns: set[str] = {"unit_id"}

        logger.info(
            f"Setup complete for MODULE_PER_YEAR: "
            f"handlers={len(handlers)}, "
            f"factors={len(factors_map)}, "
            f"expected_columns={len(expected_columns)}"
        )

        return {
            "handlers": handlers,
            "factors_map": factors_map,
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
        - Determine data_entry_type from factor
        - Validate factor requirement if handlers require it
        - Validate factor data_entry_type matches resolved type
        """
        handlers = setup_result["handlers"]
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        # If specific data_entry_type_id configured, use it directly
        if configured_data_entry_type_id is not None:
            data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
            handler = handlers[0]  # Should be the only handler

            if not handler:
                error_msg = "No handler available"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            # Validate factor if handler requires it
            if handler.require_factor_to_match and not factor:
                error_msg = "Missing factor for configured data_entry_type"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            # Validate factor matches if found
            if factor and factor.data_entry_type_id != data_entry_type.value:
                error_msg = "Factor data_entry_type_id mismatch"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            return data_entry_type, handler, None
        else:
            # No configured type: determine from factor
            if not factor:
                # Check if any handler requires a factor to match
                if any(h.require_factor_to_match for h in handlers):
                    error_msg = "Missing factor for MODULE_PER_YEAR"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, None, error_msg

                # If handlers don't require factor, we still can't
                # determine data_entry_type
                error_msg = "Missing factor - cannot determine data_entry_type"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            data_entry_type = DataEntryTypeEnum(factor.data_entry_type_id)
            handler = BaseModuleHandler.get_by_type(data_entry_type)

            return data_entry_type, handler, None
