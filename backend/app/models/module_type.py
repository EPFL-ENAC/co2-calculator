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
    equipment_electric_consumption = 4
    purchase = 5
    internal_services = 6
    external_cloud_and_ai = 7
    process_emissions = 8
    global_energy = 99


ALL_MODULE_TYPE_IDS = list(ModuleTypeEnum)


# corresponding data_entry_type enum for each module type

MODULE_TYPE_TO_DATA_ENTRY_TYPES = {
    ModuleTypeEnum.headcount: [
        DataEntryTypeEnum.member,
        DataEntryTypeEnum.student,
    ],
    ModuleTypeEnum.equipment_electric_consumption: [
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
        DataEntryTypeEnum.additional_purchases,
    ],
    ModuleTypeEnum.global_energy: [
        DataEntryTypeEnum.energy_mix,
    ],
    # Add more if needed for other modules
}


def get_data_entry_types_for_module_type(
    module_type: ModuleTypeEnum,
) -> list[DataEntryTypeEnum]:
    """Get the data entry types for a given module type."""
    return MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])
