"""Location models for train stations and airports."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class TransportModeEnum(str, Enum):
    plane = "plane"
    train = "train"


class LocationFields(SQLModel):
    """Shared location fields used by both plane/train tables."""

    name: str = Field(max_length=255, nullable=False, index=True)
    airport_size: Optional[str] = Field(default=None)
    latitude: float = Field(nullable=False)
    longitude: float = Field(nullable=False)
    continent: Optional[str] = Field(default=None, max_length=2, index=True)
    country_code: Optional[str] = Field(default=None, max_length=2, index=True)
    iata_code: Optional[str] = Field(default=None, max_length=3, index=True)
    municipality: Optional[str] = Field(default=None, max_length=255, index=True)
    keywords: Optional[str] = Field(default=None, max_length=255)


class PlaneLocation(LocationFields, table=True):
    __tablename__ = "locations_plane"
    id: Optional[int] = Field(default=None, primary_key=True)


class TrainLocation(LocationFields, table=True):
    __tablename__ = "locations_train"
    id: Optional[int] = Field(default=None, primary_key=True)


class Location(LocationFields):
    """Compatibility DTO used by services/utilities."""

    id: Optional[int] = None


class LocationRead(Location):
    """API read DTO."""
