
from app.core.logging import get_logger
from app.models.data_ingestion import EntityType
from app.schemas.year_configuration import (
    BaseReductionObjectiveHandler,
    ReductionObjectiveType,
)
from app.services.data_ingestion.base_reduction_objective_csv_provider import (
    BaseReductionObjectiveCSVProvider,
)

logger = get_logger(__name__)


class ModulePerYearReductionObjectivesApiProvider(BaseReductionObjectiveCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    def _resolve_handler(self) -> BaseReductionObjectiveHandler:
        type_id = self.config.get("reduction_objective_type_id")
        if type_id is None:
            raise ValueError("reduction_objective_type_id is required in config")
        return BaseReductionObjectiveHandler.get_by_type(
            ReductionObjectiveType(int(type_id))
        )
