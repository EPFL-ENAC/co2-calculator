from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import ModuleStatus


class InventoryBase(BaseModel):
    year: int
    # Assuming Unit.id is str as in your unit.py (will be int the future!)
    unit_id: int


class InventoryCreate(InventoryBase):
    pass


class InventoryRead(InventoryBase):
    id: int

    class Config:
        orm_mode = True


class InventoryUpdate(BaseModel):
    year: Optional[int] = None
    unit_id: Optional[str] = None


# InventoryModule schemas
class InventoryModuleBase(BaseModel):
    inventory_id: int
    module_type_id: int
    status: int = Field(default=ModuleStatus.NOT_STARTED)


class InventoryModuleCreate(BaseModel):
    """Schema for creating an inventory module (inventory_id set by path)."""

    module_type_id: int
    status: int = Field(default=ModuleStatus.NOT_STARTED)


class InventoryModuleRead(BaseModel):
    id: int
    inventory_id: int
    module_type_id: int
    status: int

    class Config:
        orm_mode = True


class InventoryModuleUpdate(BaseModel):
    """Schema for updating an inventory module status."""

    status: int = Field(
        ...,
        ge=ModuleStatus.NOT_STARTED,
        le=ModuleStatus.VALIDATED,
        description="Module status: 0=not_started, 1=in_progress, 2=validated",
    )
