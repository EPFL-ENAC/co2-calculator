from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.constants import ModuleStatus


class InventoryBase(SQLModel):
    year: int
    unit_id: int  # Unit.id is now integer


class Inventory(InventoryBase, table=True):
    __tablename__ = "inventories"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique constraint for (year, unit_id) will be set in migration or manually


class InventoryModuleBase(SQLModel):
    module_type_id: int = Field(
        foreign_key="module_types.id",
        nullable=False,
        index=True,
        description="Reference to module type classification",
    )
    status: int = Field(
        default=ModuleStatus.NOT_STARTED,
        description="Module status: 0=not_started, 1=in_progress, 2=validated",
    )
    inventory_id: int = Field(
        foreign_key="inventories.id",
        index=True,
        description="Reference to parent inventory",
    )


class InventoryModule(InventoryModuleBase, table=True):
    __tablename__ = "inventory_modules"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique constraint for (inventory_id, module_type_id) will be set in migration
