"""Building room reference model for the Buildings module."""

from typing import Optional

from sqlmodel import Field, SQLModel


class BuildingRoomBase(SQLModel):
    """Shared fields for building room reference records."""

    building_location: str = Field(nullable=False, index=True)
    building_name: str = Field(nullable=False, index=True)
    room_name: str = Field(nullable=False, index=True)
    room_type: Optional[str] = Field(default=None, nullable=True)
    room_surface_square_meter: Optional[float] = Field(default=None, nullable=True)


class BuildingRoom(BuildingRoomBase, table=True):
    """Database table model for building room reference records."""

    __tablename__ = "building_rooms"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)


class BuildingRoomRead(BuildingRoomBase):
    """Read model for API/serialization use cases."""

    id: int
