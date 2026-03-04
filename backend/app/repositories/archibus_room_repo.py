"""Archibus room repository for database operations."""

from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.archibus_room import ArchibusRoom


class ArchibusRoomRepository:
    """Repository for ArchibusRoom database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_buildings(
        self,
        unit_institutional_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """Return distinct buildings with location and name."""
        if unit_institutional_ids is not None and not unit_institutional_ids:
            return []
        stmt = (
            select(ArchibusRoom.building_location, ArchibusRoom.building_name)
            .distinct()
            .order_by(
                col(ArchibusRoom.building_location),
                col(ArchibusRoom.building_name),
            )
        )
        if unit_institutional_ids is not None:
            stmt = stmt.where(
                col(ArchibusRoom.unit_institutional_id).in_(unit_institutional_ids)
            )
        result = await self.session.exec(stmt)
        return [
            {"building_location": row[0], "building_name": row[1]}
            for row in result.all()
        ]

    async def list_rooms(
        self,
        unit_institutional_ids: Optional[list[str]] = None,
        building_location: Optional[str] = None,
        building_name: Optional[str] = None,
    ) -> list[ArchibusRoom]:
        """Return rooms, optionally filtered by unit/building."""
        if unit_institutional_ids is not None and not unit_institutional_ids:
            return []
        stmt = select(ArchibusRoom).order_by(
            col(ArchibusRoom.building_location),
            col(ArchibusRoom.building_name),
            col(ArchibusRoom.room_name),
        )
        if unit_institutional_ids is not None:
            stmt = stmt.where(
                col(ArchibusRoom.unit_institutional_id).in_(unit_institutional_ids)
            )
        if building_location:
            stmt = stmt.where(ArchibusRoom.building_location == building_location)
        elif building_name:
            stmt = stmt.where(ArchibusRoom.building_name == building_name)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_room(
        self,
        building_name: str,
        room_name: str,
        building_location: Optional[str] = None,
    ) -> Optional[ArchibusRoom]:
        """Return a single room by building_name and room_name."""
        stmt = select(ArchibusRoom).where(
            ArchibusRoom.building_name == building_name,
            ArchibusRoom.room_name == room_name,
        )
        if building_location:
            stmt = stmt.where(ArchibusRoom.building_location == building_location)
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
