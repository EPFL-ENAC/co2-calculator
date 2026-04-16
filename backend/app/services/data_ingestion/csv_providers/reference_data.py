from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_ingestion import EntityType
from app.services.data_ingestion.base_factor_csv_provider import (
    BaseFactorCSVProvider,
)

logger = get_logger(__name__)


class ModulePerYearReferenceDataApiProvider(BaseFactorCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_context(self) -> Dict[str, Any]:
        logger.info("Setup complete for reference data factor CSV: ")

        return {}
