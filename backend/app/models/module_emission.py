"""Module emission models for storing computed emission results."""

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class ModuleEmissionBase(SQLModel):
    """Base module emission model with shared fields."""

    module_id: int = Field(
        foreign_key="modules.id",
        nullable=False,
        index=True,
        description="Reference to the source module",
    )
    emission_type_id: int = Field(
        foreign_key="emission_types.id",
        nullable=False,
        index=True,
        description="Type of emission (energy, food, waste, etc.)",
    )
    # Primary factor used for calculation (main factor for traceability)
    primary_factor_id: Optional[int] = Field(
        default=None,
        foreign_key="factors.id",
        index=True,
        description="Primary factor used for calculation (power, headcount, flight, etc.)",
    )
    # Subcategory for grouping (e.g., 'scientific', 'it', 'plane', 'food')
    subcategory: Optional[str] = Field(
        default=None,
        description="Subcategory for grouping emissions (scientific/it/other for equipment, plane/train for travel, emission_type for headcount)",
    )
    kg_co2eq: float = Field(
        nullable=False,
        description="Computed emission value in kg CO2 equivalent",
    )
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Calculation metadata and factors_used array for full traceability",
    )
    formula_version: Optional[str] = Field(
        default=None,
        description="Version identifier of the calculation formula used",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when emission was computed",
    )
    is_current: bool = Field(
        default=True,
        index=True,
        description="Whether this is the current emission value for this module",
    )


class ModuleEmission(ModuleEmissionBase, table=True):
    """
    Generic emission results table.

    Stores computed CO2 emissions for all module types. Supports:
    - Multiple emissions per module (headcount → food, waste, transport, grey_energy)
    - Single emission per module (equipment → equipment)
    - Historical tracking via is_current flag
    - Multi-factor calculations (all factors stored in meta.factors_used)

    One module can produce N emission rows, one per emission_type.

    Factor storage:
    - primary_factor_id: Main calculation factor (for traceability and recalculation queries)
    - meta.factors_used: Array of all factors with roles [{id, role, factor_family, values}]

    Subcategory field for consistent grouping:
    - Equipment: data_entry_type name (scientific, it, admin)
    - Travel: data.travel_type (plane, train, car)
    - Headcount: emission_type code (food, waste, transport, grey_energy)

    Traceability is achieved through:
    - primary_factor_id FK for recalculation queries
    - meta.factors_used array for full calculation audit trail
    - document_versions table for historical factor snapshots

    Examples:
        Equipment emission (1 row):
            module_id=42, emission_type_id=2 (equipment), kg_co2eq=123.4,
            primary_factor_id=5, subcategory='scientific',
            meta={
                "factors_used": [
                    {"id": 5, "role": "primary", "factor_family": "power", ...},
                    {"id": 10, "role": "emission", "factor_family": "emission", ...}
                ]
            }

        Headcount emissions (4 rows):
            module_id=77, emission_type_id=3 (food), kg_co2eq=336.0,
            primary_factor_id=11, subcategory='food'
    """

    __tablename__ = "module_emissions"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<ModuleEmission module={self.module_id} "
            f"type={self.emission_type_id} sub={self.subcategory}: {self.kg_co2eq} kgCO2eq>"
        )
