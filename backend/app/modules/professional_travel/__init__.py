"""Professional travel module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.professional_travel.data_entries import (
    DepartureDateMixin,
    PlaneCabinClassValidationMixin,
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelPlaneHandlerResponse,
    ProfessionalTravelPlaneHandlerUpdate,
    ProfessionalTravelTrainHandlerCreate,
    ProfessionalTravelTrainHandlerResponse,
    ProfessionalTravelTrainHandlerUpdate,
    TrainCabinClassValidationMixin,
)
from app.modules.professional_travel.factors import (
    TravelPlaneFactorCreate,
    TravelPlaneFactorHandler,
    TravelPlaneFactorResponse,
    TravelPlaneFactorUpdate,
    TravelTrainFactorCreate,
    TravelTrainFactorHandler,
    TravelTrainFactorResponse,
    TravelTrainFactorUpdate,
)
from app.modules.professional_travel.handlers import (
    MemberEntry,
    ProfessionalTravelBaseModuleHandler,
    ProfessionalTravelPlaneModuleHandler,
    ProfessionalTravelTrainModuleHandler,
)

__all__ = [
    "DepartureDateMixin",
    "PlaneCabinClassValidationMixin",
    "ProfessionalTravelPlaneHandlerCreate",
    "ProfessionalTravelPlaneHandlerResponse",
    "ProfessionalTravelPlaneHandlerUpdate",
    "ProfessionalTravelTrainHandlerCreate",
    "ProfessionalTravelTrainHandlerResponse",
    "ProfessionalTravelTrainHandlerUpdate",
    "TrainCabinClassValidationMixin",
    "TravelPlaneFactorCreate",
    "TravelPlaneFactorHandler",
    "TravelPlaneFactorResponse",
    "TravelPlaneFactorUpdate",
    "TravelTrainFactorCreate",
    "TravelTrainFactorHandler",
    "TravelTrainFactorResponse",
    "TravelTrainFactorUpdate",
    "MemberEntry",
    "ProfessionalTravelBaseModuleHandler",
    "ProfessionalTravelPlaneModuleHandler",
    "ProfessionalTravelTrainModuleHandler",
]
