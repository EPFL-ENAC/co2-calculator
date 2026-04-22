"""Application constants and enums."""

from enum import IntEnum

from app.models.module_type import ModuleTypeEnum


# =============================================================================
# Module Status
# =============================================================================
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


# =============================================================================
# Status Priority Order
# =============================================================================
STATUS_ORDER = {
    "validated": 3,
    "in-progress": 2,
    "default": 1,
}


# =============================================================================
# Backoffice Pagination Defaults
# =============================================================================
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE_UNITS = 50
DEFAULT_PAGE_SIZE_EXPORT = 100
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE_UNITS = 100
MAX_PAGE_SIZE_EXPORT = 100


# =============================================================================
# Backoffice Error Messages
# =============================================================================
ERROR_AT_LEAST_ONE_YEAR = "At least one year must be specified for reporting overview"
ERROR_INVALID_FORMAT = "Invalid format specified"


# =============================================================================
# Backoffice Export Constants
# =============================================================================
EXPORT_CSV_DATE_FORMAT = "%Y-%m-%d"
EXPORT_CSV_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
EXPORT_FILENAME_PREFIX_REPORTING = "reporting_export"
EXPORT_FILENAME_PREFIX_USAGE = "usage_report"
EXPORT_FILENAME_PREFIX_RESULTS = "results_report"
EXPORT_FILENAME_PREFIX_DETAILED = "detailed_report"


# =============================================================================
# Backoffice CSV Headers
# =============================================================================
EXPORT_CSV_HEADERS = [
    "id",
    "unit_name",
    "affiliation",
    "validation_status",
    "principal_user",
    "last_update",
    "highest_result_category",
    "total_carbon_footprint",
    "view_url",
]


# =============================================================================
# Backoffice Fallback Values
# =============================================================================
UNKNOWN_UNIT = "Unknown Unit"
UNKNOWN_AFFILIATION = "Unknown Affiliation"
UNKNOWN_USER = "Unknown User"
UNKNOWN_STATUS = "unknown"
DEFAULT_CARBON_FOOTPRINT = 0.0


# =============================================================================
# Year Validation
# =============================================================================
YEAR_LENGTH = 4


# =============================================================================
# Module Completion
# =============================================================================
TOTAL_MODULE_TYPES = len(ModuleTypeEnum)
DEFAULT_COMPLETION_PROGRESS = f"0/{TOTAL_MODULE_TYPES}"
