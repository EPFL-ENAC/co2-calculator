"""Generic factor model for storing calculation coefficients across module types."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


class FactorBase(SQLModel):
    """Base factor model with shared fields."""

    emission_type_id: int = Field(
        foreign_key="emission_types.id",
        nullable=False,
        index=True,
        description="The emission type this factor produces or converts to",
    )
    is_conversion: bool = Field(
        default=False,
        nullable=False,
        index=True,
        description="True for conversion factors (e.g., energy mix kWh→kgCO2eq), False for calculation factors",
    )
    data_entry_type_id: Optional[int] = Field(
        default=None,
        foreign_key="data_entry_types.id",
        index=True,
        description="Scope to specific data entry type (e.g., scientific, student)",
    )
    classification: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Classification hierarchy as JSON (e.g., {class: 'X', sub_class: 'Y'})",
    )
    values: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Factor values as JSON (e.g., {active_power_w: 100, standby_power_w: 10})",
    )


class Factor(FactorBase, table=True):
    """
    Generic factor table for storing calculation coefficients.

    Each emission_type has its own calculation strategy:
    - equipment (id=2): Equipment power calculation (uses conversion factor for energy mix)
    - food (id=3): Headcount food calculation (FTE-based)
    - waste (id=4): Headcount waste calculation (FTE-based)
    - transport (id=5): Headcount transport/commute calculation (FTE-based)
    - grey_energy (id=6): Headcount grey energy calculation (FTE-based)
    - professional_travel (id=7): Flight/train calculation (distance-based)
    - energy (id=1): Conversion factor for kWh→kgCO2eq (is_conversion=true)

    Conversion factors (is_conversion=true):
    - Used by other calculations but don't have their own strategy
    - Example: Energy mix factors convert kWh to kgCO2eq for equipment calculations

    Lookup strategies by emission_type:
    - equipment: data_entry_type_id + classification->>'class' + classification->>'sub_class'
    - food/waste/transport/grey_energy: data_entry_type_id (member vs student)
    - professional_travel: classification->>'distance_band' + classification->>'cabin_class'
    - energy (conversion): classification->>'region' (e.g., 'CH', 'EU')

    Versioning: All changes tracked via document_versions table.

    Examples:
        Equipment factor:
            emission_type_id=2, is_conversion=false,
            data_entry_type_id=9 (scientific),
            classification={'class': 'Centrifugation', 'sub_class': 'Ultra centrifuges'},
            values={'active_power_w': 1300, 'standby_power_w': 130}

        Headcount food factor:
            emission_type_id=3, is_conversion=false,
            data_entry_type_id=1 (member),
            classification={},
            values={'kg_co2eq_per_fte': 420}

        Energy mix (conversion factor):
            emission_type_id=1, is_conversion=true,
            data_entry_type_id=100 (energy_mix),
            classification={'region': 'CH'},
            values={'kg_co2eq_per_kwh': 0.012}
    """

    __tablename__ = "factors"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        emission_type = f"emission_{self.emission_type_id}"
        conversion_flag = " [conversion]" if self.is_conversion else ""
        cls_str = ""
        if self.classification:
            cls_str = f" {self.classification}"
        return f"<Factor {emission_type}{conversion_flag}{cls_str}>"
