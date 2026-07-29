# This file is used to mark the directory as a Python package and
# to import relevant modules for easier access. Importing it registers
# every module and factor handler (metaclass side effect).
# Simulator Plan handlers register through the same import side effect;
# importing app.modules is the single registration point for both.
import app.modules_planner  # noqa: E402, F401
from app.modules.buildings import (
    BuildingRoomHandlerCreate,
    EnergyCombustionHandlerCreate,
)
from app.modules.equipment import EquipmentHandlerCreate
from app.modules.external_cloud_and_ai import (
    ExternalAIHandlerCreate,
    ExternalCloudHandlerCreate,
)
from app.modules.headcount import (
    HeadCountCreate,
    HeadCountStudentCreate,
    HeadCountStudentUpdate,
    HeadCountUpdate,
)
from app.modules.process_emissions import ProcessEmissionsHandlerCreate
from app.modules.professional_travel import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
)
from app.modules.purchase import (
    PurchaseCentralizedHandlerCreate,
    PurchaseHandlerCreate,
)
from app.modules.research_facilities import (
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesCommonHandlerCreate,
)

__all__ = [
    "BuildingRoomHandlerCreate",
    "EnergyCombustionHandlerCreate",
    "ExternalAIHandlerCreate",
    "ExternalCloudHandlerCreate",
    "EquipmentHandlerCreate",
    "HeadCountCreate",
    "HeadCountUpdate",
    "HeadCountStudentCreate",
    "HeadCountStudentUpdate",
    "ProcessEmissionsHandlerCreate",
    "ProfessionalTravelPlaneHandlerCreate",
    "ProfessionalTravelTrainHandlerCreate",
    "PurchaseHandlerCreate",
    "PurchaseCentralizedHandlerCreate",
    "ResearchFacilitiesCommonHandlerCreate",
    "ResearchFacilitiesAnimalHandlerCreate",
]
