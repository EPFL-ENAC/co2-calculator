"""Location models for train stations and airports."""

from typing import Optional

from sqlmodel import Field, SQLModel

# ==========================================
# 1. BASE MODEL
# ==========================================


class LocationBase(SQLModel):
    """
    Shared fields for location records.
    Stores train stations and airports with their geographic coordinates.
    """

    transport_mode: str = Field(
        nullable=False,
        index=True,
        description="Transport mode: 'plane' or 'train'",
    )
    name: str = Field(
        max_length=255,
        nullable=False,
        index=True,
        description="Location name (e.g., 'Lyndhurst Halt', 'Utirik Airport')",
    )
    airport_size: Optional[str] = Field(
        default=None,
        description="Airport size: 'medium_airport' or 'large_airport'",
    )
    latitude: float = Field(
        nullable=False,
        description="Latitude coordinate (decimal degrees)",
    )
    longitude: float = Field(
        nullable=False,
        description="Longitude coordinate (decimal degrees)",
    )
    continent: Optional[str] = Field(
        default=None,
        max_length=2,
        index=True,
        description="Continent (e.g., 'EU', 'NA', 'SA')",
    )
    countrycode: Optional[str] = Field(
        default=None,
        max_length=2,
        index=True,
        description="ISO country code (e.g., 'AE', 'AL', 'AM')",
    )
    iata_code: Optional[str] = Field(
        default=None,
        max_length=3,
        index=True,
        description="IATA airport code (e.g., 'UTK', 'OCA') - only for planes",
    )
    municipality: Optional[str] = Field(
        default=None,
        max_length=255,
        index=True,
        description="Municipality (e.g., 'Dubai', 'Berlin')",
    )
    keywords: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Keywords (e.g., ['airport', 'train station'])",
    )


# ==========================================
# 2. TABLE MODEL (Database)
# ==========================================


class Location(LocationBase, table=True):
    """
    Database table for train stations and airports.
    Inherits Base fields + Audit fields + Adds ID.
    """

    __tablename__ = "locations"

    # ID: Integer, Primary Key, Auto-Increment
    id: Optional[int] = Field(default=None, primary_key=True)

    def __repr__(self) -> str:
        return (
            f"<Location id={self.id} "
            f"mode={self.transport_mode} "
            f"name={self.name} "
            f"({self.latitude}, {self.longitude}) "
            f"country={self.countrycode}>"
        )


# ==========================================
# 3. API OUTPUT MODELS (DTOs)
# ==========================================


class LocationRead(LocationBase):
    """
    Response schema for GET requests.
    Returns Data + ID + Audit timestamps.
    """

    id: int
