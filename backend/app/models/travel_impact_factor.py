"""Travel impact factor models for CO2 calculations.

PlaneImpactFactor: Impact factors for plane travel by haul category.
TrainImpactFactor: Impact factors for train travel by country.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import TIMESTAMP, Column, Field, SQLModel

from .headcount import AuditMixin

# ==========================================
# 1. PLANE IMPACT FACTOR
# ==========================================


class PlaneImpactFactorBase(SQLModel):
    """
    Base model for plane impact factors.
    Stores impact scores and RFI adjustments by haul category.
    """

    factor_type: str = Field(
        default="plane",
        max_length=50,
        nullable=False,
        index=True,
        description="Factor type: 'plane'",
    )
    category: str = Field(
        max_length=50,
        nullable=False,
        index=True,
        description=(
            "Haul category: 'very_short_haul', 'short_haul', 'medium_haul', 'long_haul'"
        ),
    )
    impact_score: float = Field(
        nullable=False,
        description="Impact score in kg CO2-Eq per passenger-km",
    )
    rfi_adjustment: float = Field(
        nullable=False,
        description="Radiative Forcing Index (RFI) adjustment factor",
    )
    min_distance: Optional[float] = Field(
        default=None,
        nullable=True,
        description="Minimum distance in km for this category (None = no minimum)",
    )
    max_distance: Optional[float] = Field(
        default=None,
        nullable=True,
        description="Maximum distance in km for this category (None = no maximum)",
    )
    valid_from: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
        description="Date from which this factor is valid",
    )
    valid_to: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
        description="Date until which this factor is valid (NULL = current)",
    )
    source: Optional[str] = Field(
        default=None,
        description="Data source or reference",
    )


class PlaneImpactFactor(PlaneImpactFactorBase, AuditMixin, table=True):
    """
    Database table for plane impact factors by haul category.

    Categories with distance ranges:
    - very_short_haul: <800km (min_distance=None, max_distance=800)
    - short_haul: 800-1500 km (min_distance=800, max_distance=1500)
    - medium_haul: 1500-4000 km (min_distance=1500, max_distance=4000)
    - long_haul: >4000km (min_distance=4000, max_distance=None)
    """

    __tablename__ = "plane_impact_factors"

    id: Optional[int] = Field(default=None, primary_key=True)

    def __repr__(self) -> str:
        return (
            f"<PlaneImpactFactor id={self.id} "
            f"category={self.category} "
            f"impact={self.impact_score} "
            f"rfi={self.rfi_adjustment}>"
        )


# ==========================================
# 2. TRAIN IMPACT FACTOR
# ==========================================


class TrainImpactFactorBase(SQLModel):
    """
    Base model for train impact factors.
    Stores impact scores by country code.
    """

    countrycode: str = Field(
        max_length=10,
        nullable=False,
        index=True,
        description=(
            "ISO country code (e.g., 'CH', 'FR', 'DE', 'IT', 'AT') "
            "or 'RoW' for Rest of World"
        ),
    )
    impact_score: float = Field(
        nullable=False,
        description="Impact score in kg CO2-Eq per passenger-km",
    )
    valid_from: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
        description="Date from which this factor is valid",
    )
    valid_to: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
        description="Date until which this factor is valid (NULL = current)",
    )
    source: Optional[str] = Field(
        default=None,
        description="Data source or reference",
    )


class TrainImpactFactor(TrainImpactFactorBase, AuditMixin, table=True):
    """
    Database table for train impact factors by country.

    Countries:
    - CH: Switzerland (fleet average)
    - FR: France
    - DE: Germany
    - IT: Italy
    - AT: Austria
    - RoW: Rest of World (fallback for countries not listed)

    Join with locations table using countrycode field.
    """

    __tablename__ = "train_impact_factors"

    id: Optional[int] = Field(default=None, primary_key=True)

    def __repr__(self) -> str:
        return (
            f"<TrainImpactFactor id={self.id} "
            f"countrycode={self.countrycode} "
            f"impact={self.impact_score}>"
        )
