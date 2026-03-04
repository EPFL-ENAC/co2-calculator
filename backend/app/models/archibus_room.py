"""Archibus room model for building/room lookup in the Buildings module."""

from typing import Optional

from sqlmodel import Field, SQLModel


class ArchibusRoomBase(SQLModel):
    """Shared fields for Archibus room records."""

    unit_institutional_id: Optional[str] = Field(
        default=None,
        nullable=True,
        index=True,
    )
    building_location: str = Field(nullable=False, index=True)
    building_name: str = Field(nullable=False, index=True)
    room_name: str = Field(nullable=False, index=True)
    room_type: Optional[str] = Field(default=None, nullable=True)
    room_surface_square_meter: Optional[float] = Field(default=None, nullable=True)
    heating_kwh_per_square_meter: Optional[float] = Field(default=None, nullable=True)
    cooling_kwh_per_square_meter: Optional[float] = Field(default=None, nullable=True)
    ventilation_kwh_per_square_meter: Optional[float] = Field(
        default=None, nullable=True
    )
    lighting_kwh_per_square_meter: Optional[float] = Field(default=None, nullable=True)
    note: Optional[str] = Field(default=None, nullable=True)
    kg_co2eq: Optional[float] = Field(default=None, nullable=True)


class ArchibusRoom(ArchibusRoomBase, table=True):
    """Database table model for Archibus room records."""

    __tablename__ = "archibus_rooms"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)


class ArchibusRoomRead(ArchibusRoomBase):
    """Read model for API/serialization use cases."""

    id: int
