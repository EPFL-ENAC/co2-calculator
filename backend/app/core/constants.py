"""Application constants and enums."""

from enum import IntEnum

from app.models.data_entry import DataEntryTypeEnum
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
# Status to ModuleStatus Mapping
# =============================================================================
STATUS_TO_ENUM = {
    "validated": ModuleStatus.VALIDATED,
    "in-progress": ModuleStatus.IN_PROGRESS,
    "not_started": ModuleStatus.NOT_STARTED,
}


# =============================================================================
# Backoffice Pagination Defaults
# =============================================================================
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE_UNITS = 50
DEFAULT_PAGE_SIZE_EXPORT = 100
MIN_PAGE_SIZE = 1
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE_UNITS = 50
DEFAULT_PAGE_SIZE_EXPORT = 100
MAX_PAGE_SIZE_UNITS = 5000
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

# Base name of each submodule's file inside the detailed-export archive (#589).
# These are the names the product already uses for the submodule elsewhere: the
# import templates users download (``frontend/public/templates``) and the factor
# seeds (``app/seed/seed_generic_factors.py``). Exporting the raw enum member
# names instead would hand back files (``buildings_building``) under names no
# one outside the backend recognises.
#
# The lookup in ``report_detailed`` is unguarded, so every ``DataEntryTypeEnum``
# member must appear here — ``tests/unit/v1/test_backoffice.py`` pins that.
DETAILED_EXPORT_FILE_NAMES: dict[DataEntryTypeEnum, str] = {
    DataEntryTypeEnum.member: "headcount_member",
    DataEntryTypeEnum.student: "headcount_students",
    DataEntryTypeEnum.scientific: "equipment_scientific",
    DataEntryTypeEnum.it: "equipment_IT",
    DataEntryTypeEnum.other: "equipment_other",
    DataEntryTypeEnum.plane: "travel_planes",
    DataEntryTypeEnum.train: "travel_trains",
    DataEntryTypeEnum.building: "building_rooms",
    DataEntryTypeEnum.energy_combustion: "building_energycombustions",
    DataEntryTypeEnum.building_embodied_energy: "buildings_greyenergy",
    DataEntryTypeEnum.external_clouds: "external_clouds",
    DataEntryTypeEnum.external_ai: "external_ai",
    DataEntryTypeEnum.process_emissions: "processemissions",
    DataEntryTypeEnum.scientific_equipment: "purchases_scientificequipment",
    DataEntryTypeEnum.it_equipment: "purchases_itequipment",
    DataEntryTypeEnum.consumable_accessories: "purchases_consumables",
    DataEntryTypeEnum.biological_chemical_gaseous_product: (
        "purchases_biological_chemical_gaseous"
    ),
    DataEntryTypeEnum.services: "purchases_services",
    DataEntryTypeEnum.vehicles: "purchases_vehicles",
    DataEntryTypeEnum.other_purchases: "purchases_other",
    DataEntryTypeEnum.additional_purchases: "purchases_additional",
    DataEntryTypeEnum.research_facilities: "researchfacilities_common",
    DataEntryTypeEnum.mice_and_fish_animal_facilities: "researchfacilities_animals",
}


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
