"""Data entry model for storing dynamic data across different module types."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


class DataEntryBase(SQLModel):
    """Base data entry model with shared fields."""

    data_entry_type_id: Optional[int] = Field(
        default=None,
        foreign_key="data_entry_types.id",
        index=True,
        description="Reference to data entry type/variant within module",
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
    Generic data entry table for storing data across different module types.

    This table provides a flexible storage mechanism where:
    - carbon_report_module_id links to the specific carbon report module instance
      (module_type_id is on carbon_report_modules, not duplicated here)
    - data_entry_type_id defines the subcategory/variant (student, member, scientific, etc.)
    - data stores the actual row data as JSON

    To get module_type_id, join through carbon_report_modules:
        data_entries.carbon_report_module_id → carbon_report_modules.module_type_id

    Examples:
    - Headcount student: data_entry_type=2, data={fte: 10.5, ...}
    - Equipment scientific: data_entry_type=9, data={name: "Microscope", ...}
    """

    __tablename__ = "data_entries"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<DataEntry {self.id}: "
            f"type={self.data_entry_type_id} "
            f"report_module={self.carbon_report_module_id}>"
        )
