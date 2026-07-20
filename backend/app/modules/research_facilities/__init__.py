"""Research facilities module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.research_facilities.data_entries import (
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesAnimalHandlerResponse,
    ResearchFacilitiesAnimalHandlerUpdate,
    ResearchFacilitiesCommonHandlerCreate,
    ResearchFacilitiesCommonHandlerResponse,
    ResearchFacilitiesCommonHandlerUpdate,
)
from app.modules.research_facilities.factors import (
    ResearchFacilitiesAnimalFactorCreate,
    ResearchFacilitiesAnimalFactorHandler,
    ResearchFacilitiesAnimalFactorResponse,
    ResearchFacilitiesAnimalFactorUpdate,
    ResearchFacilitiesCommonFactorCreate,
    ResearchFacilitiesCommonFactorHandler,
    ResearchFacilitiesCommonFactorResponse,
    ResearchFacilitiesCommonFactorUpdate,
)
from app.modules.research_facilities.handlers import (
    ResearchFacilitiesAnimalModuleHandler,
    ResearchFacilitiesCommonModuleHandler,
)

__all__ = [
    "ResearchFacilitiesAnimalHandlerCreate",
    "ResearchFacilitiesAnimalHandlerResponse",
    "ResearchFacilitiesAnimalHandlerUpdate",
    "ResearchFacilitiesCommonHandlerCreate",
    "ResearchFacilitiesCommonHandlerResponse",
    "ResearchFacilitiesCommonHandlerUpdate",
    "ResearchFacilitiesAnimalFactorCreate",
    "ResearchFacilitiesAnimalFactorHandler",
    "ResearchFacilitiesAnimalFactorResponse",
    "ResearchFacilitiesAnimalFactorUpdate",
    "ResearchFacilitiesCommonFactorCreate",
    "ResearchFacilitiesCommonFactorHandler",
    "ResearchFacilitiesCommonFactorResponse",
    "ResearchFacilitiesCommonFactorUpdate",
    "ResearchFacilitiesAnimalModuleHandler",
    "ResearchFacilitiesCommonModuleHandler",
]
