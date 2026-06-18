from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.schemas.data_entry import ModuleHandler
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
    _get_required_columns_from_handler,
)

logger = get_logger(__name__)


class ModuleUnitSpecificCSVProvider(BaseCSVProvider):
    """
    CSV provider for MODULE_UNIT_SPECIFIC entity type.

    Handles unit-specific data like equipment per carbon report module.
    Requires a single data_entry_type and associated carbon_report_module_id.
    """

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """
        Setup handlers and factors for MODULE_UNIT_SPECIFIC.

        Single handler for the configured data_entry_type, with strict
        required-column validation derived from the handler's DTO.
        """
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is None:
            raise Exception(
                "data_entry_type must be specified for MODULE_UNIT_SPECIFIC"
            )

        configured_data_entry_type = DataEntryTypeEnum(
            int(configured_data_entry_type_id)
        )

        handlers, factors_map = await self._load_handlers_and_factors(
            [configured_data_entry_type]
        )

        return self._assemble_setup_result(
            handlers=handlers,
            factors_map=factors_map,
            module_label=configured_data_entry_type.name,
            required_columns=_get_required_columns_from_handler(handlers[0]),
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
        Resolve handler and validate for MODULE_UNIT_SPECIFIC.

        Logic:
        - Priority 1/2 (configured data_entry_type_id, then the handler's
          category column) via the shared base resolver — no factor-based
          inference for this entity type
        - Validate required columns are present (strict)
        - Note: factor validation is handled by ModuleHandlerService
          when it queries the database in _process_row
        """
        handlers = setup_result["handlers"]
        required_columns = setup_result["required_columns"]

        data_entry_type, handler = self._resolve_type_from_config_or_category(
            filtered_row, handlers, row_idx, stats, max_row_errors
        )

        if data_entry_type is None:
            error_msg = (
                "Missing data_entry_type_id in job config or category field in CSV"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        if handler is None:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        if required_columns and not required_columns.issubset(filtered_row.keys()):
            missing_fields = required_columns - set(filtered_row.keys())
            error_msg = f"Missing required fields {missing_fields}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        return data_entry_type, handler, None
