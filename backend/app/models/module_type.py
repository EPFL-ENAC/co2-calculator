"""Module type model for classifying different module categories."""

from enum import IntEnum

from app.models.data_entry import DataEntryTypeEnum


# enum - used in other files
class ModuleTypeEnum(IntEnum):
    """
    How the data entered the system.

    Current:
    - api: direct API call
    - csv: CSV file upload

    Potential future values
    - webhook: event-driven external push
    - sync: scheduled integration sync
    - import_job: background/batch import
    - manual: manual user entry
    """

    headcount = 1
    professional_travel = 2
    buildings = 3
    equipment = 4
    purchase = 5
    research_facilities = 6
    external_cloud_and_ai = 7
    process_emissions = 8


ALL_MODULE_TYPE_IDS = [mt for mt in ModuleTypeEnum]

TOTAL_MODULE_TYPES = len(ModuleTypeEnum)
DEFAULT_COMPLETION_PROGRESS = f"0/{TOTAL_MODULE_TYPES}"

# Simulator Plan "prefilled" (type-2) modules: snapshot-copied from the
# reference year. Mirrors the frontend planner-module-config
# ``behavior === 'prefilled'`` set. Headcount is prefilled too, but its
# Calculator rows are aggregated per SIUS category instead of copied one to
# one — see ``SimulatorPlanService.prefill_headcount_from_reference``.
PLANNER_PREFILLED_MODULE_TYPES: set[ModuleTypeEnum] = {
    ModuleTypeEnum.headcount,
    ModuleTypeEnum.process_emissions,
    ModuleTypeEnum.buildings,
    ModuleTypeEnum.equipment,
    ModuleTypeEnum.research_facilities,
    ModuleTypeEnum.external_cloud_and_ai,
}

# Modules a Project Grant report always counts: a grant proposal is first and
# foremost about the equipment and research facilities it funds, so their
# Active checkbox is locked on (#1976). Mirrors the frontend
# planner-module-config GRANT_LOCKED_MODULES set.
GRANT_LOCKED_MODULE_TYPES: set[ModuleTypeEnum] = {
    ModuleTypeEnum.equipment,
    ModuleTypeEnum.research_facilities,
}


# corresponding data_entry_type enum for each module type

MODULE_TYPE_TO_DATA_ENTRY_TYPES = {
    ModuleTypeEnum.headcount: [
        DataEntryTypeEnum.member,
        DataEntryTypeEnum.student,
        DataEntryTypeEnum.planner_headcount,
    ],
    ModuleTypeEnum.equipment: [
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.other,
    ],
    ModuleTypeEnum.professional_travel: [
        DataEntryTypeEnum.plane,
        DataEntryTypeEnum.train,
    ],
    ModuleTypeEnum.buildings: [
        DataEntryTypeEnum.building,
        DataEntryTypeEnum.energy_combustion,
        DataEntryTypeEnum.building_embodied_energy,
    ],
    ModuleTypeEnum.external_cloud_and_ai: [
        DataEntryTypeEnum.external_clouds,
        DataEntryTypeEnum.external_ai,
    ],
    ModuleTypeEnum.process_emissions: [
        DataEntryTypeEnum.process_emissions,
    ],
    ModuleTypeEnum.purchase: [
        DataEntryTypeEnum.scientific_equipment,
        DataEntryTypeEnum.it_equipment,
        DataEntryTypeEnum.consumable_accessories,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        DataEntryTypeEnum.services,
        DataEntryTypeEnum.vehicles,
        DataEntryTypeEnum.other_purchases,
        DataEntryTypeEnum.purchases_centralized,
        # Planner kinds last so Calculator submodule ordering is untouched.
        DataEntryTypeEnum.planner_purchase,
        DataEntryTypeEnum.planner_purchase_budget,
    ],
    ModuleTypeEnum.research_facilities: [
        DataEntryTypeEnum.research_facilities,
        DataEntryTypeEnum.animal_facilities,
    ],
    # Add more if needed for other modules
}


def get_data_entry_types_for_module_type(
    module_type: ModuleTypeEnum,
) -> list[DataEntryTypeEnum]:
    """Get the data entry types for a given module type.

    Args:
        module_type: The module type to get data entry types for.
    Returns:
        List of data entry types associated with the given module type.
    """
    return MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])


def get_module_type_for_data_entry_type(
    data_entry_type: DataEntryTypeEnum,
) -> ModuleTypeEnum | None:
    """Get the module type for a given data entry type.

    Args:
        data_entry_type: The data entry type to get the module type for.
    Returns:
        The module type associated with the given data entry type, or None if not found.
    """
    for module_type, data_entry_types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        if data_entry_type in data_entry_types:
            return module_type
    return None
