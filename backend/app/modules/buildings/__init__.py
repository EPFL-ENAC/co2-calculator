"""Buildings module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.buildings.data_entries import (
    VALID_ROOM_TYPES,
    BuildingEmbodiedEnergyHandlerCreate,
    BuildingEmbodiedEnergyHandlerResponse,
    BuildingEmbodiedEnergyHandlerUpdate,
    BuildingRoomBuildingResponse,
    BuildingRoomEnergyDefaultsResponse,
    BuildingRoomHandlerCreate,
    BuildingRoomHandlerResponse,
    BuildingRoomHandlerUpdate,
    BuildingRoomResponse,
    EnergyCombustionHandlerCreate,
    EnergyCombustionHandlerResponse,
    EnergyCombustionHandlerUpdate,
)
from app.modules.buildings.factors import (
    BuildingEmbodiedEnergyFactorCreate,
    BuildingEmbodiedEnergyFactorHandler,
    BuildingEmbodiedEnergyFactorResponse,
    BuildingEmbodiedEnergyFactorUpdate,
    BuildingsFactorCreate,
    BuildingsFactorHandler,
    BuildingsFactorResponse,
    BuildingsFactorUpdate,
    EnergyCombustionFactorCreate,
    EnergyCombustionFactorHandler,
    EnergyCombustionFactorResponse,
    EnergyCombustionFactorUpdate,
)
from app.modules.buildings.handlers import (
    BuildingEmbodiedEnergyModuleHandler,
    BuildingRoomModuleHandler,
    EnergyCombustionModuleHandler,
)

__all__ = [
    "VALID_ROOM_TYPES",
    "BuildingEmbodiedEnergyHandlerCreate",
    "BuildingEmbodiedEnergyHandlerResponse",
    "BuildingEmbodiedEnergyHandlerUpdate",
    "BuildingRoomBuildingResponse",
    "BuildingRoomEnergyDefaultsResponse",
    "BuildingRoomHandlerCreate",
    "BuildingRoomHandlerResponse",
    "BuildingRoomHandlerUpdate",
    "BuildingRoomResponse",
    "EnergyCombustionHandlerCreate",
    "EnergyCombustionHandlerResponse",
    "EnergyCombustionHandlerUpdate",
    "BuildingEmbodiedEnergyFactorCreate",
    "BuildingEmbodiedEnergyFactorHandler",
    "BuildingEmbodiedEnergyFactorResponse",
    "BuildingEmbodiedEnergyFactorUpdate",
    "BuildingsFactorCreate",
    "BuildingsFactorHandler",
    "BuildingsFactorResponse",
    "BuildingsFactorUpdate",
    "EnergyCombustionFactorCreate",
    "EnergyCombustionFactorHandler",
    "EnergyCombustionFactorResponse",
    "EnergyCombustionFactorUpdate",
    "BuildingEmbodiedEnergyModuleHandler",
    "BuildingRoomModuleHandler",
    "EnergyCombustionModuleHandler",
]
