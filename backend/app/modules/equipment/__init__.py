"""Equipment module package.

Importing this package registers the module and factor handlers
(metaclass side effect in ``handlers``/``factors``).
"""

from app.modules.equipment.data_entries import (
    MAX_WEEKLY_USAGE_HOURS,
    EquipmentHandlerCreate,
    EquipmentHandlerResponse,
    EquipmentHandlerUpdate,
)
from app.modules.equipment.factors import (
    EquipmentFactorCreate,
    EquipmentFactorHandler,
    EquipmentFactorResponse,
    EquipmentFactorUpdate,
)
from app.modules.equipment.handlers import EquipmentModuleHandler

__all__ = [
    "MAX_WEEKLY_USAGE_HOURS",
    "EquipmentHandlerCreate",
    "EquipmentHandlerResponse",
    "EquipmentHandlerUpdate",
    "EquipmentFactorCreate",
    "EquipmentFactorHandler",
    "EquipmentFactorResponse",
    "EquipmentFactorUpdate",
    "EquipmentModuleHandler",
]
