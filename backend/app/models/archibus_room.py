"""Archibus room model for building/room lookup in the Buildings module."""

from typing import Optional

from sqlmodel import Field, SQLModel


class ArchibusRoom(SQLModel, table=True):
    """Room data imported from the Archibus facility-management system.

    Used by the Buildings module to populate building/room dropdowns
    and auto-fill surface area for energy consumption calculations.
    """

    __tablename__ = "archibus_rooms"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    building_name: str = Field(nullable=False, index=True)
    building_code: str = Field(nullable=False, index=True)
    room_code: str = Field(nullable=False, index=True)
    room_name: str = Field(nullable=False)
    generic_type_din: str = Field(nullable=False)
    sia_type: str = Field(nullable=False)
    surface_m2: float = Field(nullable=False)
