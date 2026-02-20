"""Archibus room repository for database operations."""

from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.archibus_room import ArchibusRoom


class ArchibusRoomRepository:
    """Repository for ArchibusRoom database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_buildings(self) -> list[dict]:
        """Return distinct buildings with their codes and names."""
        stmt = (
            select(ArchibusRoom.building_code, ArchibusRoom.building_name)
            .distinct()
            .order_by(col(ArchibusRoom.building_name))
        )
        result = await self.session.exec(stmt)
        return [
            {"building_code": row[0], "building_name": row[1]} for row in result.all()
        ]

    async def list_rooms(
        self,
        building_code: Optional[str] = None,
        building_name: Optional[str] = None,
    ) -> list[ArchibusRoom]:
        """Return rooms, optionally filtered by building_code or building_name."""
        stmt = select(ArchibusRoom).order_by(
            col(ArchibusRoom.building_code), col(ArchibusRoom.room_code)
        )
        if building_code:
            stmt = stmt.where(ArchibusRoom.building_code == building_code)
        elif building_name:
            stmt = stmt.where(ArchibusRoom.building_name == building_name)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_room(
        self, building_code: str, room_code: str
    ) -> Optional[ArchibusRoom]:
        """Return a single room by building_code and room_code."""
        stmt = select(ArchibusRoom).where(
            ArchibusRoom.building_code == building_code,
            ArchibusRoom.room_code == room_code,
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def get_room_by_names(
        self, building_name: str, room_name: str
    ) -> Optional[ArchibusRoom]:
        """Return a single room by building_name and room_name."""
        stmt = select(ArchibusRoom).where(
            ArchibusRoom.building_name == building_name,
            ArchibusRoom.room_name == room_name,
        )
        result = await self.session.exec(stmt)
        return result.first()
