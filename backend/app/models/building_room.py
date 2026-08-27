"""Building room model for building/room lookup in the Buildings module."""

from sqlmodel import Field, SQLModel


class BuildingRoomBase(SQLModel):
    """Shared fields for building room records."""

    building_location: str = Field(nullable=False, index=True)
    building_name: str = Field(nullable=False, index=True)
    room_name: str = Field(nullable=False, index=True)
    room_type: str | None = Field(default=None, nullable=True)
    room_surface_square_meter: float | None = Field(default=None, nullable=True)


class BuildingRoom(BuildingRoomBase, table=True):
    """Database table model for building room records."""

    __tablename__ = "building_rooms"
    id: int | None = Field(default=None, primary_key=True, index=True)


class BuildingRoomRead(BuildingRoomBase):
    """Read model for API/serialization use cases."""

    id: int
