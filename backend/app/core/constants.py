"""Application constants and enums."""

from enum import IntEnum


class ModuleStatus(IntEnum):
    """
    Status values for inventory modules.

    These map to the frontend MODULE_STATES constant:
    - NOT_STARTED (0) = Default
    - IN_PROGRESS (1) = InProgress
    - VALIDATED (2) = Validated
    """

    NOT_STARTED = 0
    IN_PROGRESS = 1
    VALIDATED = 2


# Module type IDs matching the seeded module_types table
# These correspond to frontend MODULES constant
class ModuleTypeId(IntEnum):
    """Module type IDs as seeded in module_types table."""

    MY_LAB = 1
    PROFESSIONAL_TRAVEL = 2
    INFRASTRUCTURE = 3
    EQUIPMENT_ELECTRIC_CONSUMPTION = 4
    PURCHASE = 5
    INTERNAL_SERVICES = 6
    EXTERNAL_CLOUD = 7


# List of all module type IDs for iteration
ALL_MODULE_TYPE_IDS = list(ModuleTypeId)
