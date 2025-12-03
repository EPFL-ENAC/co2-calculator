"""Emission factor model for CO2 calculations."""

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class EmissionFactorBase(SQLModel):
    """Base emission factor model with shared fields."""

    factor_name: str = Field(
        nullable=False,
        index=True,
        description="Name of the emission factor (e.g., 'swiss_electricity_mix')",
    )
    value: float = Field(
        nullable=False,
        description="Emission factor value in kgCO2eq/kWh",
    )
    version: int = Field(
        nullable=False,
        index=True,
        description="Version number of this factor",
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
    region: Optional[str] = Field(
        default=None,
        index=True,
        description="Geographic region (e.g., 'CH', 'EU', 'US')",
    )
    source: Optional[str] = Field(
        default=None,
        description="Data source or reference",
    )
    factor_metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (units, methodology, etc.)",
        sa_column=Column(JSON),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True)),
    )
    created_by: Optional[str] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="User who created this factor version",
    )


class EmissionFactor(EmissionFactorBase, table=True):
    """
    Emission factor for CO2 calculations with versioning support.

    Each factor change creates a new version row. The valid_to field is NULL
    for the current active version and populated when superseded.

    Example:
    - Version 1: swiss_electricity_mix = 0.125, valid_from='2024-01-01', valid_to=NULL
    - Version 2: swiss_electricity_mix = 0.120, valid_from='2025-01-01', valid_to=NULL
          (Version 1 valid_to is updated to '2024-12-31')
    """

    __tablename__ = "emission_factors"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<EmissionFactor {self.factor_name} v{self.version}: "
            f"{self.value} kgCO2eq/kWh>"
        )


class PowerFactorBase(SQLModel):
    """Base power factor model for equipment power consumption data."""

    submodule: str = Field(
        nullable=False,
        index=True,
        description="Equipment submodule grouping (e.g., 'scientific', 'it', 'other')",
    )
    sub_category: Optional[str] = Field(
        default=None,
        index=True,
        description="Equipment sub-category",
    )
    equipment_class: str = Field(
        nullable=False,
        index=True,
        description="Equipment class",
    )
    sub_class: Optional[str] = Field(
        default=None,
        index=True,
        description="Equipment sub-class for more specific categorization",
    )
    active_power_w: float = Field(
        nullable=False,
        description="Average power consumption in active mode (Watts)",
    )
    standby_power_w: float = Field(
        nullable=False,
        description="Average power consumption in standby/passive mode (Watts)",
    )
    version: int = Field(
        nullable=False,
        index=True,
        description="Version number of this power factor",
    )
    valid_from: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
        description="Date from which this power factor is valid",
    )
    valid_to: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
        description="Date until which this power factor is valid (NULL = current)",
    )
    source: Optional[str] = Field(
        default=None,
        description="Data source or reference for power measurements",
    )
    power_metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (measurement conditions, notes, etc.)",
        sa_column=Column(JSON),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    created_by: Optional[str] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="User who created this power factor version",
    )


class PowerFactor(PowerFactorBase, table=True):
    """
    Power consumption factors for different equipment types with versioning.

    Stores typical active and standby power consumption values for equipment
    categories. Used to estimate energy consumption when exact power data is
    not available.

    Lookup strategy: Match by submodule + equipment_class + sub_class (if provided).
    If no exact match, fallback to submodule + equipment_class.

    Example:
        submodule='scientific', equipment_class='Centrifugation',
        sub_class='Ultra centrifuges', active_power_w=1300, standby_power_w=130
    """

    __tablename__ = "power_factors"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        cls = f"{self.submodule}/{self.equipment_class}"
        if self.sub_class:
            cls += f"/{self.sub_class}"
        return f"<PowerFactor {cls} v{self.version}: {self.active_power_w}W active>"
