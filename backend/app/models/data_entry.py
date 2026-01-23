"""Generic module model for storing dynamic data across different module types."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


## Will be renamed to data_entries later
class DataEntryBase(SQLModel):
    """Base module model with shared fields."""

    # variant is  data_entry_types
    data_entry_type_id: Optional[int] = Field(
        default=None,
        foreign_key="data_entry_types.id",
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

    def __repr__(self) -> str:
        return (
            f"<DataEntry {self.id}>: "
            f"data_entry_type={self.data_entry_type_id} "
            f"carbon_report_module={self.carbon_report_module_id}>"
        )
