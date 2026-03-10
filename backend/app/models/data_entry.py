"""Generic module model for storing dynamic data across different module types."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import JSON, Field, SQLModel


class DataEntryStatusEnum(int, Enum):
    PENDING = 0
    VALIDATED = 1
    REJECTED = 2


class DataEntryTypeEnum(int, Enum):
    # headcount
    member = 1
    student = 2
    # equipment
    scientific = 10
    it = 11
    other = 12
    # travel
    plane = 20
    train = 21
    # building/room
    building = 30
    energy_combustion = 31
    # external clouds and ai
    external_clouds = 40
    external_ai = 41
    # process emissions
    process_emissions = 50
    # purchase
    scientific_equipment = 60
    it_equipment = 61
    consumable_accessories = 62
    biological_chemical_gaseous_product = 63
    services = 64
    vehicles = 65
    other_purchases = 66
    additional_purchases = 67

    # Research facilities: Was internal services
    # Implementation of the module "Research facilities" and its sub-modules:
    research_facilities = 70
    mice_and_fish_animal_facilities = 71
    # not a module per se but we need a data_entry_type to link the factor
    # energy_mix will disapear when we add the info in the factor equipment table
    # energy mix
    energy_mix = 100


## Will be renamed to data_entries later
class DataEntryBase(SQLModel):
    """Base module model with shared fields."""

    # variant is data_entry_types
    data_entry_type_id: int = Field(
        nullable=False,
        index=True,
        description="Reference to data entry type within module",
    )
    carbon_report_module_id: int = Field(
        foreign_key="carbon_report_modules.id",
        nullable=False,
        index=True,
        description="Reference to parent carbon report module instance",
    )
    data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Dynamic JSON storage for module-specific data",
    )

    status: Optional[DataEntryStatusEnum] = Field(
        default=DataEntryStatusEnum.PENDING,
        description="Optional status field for additional state tracking",
    )

    @property
    def data_entry_type(self) -> DataEntryTypeEnum:
        """Get the data entry type as an enum."""
        return DataEntryTypeEnum(self.data_entry_type_id)

    @data_entry_type.setter
    def data_entry_type(self, value: DataEntryTypeEnum) -> None:
        """Set the data entry type from an enum."""
        self.data_entry_type_id = value.value


# Database model


class DataEntry(DataEntryBase, table=True):
    """
    Generic module table for storing data across different module types.

    This table provides a flexible storage mechanism where:
    - module_type_id defines the category (headcount, equipment, travel)
    - data_entry_type_id defines the subcategory (student, member, etc.)
    - carbon_report_module_id links to the specific carbon report module instance
    - data stores the actual row data as JSON

    Examples:
    - Headcount student: module_type=1, data_entry_type=2, data={...}
    - Equipment scientific: module_type=4, data_entry_type=9, data={...}
    """

    __tablename__ = "data_entries"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, default=datetime.utcnow, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DataEntry {self.id}>: "
            f"data_entry_type={self.data_entry_type_id} "
            f"carbon_report_module={self.carbon_report_module_id}>"
        )
