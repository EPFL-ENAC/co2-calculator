"""Emission type model for categorizing different types of emissions."""

from typing import Optional

from sqlmodel import Field, SQLModel


class EmissionTypeBase(SQLModel):
    """Base emission type model with shared fields."""

    code: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Unique code identifier (e.g., 'equipment', 'food', 'waste')",
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of this emission type",
    )


class EmissionType(EmissionTypeBase, table=True):
    """
    Emission type table for strict categorization of emissions.

    This provides a stable taxonomy for all emission calculations.
    All values are in kg_co2eq (implicit).

    Categories:
    - equipment: Equipment electricity consumption
    - food: Food-related emissions (catering, meals)
    - waste: Waste disposal emissions
    - commute: Commuting/transport emissions
    - grey_energy: Embodied energy in materials/infrastructure
    - professional_travel: Business travel (flights, trains, cars)
    - infrastructure: Building infrastructure (heating, cooling, etc.)
    - infrastructure_gas: Building gas consumption
    - unit_gas: Unit-level gas consumption
    - purchases: Procurement emissions
    - internal_services: Internal EPFL services (SCITAS, RCP, etc.)
    - external_cloud: External cloud services
    - research_core_facilities: Shared research infrastructure

    Chart grouping varies by module:
    - Equipment: group by data_entry_type (scientific, it, other)
    - Travel: group by data.travel_type (plane, train, car)
    - Headcount: group by emission_type (food, waste, commute, grey_energy)
    - Purchases: group by data_entry_type (bio_chemicals, consumables, etc.)
    """

    __tablename__ = "emission_types"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<EmissionType {self.code}>"
