"""Generic factor model for storing calculation coefficients across module types."""

from typing import Optional

from sqlalchemy import Index
from sqlmodel import JSON, Column, Field, SQLModel


class FactorBase(SQLModel):
    """Base factor model with shared fields."""

    # EmissionType value
    emission_type_id: int = Field(
        nullable=False,
        index=True,
        description="The emission type this factor produces or converts to",
    )
    # it used to be optional, but now all factors are scoped to a data entry type
    data_entry_type_id: int = Field(
        default=None,
        index=True,
        description="""Scope to specific data entry type (e.g., scientific, student)""",
    )
    classification: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="""Classification hierarchy as JSON
            (e.g., {'class': 'Centrifugation', 'sub_class': 'Ultra centrifuges'})""",
    )
    values: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="""Factor values as JSON
            (e.g., {active_power_w: 100, standby_power_w: 10})""",
    )
    year: Optional[int] = Field(
        default=None,
        nullable=True,  # Initially nullable for migration, will enforce NOT NULL later
        index=True,
        description="""Year for which this factor applies.
            Enables year-specific factor uploads and calculations.
            Allows tracking historical factors and annual updates.""",
    )


class Factor(FactorBase, table=True):
    """
    Generic factor table for storing calculation coefficients.

    Each emission_type has its own calculation strategy:
    - equipment (id=2): Equipment power calculation
        (energy mix factor stored directly in CSV as ef_kg_co2eq_per_kwh)
    - food (id=3): Headcount food calculation (FTE-based)
    - waste (id=4): Headcount waste calculation (FTE-based)
    - transport (id=5): Headcount transport/commute calculation (FTE-based)
    - professional_travel (id=7): Flight/train calculation (distance-based)

    Note: emission_type_id=1 (energy conversion) has been removed.
    Energy mix factors are now stored directly in equipment factors CSV
    as ef_kg_co2eq_per_kwh column, eliminating the need for separate
    conversion factors.

    Lookup strategies by emission_type:
    - equipment: data_entry_type_id
        + classification->>'class' + classification->>'sub_class'
        + values include ef_kg_co2eq_per_kwh for energy mix
    - food/waste/transport: data_entry_type_id (member vs student)
    - professional_travel:
        classification->>'distance_band' + classification->>'cabin_class'

    Versioning: All changes tracked via document_versions table.
    Year Scoping: Factors are now scoped to a specific year, enabling
        annual factor updates and historical tracking. All factor lookups
        should include year filtering to ensure correct calculations.

    Examples:
        Equipment factor:
            emission_type_id=2,
            data_entry_type_id=9 (scientific), year=2025,
            classification={'class': 'Centrifugation',
            'sub_class': 'Ultra centrifuges'},
            values={'active_power_w': 1300, 'standby_power_w': 130,
                   'ef_kg_co2eq_per_kwh': 0.045}

        Headcount food factor:
            emission_type_id=3,
            data_entry_type_id=1 (member), year=2025,
            classification={},
            values={'kg_co2eq_per_fte': 420}
    """

    __tablename__ = "factors"
    __table_args__ = (
        Index(
            "ix_factors_data_entry_type_year",
            "data_entry_type_id",
            "year",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        emission_type = f"emission_{self.emission_type_id}"
        cls_str = ""
        if self.classification:
            cls_str = f" {self.classification}"
        return f"<Factor {emission_type}{cls_str}>"
