"""Building rooms lookup API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.modules.buildings.schemas import (
    BuildingRoomBuildingResponse,
    BuildingRoomResponse,
)
from app.services.building_room_service import BuildingRoomService

router = APIRouter()


@router.get(
    "/building-rooms",
    response_model=list[BuildingRoomBuildingResponse | BuildingRoomResponse],
)
async def get_building_rooms(
    building_location: Optional[str] = Query(default=None),
    building_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> list[BuildingRoomBuildingResponse | BuildingRoomResponse]:
    """Return buildings and rooms for the Buildings module dropdowns."""

    building_room_service = BuildingRoomService(db)

    if building_location or building_name:
        rooms = await building_room_service.list_rooms(
            building_location=building_location,
            building_name=building_name,
        )
        return [BuildingRoomResponse.model_validate(room) for room in rooms]

    buildings = await building_room_service.list_buildings()
    return [
        BuildingRoomBuildingResponse.model_validate(building) for building in buildings
    ]
