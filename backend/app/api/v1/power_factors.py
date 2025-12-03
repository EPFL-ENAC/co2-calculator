from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.schemas.power_factor import EquipmentClassList, EquipmentSubclassList
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
