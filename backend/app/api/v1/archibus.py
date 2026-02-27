"""Archibus lookup API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.repositories.archibus_room_repo import ArchibusRoomRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.archibus import ArchibusBuildingResponse, ArchibusRoomResponse

router = APIRouter()


@router.get(
    "/archibus-rooms",
    response_model=list[ArchibusBuildingResponse | ArchibusRoomResponse],
)
async def get_archibus_rooms(
    unit_id: Optional[int] = Query(default=None),
    building_location: Optional[str] = Query(default=None),
    building_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> list[ArchibusBuildingResponse | ArchibusRoomResponse]:
    """Return Archibus buildings and rooms for the Buildings module dropdowns."""

    repo = ArchibusRoomRepository(db)
    if unit_id is None:
        return []

    unit = await UnitRepository(db).get_by_id(unit_id)
    if unit is None:
        return []

    unit_institutional_ids = UnitRepository.build_archibus_unit_ids(unit)

    if building_location or building_name:
        rooms = await repo.list_rooms(
            unit_institutional_ids=unit_institutional_ids,
            building_location=building_location,
            building_name=building_name,
        )
        return [ArchibusRoomResponse.model_validate(room) for room in rooms]

    buildings = await repo.list_buildings(unit_institutional_ids=unit_institutional_ids)
    return [ArchibusBuildingResponse.model_validate(building) for building in buildings]
