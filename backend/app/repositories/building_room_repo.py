"""Building room repository for database operations."""

from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building_room import BuildingRoom


class BuildingRoomRepository:
    """Repository for BuildingRoom database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_buildings(self) -> list[dict]:
        """Return distinct buildings with location and name."""
        stmt = (
            select(BuildingRoom.building_location, BuildingRoom.building_name)
            .distinct()
            .order_by(
                col(BuildingRoom.building_location),
                col(BuildingRoom.building_name),
            )
        )
        result = await self.session.exec(stmt)
        return [
            {"building_location": row[0], "building_name": row[1]}
            for row in result.all()
        ]

    async def list_rooms(
        self,
        building_location: Optional[str] = None,
        building_name: Optional[str] = None,
    ) -> list[BuildingRoom]:
        """Return rooms, optionally filtered by building."""
        stmt = select(BuildingRoom).order_by(
            col(BuildingRoom.building_location),
            col(BuildingRoom.building_name),
            col(BuildingRoom.room_name),
        )
        if building_location:
            stmt = stmt.where(BuildingRoom.building_location == building_location)
        elif building_name:
            stmt = stmt.where(BuildingRoom.building_name == building_name)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_room(
        self,
        building_name: str,
        room_name: str,
        building_location: Optional[str] = None,
    ) -> Optional[BuildingRoom]:
        """Return a single room by building_name and room_name."""
        stmt = select(BuildingRoom).where(
            BuildingRoom.building_name == building_name,
            BuildingRoom.room_name == room_name,
        )
        if building_location:
            stmt = stmt.where(BuildingRoom.building_location == building_location)
        result = await self.session.exec(stmt)
        return result.first()

    async def get_room_by_names(
        self, building_name: str, room_name: str
    ) -> Optional[BuildingRoom]:
        """Return a single room by building_name and room_name."""
        stmt = select(BuildingRoom).where(
            BuildingRoom.building_name == building_name,
            BuildingRoom.room_name == room_name,
        )
        result = await self.session.exec(stmt)
        return result.first()
