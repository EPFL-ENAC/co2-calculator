"""Professional Travel models for CO2 calculations."""

from datetime import date as dt_date
from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, field_validator
from sqlalchemy import JSON, TIMESTAMP, Column, String
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.data_ingestion import IngestionMethod
from app.models.user import UserProvider

from .headcount import AuditMixin

# ==========================================
# 1. BASE MODEL
# ==========================================


class ProfessionalTravelBase(SQLModel):
    """
    Shared fields. These are required when Creating a new record.
    NOTE: 'id', 'provider', 'year', and 'audit' fields are excluded here.
    """

    # Traveler information
    traveler_id: Optional[int] = Field(
        default=None,
        description="Links to headcount.cf_user_id",
    )
    traveler_name: str = Field(
        max_length=255,
        description="Display name from headcount (dropdown from Headcount module)",
    )

    # Trip details
    origin_location_id: int = Field(
        foreign_key="locations.id",
        index=True,
        description="Reference to origin location (airport or train station)",
    )
    destination_location_id: int = Field(
        foreign_key="locations.id",
        index=True,
        description="Reference to destination location (airport or train station)",
    )
    departure_date: Optional[dt_date] = Field(
        default=None,
        description="Start date (OPTIONAL - approximate date of travel)",
    )

    @field_validator("departure_date", mode="before")
    @classmethod
    def parse_date(cls, v: Union[str, dt_date, None]) -> Optional[dt_date]:
        """Parse date from string, accepting both YYYY-MM-DD and YYYY/MM/DD formats."""
        if v is None or isinstance(v, dt_date):
            return v
        if isinstance(v, str):
            # Handle empty strings as None
            if not v.strip():
                return None
            # Replace slashes with dashes for ISO format parsing
            normalized = v.replace("/", "-")
            try:
                return dt_date.fromisoformat(normalized)
            except ValueError:
                raise ValueError(
                    f"Invalid date format: {v}. Expected YYYY-MM-DD or YYYY/MM/DD"
                )
        return v

    is_round_trip: bool = Field(
        default=False,
        description="If true, duplicates as 2 rows ",
    )

    # Transport information
    transport_mode: str = Field(
        max_length=50,
        description="'flight' | 'train' (Type: Plane or Train)",
    )
    class_: Optional[str] = Field(
        default=None,
        alias="class",
        sa_column=Column("class", String(50)),
        description="Train: class_1/class_2 | Plane: first/business/eco/eco_plus",
    )
    number_of_trips: int = Field(
        default=1,
        description="Number of trips (default: 1)",
    )

    # Organization & filtering
    unit_id: int = Field(
        index=True,
        description="Cost center/unit",
    )


# ==========================================
# 2. TABLE MODEL (Database)
# ==========================================


class ProfessionalTravel(ProfessionalTravelBase, AuditMixin, table=True):
    """
    The actual Database Table.
    Inherits Base fields + Audit fields + Adds ID, Provider, and Year.
    """

    __tablename__ = "professional_travels"

    # ID: Integer, Primary Key, Auto-Increment (Serial/Identity)
    id: Optional[int] = Field(default=None, primary_key=True)

    # traveler_id is optional - traveler_name is used as free-text field
    traveler_id: Optional[int] = Field(
        default=None,
        description="Links to headcount.cf_user_id (optional)",
    )

    # Provider: Set by system/logic, not by user input directly
    provider: UserProvider = Field(
        default=UserProvider.DEFAULT,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
        description="Sync source provider (accred, default, test)",
    )
    provider_source: IngestionMethod = Field(
        default=IngestionMethod.manual,
        sa_column=Column(
            SAEnum(IngestionMethod, name="ingestion_method_enum", native_enum=True),
            nullable=False,
        ),
        description="Sync source provider (accred, default, test)",
    )

    # Year: Calculated from departure_date for filtering
    year: int = Field(
        index=True,
        description="Calculated from departure_date for filtering",
    )

    def __repr__(self) -> str:
        return (
            f"<ProfessionalTravel id={self.id} "
            f"traveler={self.traveler_name} "
            f"origin_location_id={self.origin_location_id} "
            f"destination_location_id={self.destination_location_id}>"
        )


# ==========================================
# 3. API INPUT MODELS (DTOs)
# ==========================================


class ProfessionalTravelCreate(ProfessionalTravelBase):
    """
    Body payload for POST requests.
    Exact copy of Base (all fields required), but no ID/Audit/Provider/Year allowed.
    """

    pass


class ProfessionalTravelUpdate(SQLModel):
    """
    Body payload for PATCH requests.
    All fields are Optional. We do NOT inherit from Base to avoid
    required field conflicts.
    """

    traveler_id: Optional[int] = None
    traveler_name: Optional[str] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    departure_date: Optional[dt_date] = None

    @field_validator("departure_date", mode="before")
    @classmethod
    def parse_date(cls, v: Union[str, dt_date, None]) -> Optional[dt_date]:
        """Parse date from string, accepting both YYYY-MM-DD and YYYY/MM/DD formats."""
        if v is None or isinstance(v, dt_date):
            return v
        if isinstance(v, str):
            # Handle empty strings as None
            if not v.strip():
                return None
            # Replace slashes with dashes for ISO format parsing
            normalized = v.replace("/", "-")
            try:
                return dt_date.fromisoformat(normalized)
            except ValueError:
                raise ValueError(
                    f"Invalid date format: {v}. Expected YYYY-MM-DD or YYYY/MM/DD"
                )
        return v

    is_round_trip: Optional[bool] = None
    transport_mode: Optional[str] = None
    class_: Optional[str] = None
    number_of_trips: Optional[int] = None
    unit_id: Optional[int] = None
    provider: Optional[UserProvider] = None
    provider_source: Optional[IngestionMethod] = None


# ==========================================
# 4. API OUTPUT MODELS (DTOs)
# ==========================================


class ProfessionalTravelRead(ProfessionalTravelBase, AuditMixin):
    """
    Response schema for GET requests.
    Returns Data + ID + Provider + Year + Audit timestamps.
    """

    id: int
    provider: Optional[UserProvider] = None
    year: int


class ProfessionalTravelItemResponse(BaseModel):
    """
    Response schema for Professional Travel items in module submodule.
    """

    id: int = Field(..., description="Professional travel record identifier")
    traveler_name: str = Field(..., description="Display name of the traveler")
    origin_location_id: int = Field(..., description="Origin location ID")
    destination_location_id: int = Field(..., description="Destination location ID")
    origin: Optional[str] = Field(
        None, description="Origin location name (from locations table)"
    )
    destination: Optional[str] = Field(
        None, description="Destination location name (from locations table)"
    )
    transport_mode: str = Field(..., description="Transport mode: flight or train")
    class_: Optional[str] = Field(
        None, alias="class", description="Travel class"
    )  # alias for frontend compatibility
    departure_date: Optional[dt_date] = Field(None, description="Departure date")
    number_of_trips: int = Field(default=1, description="Number of trips")
    distance_km: Optional[float] = Field(
        None, description="Distance in km (from professional_travel_emissions table)"
    )
    kg_co2eq: Optional[float] = Field(
        None,
        description=(
            "CO2 emissions in kg CO2-eq (from professional_travel_emissions table)"
        ),
    )
    can_edit: bool = Field(
        ..., description="Whether the current user can edit this item"
    )


class ProfessionalTravelList(SQLModel):
    """
    Response schema for Paginated Lists.
    """

    items: List[ProfessionalTravelRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


# ==========================================
# 5. EMISSION MODEL (Versioned calculations)
# ==========================================


class ProfessionalTravelEmissionBase(SQLModel):
    """Base model for calculated professional travel emissions with versioning."""

    professional_travel_id: int = Field(
        nullable=False,
        foreign_key="professional_travels.id",
        index=True,
        description="Reference to professional travel record",
    )

    # Calculated values
    distance_km: float = Field(
        nullable=False,
        description="Distance in km (calculated from locations)",
    )
    kg_co2eq: float = Field(
        nullable=False,
        description="CO2 emissions in kg CO2-equivalent",
    )

    # Versioning - tracks which factors were used
    plane_impact_factor_id: Optional[int] = Field(
        default=None,
        foreign_key="plane_impact_factors.id",
        index=True,
        description="Plane impact factor version used (if transport_mode is flight)",
    )
    train_impact_factor_id: Optional[int] = Field(
        default=None,
        foreign_key="train_impact_factors.id",
        index=True,
        description="Train impact factor version used (if transport_mode is train)",
    )

    # Calculation metadata
    formula_version: str = Field(
        default="v1",
        nullable=False,
        description="Formula version identifier",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when calculation was performed",
    )

    # Snapshot of input values at calculation time (for audit trail)
    calculation_inputs: dict = Field(
        default_factory=dict,
        description="Snapshot of travel parameters used in calculation",
        sa_column=Column(JSON),
    )

    # Flag for validity
    is_current: bool = Field(
        default=True,
        nullable=False,
        index=True,
        description="Whether this is the current/latest calculation for this travel",
    )


class ProfessionalTravelEmission(ProfessionalTravelEmissionBase, table=True):
    """
    Calculated CO2 emissions for professional travel with full versioning
    and audit trail.

    Stores:
    - Calculated distance (km)
    - Calculated CO2 emissions (kg CO2-eq)
    - References to factor versions used
    - Timestamp and input snapshot for reproducibility

    Multiple versions can exist per travel record for historical tracking.
    Only one row per travel should have is_current=True.

    When factors change or travel is updated:
    1. Mark current row as is_current=False
    2. Calculate new values with new factor versions
    3. Insert new row with is_current=True
    """

    __tablename__ = "professional_travel_emissions"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        current = " [CURRENT]" if self.is_current else ""
        return (
            f"<ProfessionalTravelEmission {self.id}: "
            f"travel_id={self.professional_travel_id}, "
            f"{self.kg_co2eq:.2f} kgCO2eq{current}>"
        )
