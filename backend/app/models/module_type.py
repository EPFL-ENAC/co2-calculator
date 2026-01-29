"""Module type model for classifying different module categories."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.data_entry import DataEntryTypeEnum


# enum - used in other files
class ModuleTypeEnum(int, Enum):
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
    infrastructure = 3
    equipment_electric_consumption = 4
    purchase = 5
    internal_services = 6
    external_cloud_and_ai = 7
    global_energy = 99


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
        # DataEntryTypeEnum.flight,
        # DataEntryTypeEnum.train,
        DataEntryTypeEnum.trips,
    ],
    ModuleTypeEnum.infrastructure: [
        DataEntryTypeEnum.building,
    ],
    ModuleTypeEnum.external_cloud_and_ai: [
        DataEntryTypeEnum.external_clouds,
        DataEntryTypeEnum.external_ai,
    ],
    ModuleTypeEnum.global_energy: [
        DataEntryTypeEnum.energy_mix,
    ],
    # Add more if needed for other modules
}


class ModuleTypeBase(SQLModel):
    """Base module type model with shared fields."""

    name: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Module type name (e.g., 'headcount', 'equipment', 'travel')",
    )


class ModuleType(ModuleTypeBase, table=True):
    """
    Module type table for classifying different module categories.

    Examples: headcount, equipment, travel, purchases, etc.
    """

    __tablename__ = "module_types"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<ModuleType {self.id}: {self.name}>"
