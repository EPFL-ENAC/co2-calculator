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
    PurchaseAdditionalHandlerCreate,
    PurchaseHandlerCreate,
)
from app.modules.research_facilities.animals_schemas import (
    ResearchFacilitiesAnimalHandlerCreate,
)
from app.modules.research_facilities.common_schemas import (
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
    "PurchaseAdditionalHandlerCreate",
    "ResearchFacilitiesCommonHandlerCreate",
    "ResearchFacilitiesAnimalHandlerCreate",
]
