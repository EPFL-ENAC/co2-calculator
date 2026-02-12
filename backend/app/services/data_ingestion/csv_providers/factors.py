from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.schemas.factor import BaseFactorHandler
from app.services.data_ingestion.base_factor_csv_provider import (
    BaseFactorCSVProvider,
    _get_expected_columns_from_handlers,
    _get_required_columns_from_handler,
)

logger = get_logger(__name__)


class ModulePerYearFactorCSVProvider(BaseFactorCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_context(self) -> Dict[str, Any]:
        valid_entry_types = self._resolve_valid_entry_types()
        configured_data_entry_type_id = self.data_entry_type_id
        factor_variant = self.factor_variant

        handlers = []
        if configured_data_entry_type_id is not None:
            configured_type = DataEntryTypeEnum(int(configured_data_entry_type_id))
            handler = BaseFactorHandler.get_by_type(configured_type, factor_variant)
            handlers = [handler]
        else:
            handlers = [
                BaseFactorHandler.get_by_type(entry_type, factor_variant)
                for entry_type in valid_entry_types
            ]

        expected_columns = _get_expected_columns_from_handlers(handlers)
        required_columns: set[str] = set()
        if len(handlers) == 1:
            required_columns = _get_required_columns_from_handler(handlers[0])

        logger.info(
            "Setup complete for factor CSV: "
            f"handlers={len(handlers)}, "
            f"expected_columns={len(expected_columns)}"
        )

        return {
            "handlers": handlers,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
            "valid_entry_types": valid_entry_types,
            "factor_variant": factor_variant,
        }
