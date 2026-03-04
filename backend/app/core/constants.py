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
