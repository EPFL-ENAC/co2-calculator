from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_db
from app.schemas.inventory import (
    InventoryCreate,
    InventoryModuleRead,
    InventoryModuleUpdate,
    InventoryRead,
)
from app.services.inventory_module_service import InventoryModuleService
from app.services.inventory_service import InventoryService

router = APIRouter()


# List all inventories for a given unit
@router.get("/unit/{unit_id}/", response_model=List[InventoryRead])
async def list_inventories_by_unit(unit_id: int, db: AsyncSession = Depends(get_db)):
    service = InventoryService(db)
    return await service.list_inventories_by_unit(unit_id)


# Return 404 if inventory not found retrieve inventory of a unit for a given year
@router.get("/unit/{unit_id}/year/{year}/", response_model=InventoryRead)
async def get_inventory_by_unit_and_year(
    unit_id: int, year: int, db: AsyncSession = Depends(get_db)
):
    service = InventoryService(db)
    inv = await service.get_inventory_by_unit_and_year(unit_id, year)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inv


# Create a new inventory for a given unit and year
@router.post("/", response_model=InventoryRead, status_code=status.HTTP_201_CREATED)
async def create_inventory(
    inventory: InventoryCreate, db: AsyncSession = Depends(get_db)
):
    service = InventoryService(db)
    return await service.create_inventory(inventory)


@router.get("/{inventory_id}", response_model=InventoryRead)
async def get_inventory(inventory_id: int, db: AsyncSession = Depends(get_db)):
    service = InventoryService(db)
    inv = await service.get_inventory(inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inv


# --- InventoryModule endpoints ---


@router.get("/{inventory_id}/modules/", response_model=List[InventoryModuleRead])
async def list_inventory_modules(inventory_id: int, db: AsyncSession = Depends(get_db)):
    """List all modules for an inventory with their statuses."""
    # First verify inventory exists
    inv_service = InventoryService(db)
    inv = await inv_service.get_inventory(inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")

    module_service = InventoryModuleService(db)
    return await module_service.list_modules(inventory_id)


@router.patch(
    "/{inventory_id}/modules/{module_type_id}/status",
    response_model=InventoryModuleRead,
)
async def update_module_status(
    inventory_id: int,
    module_type_id: int,
    update: InventoryModuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the status of an inventory module.

    Status values:
    - 0: not_started
    - 1: in_progress
    - 2: validated
    """
    # First verify inventory exists
    inv_service = InventoryService(db)
    inv = await inv_service.get_inventory(inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")

    module_service = InventoryModuleService(db)
    try:
        result = await module_service.update_status(
            inventory_id, module_type_id, update.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Module type {module_type_id} not found for inventory {inventory_id}"
            ),
        )
    return result
