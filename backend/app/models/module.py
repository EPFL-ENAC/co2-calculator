"""Generic module model for storing dynamic data across different module types."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


## Will be renamed to data_entries later
class ModuleBase(SQLModel):
    """Base module model with shared fields."""

    module_type_id: int = Field(
        foreign_key="module_types.id",
        nullable=False,
        index=True,
        description="Reference to module type classification",
    )
    # variant is  data_entry_types
    variant_type_id: Optional[int] = Field(
        default=None,
        foreign_key="variant_types.id",
        index=True,
        description="Reference to variant type within module",
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


class Module(ModuleBase, table=True):
    """
    Generic module table for storing data across different module types.

    This table provides a flexible storage mechanism where:
    - module_type_id defines the category (headcount, equipment, travel)
    - variant_type_id defines the subcategory (student, member, etc.)
    - carbon_report_module_id links to the specific carbon report module instance
    - data stores the actual row data as JSON

    Examples:
    - Headcount student: module_type=1, variant_type=2, data={...}
    - Equipment scientific: module_type=4, variant_type=9, data={...}
    """

    __tablename__ = "modules"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<Module {self.id}: type={self.module_type_id} "
            f"variant={self.variant_type_id} "
            f"carbon_report_module={self.carbon_report_module_id}>"
        )
