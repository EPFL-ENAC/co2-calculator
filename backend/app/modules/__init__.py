# This file is used to mark the directory as a Python package and
# to import relevant modules for easier access.
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
from app.modules.professional_travel.schemas import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
)

__all__ = [
    "ExternalAIHandlerCreate",
    "ExternalCloudHandlerCreate",
    "EquipmentHandlerCreate",
    "HeadCountCreate",
    "HeadCountUpdate",
    "HeadCountStudentCreate",
    "HeadCountStudentUpdate",
    "ProfessionalTravelPlaneHandlerCreate",
    "ProfessionalTravelTrainHandlerCreate",
]
