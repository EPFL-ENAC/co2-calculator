"""Data entry emission models for storing computed emission results."""

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class DataEntryEmissionBase(SQLModel):
    """Base data entry emission model with shared fields."""

    data_entry_id: int = Field(
        foreign_key="data_entries.id",
        nullable=False,
        index=True,
        description="Reference to the source data entry",
    )
    emission_type_id: int = Field(
        foreign_key="emission_types.id",
        nullable=False,
        index=True,
        description="Type of emission (equipment, food, waste, commute, etc.)",
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
        description="Calculation inputs and factors_used array for full traceability",
    )
    formula_version: Optional[str] = Field(
        default=None,
        description="Git SHA1 or version tag of the codebase used for calculation",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when emission was computed",
    )


class DataEntryEmission(DataEntryEmissionBase, table=True):
    """
    Generic emission results table.

    Stores computed CO2 emissions for all module types. Supports:
    - Multiple emissions per data entry (headcount → food, waste, commute, grey_energy)
    - Single emission per data entry (equipment → equipment)
    - Multi-factor calculations (all factors stored in meta.factors_used)

    One data entry can produce N emission rows, one per emission_type.

    Factor storage:
    - primary_factor_id: Main calculation factor (for traceability and recalculation queries)
    - meta.factors_used: Array of all factors with roles [{id, role, factor_family, values}]

    Subcategory field for consistent grouping:
    - Equipment: data_entry_type name (scientific, it, admin)
    - Travel: data.travel_type (plane, train, car)
    - Headcount: emission_type code (food, waste, transport, grey_energy)

    For equipment calculations (2 factors):
    - primary_factor_id → power factor (watts)
    - meta.factors_used → [{role: 'primary', ...power}, {role: 'emission', ...energy_mix}]
    - Formula: kg_co2eq = annual_kwh × emission_factor.values.kg_co2eq_per_kwh
    - subcategory: 'scientific', 'it', or 'admin'

    For headcount calculations (1 factor per emission):
    - primary_factor_id → headcount factor for that emission_type
    - meta.factors_used → [{role: 'primary', ...headcount_factor}]
    - Formula: kg_co2eq = fte × factor.values.kg_co2eq_per_fte
    - subcategory: 'food', 'waste', 'transport', or 'grey_energy'

    Grouping queries:
    ```sql
    SELECT emission_type_id, subcategory, SUM(kg_co2eq)
    FROM data_entry_emissions
    GROUP BY emission_type_id, subcategory
    ```

    Versioning: All changes tracked via document_versions table.
    The row is always updated in place; history is in document_versions.

    Examples:
        Equipment emission (1 row):
            data_entry_id=42, emission_type_id=2 (equipment), kg_co2eq=123.4,
            primary_factor_id=5 (power), subcategory='scientific',
            meta={
                "annual_kwh": 3569.3,
                "factors_used": [
                    {"id": 5, "role": "primary", "factor_family": "power", "values": {...}},
                    {"id": 10, "role": "emission", "factor_family": "emission", "values": {...}}
                ]
            }

        Headcount emissions (4 rows):
            data_entry_id=77, emission_type_id=3 (food), kg_co2eq=336.0,
            primary_factor_id=11 (food factor), subcategory='food',
            meta={
                "fte": 0.8,
                "factors_used": [{"id": 11, "role": "primary", "values": {...}}]
            }
    """

    __tablename__ = "data_entry_emissions"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<DataEntryEmission data_entry={self.data_entry_id} "
            f"type={self.emission_type_id} sub={self.subcategory}: {self.kg_co2eq} kgCO2eq>"
        )
