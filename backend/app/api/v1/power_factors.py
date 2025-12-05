from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.schemas.power_factor import (
    EquipmentClassList,
    EquipmentSubclassList,
    PowerFactorOut,
)
from app.services.power_factor_service import PowerFactorService

router = APIRouter()


@router.get("/{submodule}/classes", response_model=EquipmentClassList)
async def list_classes(
    submodule: str,
    session: AsyncSession = Depends(get_db),
):
    service = PowerFactorService()
    items = await service.get_classes(session, submodule)
    return EquipmentClassList(items=items)


@router.get(
    "/{submodule}/classes/{equipment_class:path}/subclasses",
    response_model=EquipmentSubclassList,
)
async def list_subclasses(
    submodule: str,
    equipment_class: str,
    session: AsyncSession = Depends(get_db),
):
    service = PowerFactorService()
    # Normalize equipment_class to match DB formatting when slashes present
    normalized = " / ".join([part.strip() for part in equipment_class.split("/")])
    items = await service.get_subclasses(session, submodule, normalized)
    return EquipmentSubclassList(items=items)


@router.get(
    "/{submodule}/classes/{equipment_class:path}/power",
    response_model=PowerFactorOut | None,
)
async def get_power_factor(
    submodule: str,
    equipment_class: str,
    sub_class: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    service = PowerFactorService()
    normalized_class = " / ".join([part.strip() for part in equipment_class.split("/")])
    pf = await service.get_power_factor(session, submodule, normalized_class, sub_class)
    if not pf:
        return None
    return PowerFactorOut(
        submodule=pf.submodule,
        equipment_class=pf.equipment_class,
        sub_class=pf.sub_class,
        active_power_w=pf.active_power_w,
        standby_power_w=pf.standby_power_w,
    )
