"""Location models for train stations and airports."""

import re
from enum import Enum
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

# ==========================================
# 1. BASE MODEL
# ==========================================


# enum - used in other files
class TransportModeEnum(str, Enum):
    """
    Location classification for transport networks.
    Used to distinguish airport locations from train station locations.
    """

    plane = "plane"
    train = "train"


class LocationBase(SQLModel):
    """
    Shared fields for location records.
    Stores train stations and airports with their geographic coordinates.
    """

    transport_mode: TransportModeEnum = Field(
        nullable=False,
        index=True,
        description="Location transport mode: 'plane' (airport) or 'train' (station)",
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
    country_code: Optional[str] = Field(
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
        description=(
            "Keywords (e.g., ['airport', 'train station']); indexed via "
            "explicit Alembic trigram GIN migration"
        ),
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
    __table_args__ = (
        Index(
            "uq_location_natural_key",
            "natural_key",
            unique=True,
        ),
    )

    # ID: Integer, Primary Key, Auto-Increment
    id: Optional[int] = Field(default=None, primary_key=True)

    natural_key: str = Field(
        max_length=500,
        nullable=False,
        description="Stable deduplication key computed at ingestion (never in CSV)",
    )

    @staticmethod
    def compute_natural_key(
        transport_mode: "TransportModeEnum",
        name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        country_code: Optional[str] = None,
        iata_code: Optional[str] = None,
    ) -> str:
        """Python mirror of ``app/seed/seed_locations.py::_NATURAL_KEY_EXPR``.

        Keep the two shapes in lock-step — the seed runs this expression in
        Postgres for bulk UPSERT, while application code (ingestion, tests)
        calls this helper. A drift between them would make the same logical
        location dedupe to two different rows.

        Plane stations are uniquely keyed by IATA, so the fast path only
        needs ``transport_mode=plane`` + ``iata_code``. Every other path
        (train, or plane without iata) requires ``name``, ``latitude``,
        ``longitude``.
        """
        if transport_mode == TransportModeEnum.plane and iata_code:
            return f"plane:{iata_code}"
        if name is None or latitude is None or longitude is None:
            raise ValueError(
                "compute_natural_key requires name, latitude, longitude "
                "unless transport_mode=plane and iata_code is provided"
            )
        mode = "train" if transport_mode == TransportModeEnum.train else "plane"
        cc = (country_code or "").lower()
        normalized = re.sub(r"\s+", " ", name.strip().lower())
        return f"{mode}:{cc}:{normalized}:{latitude}:{longitude}"

    def __repr__(self) -> str:
        return (
            f"<Location id={self.id} "
            f"mode={self.transport_mode} "
            f"name={self.name} "
            f"({self.latitude}, {self.longitude}) "
            f"country={self.country_code}>"
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
    natural_key: str
