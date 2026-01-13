"""Generic module model for storing dynamic data across different module types."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


class ModuleBase(SQLModel):
    """Base module model with shared fields."""

    variant_type_id: Optional[int] = Field(
        default=None,
        foreign_key="variant_types.id",
        index=True,
        description="Reference to variant type within module",
    )
    inventory_module_id: int = Field(
        foreign_key="inventory_modules.id",
        nullable=False,
        index=True,
        description="Reference to parent inventory module instance",
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
    - inventory_module_id links to the specific inventory module instance
      (module_type_id is on inventory_modules, not duplicated here)
    - variant_type_id defines the subcategory (student, member, etc.)
    - data stores the actual row data as JSON

    To get module_type_id, join through inventory_modules:
        modules.inventory_module_id → inventory_modules.module_type_id

    Examples:
    - Headcount student: variant_type=2, data={...}
    - Equipment scientific: variant_type=9, data={...}
    """

    __tablename__ = "modules"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<Module {self.id}: "
            f"variant={self.variant_type_id} "
            f"inv_mod={self.inventory_module_id}>"
        )
