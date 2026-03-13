# This file is used to mark the directory as a Python package and
# to import relevant modules for easier access.
from app.modules.buildings.schemas import (
    BuildingRoomHandlerCreate,
    EnergyCombustionHandlerCreate,
)
from app.modules.equipment_electric_consumption.schemas import EquipmentHandlerCreate
from app.modules.external_cloud_and_ai.schemas import (
    ExternalAIHandlerCreate,
    ExternalCloudHandlerCreate,
)
from app.modules.headcount.schemas import (
    HeadCountCreate,
    HeadCountStudentCreate,
    HeadCountStudentUpdate,
    HeadCountUpdate,
)
from app.modules.process_emissions.schemas import ProcessEmissionsHandlerCreate
from app.modules.professional_travel.schemas import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
)
from app.modules.purchase.schemas import (
    PurchaseHandlerCreate,
)
from app.modules.research_facilities.schemas import ResearchFacilitiesHandlerCreate

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
    "ResearchFacilitiesHandlerCreate",
]
