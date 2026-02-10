"""Location models for train stations and airports."""

from typing import Optional

from sqlmodel import Field, SQLModel

from .headcount import AuditMixin

# ==========================================
# 1. BASE MODEL
# ==========================================


class LocationBase(SQLModel):
    """
    Shared fields for location records.
    Stores train stations and airports with their geographic coordinates.
    """

    transport_mode: str = Field(
        max_length=50,
        nullable=False,
        index=True,
        description="Transport mode: 'train' or 'plane'",
    )
    name: str = Field(
        max_length=255,
        nullable=False,
        index=True,
        description="Location name (e.g., 'Lyndhurst Halt', 'Utirik Airport')",
    )
    latitude: float = Field(
        nullable=False,
        description="Latitude coordinate (decimal degrees)",
    )
    longitude: float = Field(
        nullable=False,
        description="Longitude coordinate (decimal degrees)",
    )
    iata_code: Optional[str] = Field(
        default=None,
        max_length=10,
        index=True,
        description="IATA airport code (e.g., 'UTK', 'OCA') - only for planes",
    )
    countrycode: Optional[str] = Field(
        default=None,
        max_length=10,
        index=True,
        description="ISO country code (e.g., 'AE', 'AL', 'AM')",
    )


# ==========================================
# 2. TABLE MODEL (Database)
# ==========================================


class Location(LocationBase, AuditMixin, table=True):
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


class LocationRead(LocationBase, AuditMixin):
    """
    Response schema for GET requests.
    Returns Data + ID + Audit timestamps.
    """

    id: int
