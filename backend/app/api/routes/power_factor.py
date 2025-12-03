from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.schemas.power_factor import EquipmentClassList, EquipmentSubclassList
from app.services.power_factor_service import PowerFactorService

router = APIRouter(prefix="/power-factors", tags=["power-factors"])


@router.get("/{submodule}/classes", response_model=EquipmentClassList)
async def list_classes(
    submodule: str,
    session: AsyncSession = Depends(get_db),
):
    service = PowerFactorService()
    items = await service.get_classes(session, submodule)
    if not items:
        # Not an error; return empty list for unknown submodule
        return EquipmentClassList(items=[])
    return EquipmentClassList(items=items)


@router.get(
    "/{submodule}/classes/{equipment_class}/subclasses",
    response_model=EquipmentSubclassList,
)
async def list_subclasses(
    submodule: str,
    equipment_class: str,
    session: AsyncSession = Depends(get_db),
):
    service = PowerFactorService()
    items = await service.get_subclasses(session, submodule, equipment_class)
    return EquipmentSubclassList(items=items)
