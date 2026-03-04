"""Building rooms lookup API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.repositories.building_room_repo import BuildingRoomRepository
from app.schemas.building_room import BuildingResponse, BuildingRoomResponse

router = APIRouter()


@router.get(
    "/building-rooms",
    response_model=list[BuildingResponse | BuildingRoomResponse],
)
async def get_building_rooms(
    unit_id: Optional[int] = Query(default=None),
    building_location: Optional[str] = Query(default=None),
    building_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> list[BuildingResponse | BuildingRoomResponse]:
    """Return buildings and rooms for the Buildings module dropdowns."""

    repo = BuildingRoomRepository(db)

    if building_location or building_name:
        rooms = await repo.list_rooms(
            building_location=building_location,
            building_name=building_name,
        )
        return [BuildingRoomResponse.model_validate(room) for room in rooms]

    buildings = await repo.list_buildings()
    return [BuildingResponse.model_validate(building) for building in buildings]
