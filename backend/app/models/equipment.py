"""Equipment inventory models for CO2 calculations."""

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class EquipmentBase(SQLModel):
    """Base equipment model with shared fields."""

    cost_center: str = Field(
        nullable=False,
        index=True,
        description="Cost center code (e.g., 'C1348')",
    )
    cost_center_description: Optional[str] = Field(
        default=None,
        description="Cost center French description",
    )
    name: str = Field(
        nullable=False,
        index=True,
        description="Equipment name/description",
    )
    category: str = Field(
        nullable=False,
        index=True,
        description="""Equipment category from source data
        (e.g., 'Audiovisual', 'Scientifical equipment')""",
    )
    submodule: str = Field(
        nullable=False,
        index=True,
        description="Equipment submodule grouping (e.g., 'scientific', 'it', 'other')",
    )
    equipment_class: str = Field(
        nullable=False,
        index=True,
        description="Equipment class",
    )
    sub_class: Optional[str] = Field(
        default=None,
        description="Equipment sub-class for more specific categorization",
    )
    service_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
        description="Date when equipment was put into service",
    )
    status: str = Field(
        default="In service",
        nullable=False,
        index=True,
        description="Equipment status (e.g., 'In service', 'Decommissioned')",
    )

    # Usage patterns (percentages or hours per week)
    active_usage_pct: Optional[float] = Field(
        default=None,
        description="Active usage as percentage of time (0-100)",
    )
    passive_usage_pct: Optional[float] = Field(
        default=None,
        description="Passive/standby usage as percentage of time (0-100)",
    )

    # Link to power factor used (if power values are derived from lookup)
    power_factor_id: Optional[int] = Field(
        default=None,
        foreign_key="power_factors.id",
        index=True,
        description="Power factor used for this equipment",
    )

    # Ownership and organization
    unit_id: int = Field(
        index=True,
        nullable=False,
        description="EPFL unit/department ID",
    )

    # Additional metadata
    equipment_metadata: Optional[dict] = Field(
        default=None,
        description="Additional equipment metadata (location, tags, etc.)",
        sa_column=Column(JSON, nullable=True),
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    created_by: Optional[str] = Field(
        default=None,
        index=True,
    )
    updated_by: Optional[str] = Field(
        default=None,
        index=True,
    )


class Equipment(EquipmentBase, table=True):
    """
    Equipment inventory for CO2 emissions calculations.

    Stores equipment metadata, usage patterns, and either:
    - Measured power consumption values (active_power_w, standby_power_w)
    - Reference to power factor for lookup (power_factor_id)

    Emissions are calculated separately and stored in EquipmentEmission table.
    """

    __tablename__ = "equipment"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<Equipment {self.id}:"
            f" {self.name} ({self.submodule}/{self.equipment_class})>"
        )


class EquipmentEmissionBase(SQLModel):
    """Base model for calculated equipment emissions with versioning."""

    equipment_id: int = Field(
        nullable=False,
        foreign_key="equipment.id",
        index=True,
        description="Reference to equipment",
    )

    # Calculated values
    annual_kwh: float = Field(
        nullable=False,
        description="Annual energy consumption in kWh",
    )
    kg_co2eq: float = Field(
        nullable=False,
        description="Annual CO2 emissions in kg CO2-equivalent",
    )

    # Versioning - tracks which factors were used
    emission_factor_id: int = Field(
        nullable=False,
        foreign_key="emission_factors.id",
        index=True,
        description="Emission factor version used for calculation",
    )
    power_factor_id: Optional[int] = Field(
        default=None,
        foreign_key="power_factors.id",
        index=True,
        description="Power factor version used (if applicable)",
    )

    # Calculation metadata
    formula_version: str = Field(
        default="v1_linear",
        nullable=False,
        description="Formula version identifier (hardcoded in calculation_service)",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when calculation was performed",
    )

    # Snapshot of input values at calculation time (for audit trail)
    calculation_inputs: dict = Field(
        default_factory=dict,
        description="Snapshot of usage and power values used in calculation",
        sa_column=Column(JSON),
    )

    # Flag for validity
    is_current: bool = Field(
        default=True,
        nullable=False,
        index=True,
        description="Whether this is the current/latest calculation for this equipment",
    )


class EquipmentEmission(EquipmentEmissionBase, table=True):
    """
    Calculated CO2 emissions for equipment with full versioning and audit trail.

    Stores:
    - Calculated annual energy consumption (kWh)
    - Calculated annual CO2 emissions (kg CO2-eq)
    - References to factor versions used
    - Timestamp and input snapshot for reproducibility

    Multiple versions can exist per equipment for historical tracking.
    Only one row per equipment should have is_current=True.

    When factors change or equipment is updated:
    1. Mark current row as is_current=False
    2. Calculate new values with new factor versions
    3. Insert new row with is_current=True
    """

    __tablename__ = "equipment_emissions"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        current = " [CURRENT]" if self.is_current else ""
        return (
            f"<EquipmentEmission {self.id}: equipment_id={self.equipment_id}, "
            f"{self.kg_co2eq:.2f} kgCO2eq{current}>"
        )
