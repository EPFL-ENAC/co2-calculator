"""CSV data ingestion providers for different entity types."""

from app.services.data_ingestion.csv_providers.factors import (
    ModulePerYearFactorCSVProvider,
)
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
)
from app.services.data_ingestion.csv_providers.module_unit_specific import (
    ModuleUnitSpecificCSVProvider,
)
from app.services.data_ingestion.csv_providers.reduction_objectives import (
    ModulePerYearReductionObjectivesApiProvider,
)
from app.services.data_ingestion.csv_providers.reference_data import (
    ModulePerYearReferenceDataApiProvider,
)

__all__ = [
    "ModuleUnitSpecificCSVProvider",
    "ModulePerYearCSVProvider",
    "ModulePerYearFactorCSVProvider",
    "ModulePerYearReductionObjectivesApiProvider",
    "ModulePerYearReferenceDataApiProvider",
]
