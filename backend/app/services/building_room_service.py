"""Building room service for business logic orchestration."""

from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building_room import BuildingRoom
from app.repositories.building_room_repo import BuildingRoomRepository


class BuildingRoomService:
    """Service layer for building-room queries."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BuildingRoomRepository(session)

    async def get_room(
        self,
        room_name: str,
    ) -> Optional[BuildingRoom]:
        """Get room by name, optionally filtered by building."""
        return await self.repo.get_room(
            room_name=room_name,
        )

    async def list_buildings(self) -> list[dict]:
        """Return distinct buildings with location and name."""
        return await self.repo.list_buildings()

    async def list_rooms(
        self,
        building_location: Optional[str] = None,
        building_name: Optional[str] = None,
    ) -> list[BuildingRoom]:
        """Return rooms, optionally filtered by building."""
        return await self.repo.list_rooms(
            building_location=building_location,
            building_name=building_name,
        )
