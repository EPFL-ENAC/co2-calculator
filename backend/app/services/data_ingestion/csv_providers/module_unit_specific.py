from typing import Any, Dict, List

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.schemas.data_entry import BaseModuleHandler
from app.seed.seed_helper import is_in_factors_map, load_factors_map
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
    _get_expected_columns_from_handlers,
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

        Requirements:
        - Single handler for the configured data_entry_type
        - Loads factors for that specific data_entry_type
        - Returns required_columns (strict validation)
        """
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is None:
            raise Exception(
                "data_entry_type must be specified for MODULE_UNIT_SPECIFIC"
            )

        configured_data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)

        # Load factors for this specific data entry type
        logger.info(f"Loading factors for data_entry_type={configured_data_entry_type}")
        type_factors = await load_factors_map(
            self.data_session, configured_data_entry_type
        )
        factors_map = type_factors

        # Get the single handler for this data_entry_type
        handler = BaseModuleHandler.get_by_type(configured_data_entry_type)
        handlers = [handler]

        # Get expected and required columns
        expected_columns = _get_expected_columns_from_handlers(handlers)
        required_columns = _get_required_columns_from_handler(handler)

        logger.info(
            f"Setup complete for MODULE_UNIT_SPECIFIC: "
            f"handlers={len(handlers)}, "
            f"factors={len(factors_map)}, "
            f"expected_columns={len(expected_columns)}, "
            f"required_columns={len(required_columns)}"
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
        Extract kind and subkind for MODULE_UNIT_SPECIFIC.

        Uses the single handler's kind_field and subkind_field directly.
        """
        handler = handlers[0] if handlers else None
        if not handler:
            return "", None

        kind_value = (
            filtered_row.get(handler.kind_field, "") if handler.kind_field else ""
        )
        subkind_value = (
            filtered_row.get(handler.subkind_field) if handler.subkind_field else None
        )
        return kind_value, subkind_value

    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, BaseModuleHandler | None, str | None]:
        """
        Resolve handler and validate for MODULE_UNIT_SPECIFIC.

        Logic:
        - Validate required columns are present
        - Check if kind/subkind exists in factors_map
        - Validate factor matching if handler requires it
        - Validate factor data_entry_type matches configured type
        """
        handlers = setup_result["handlers"]
        factors_map = setup_result["factors_map"]
        required_columns = setup_result["required_columns"]
        # Get and validate data_entry_type_id
        configured_data_entry_type_id = int(self.config["data_entry_type_id"])

        # Check required columns
        if required_columns and not required_columns.issubset(filtered_row.keys()):
            missing_fields = required_columns - set(filtered_row.keys())
            error_msg = f"Missing required fields {missing_fields}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = handlers[0]

        if not handler:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        # Check if kind/subkind combination exists in factors map
        kind_value = (
            filtered_row.get(handler.kind_field, "") if handler.kind_field else ""
        )
        subkind_value = (
            filtered_row.get(handler.subkind_field) if handler.subkind_field else None
        )

        match_factors = is_in_factors_map(
            kind=kind_value,
            subkind=subkind_value,
            factors_map=factors_map,
            require_subkind=handler.require_subkind_for_factor,
        )

        # Validate factor requirement
        if (
            factor is None
            and match_factors is False
            and handler.require_factor_to_match
        ):
            error_msg = (
                "Probably not part of authorized data entries. "
                "No matching factor found for kind/subkind"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        # Validate factor data_entry_type matches
        if factor and factor.data_entry_type_id != data_entry_type.value:
            error_msg = "Factor data_entry_type_id mismatch"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        return data_entry_type, handler, None
