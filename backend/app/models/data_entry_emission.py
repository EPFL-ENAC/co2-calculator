"""Data entry emission models for storing computed emission results."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Float, ForeignKey
from sqlmodel import JSON, TIMESTAMP, Column, Field, Integer, SQLModel

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType


@dataclass
class FactorQuery:
    """Describes how to look up factors via classification query (Strategy B).

    Args:
        data_entry_type: Scopes the DB query to a specific data entry type.
        kind: Primary classification key (e.g. 'food', 'plane', building_name).
        subkind: Optional secondary classification key (e.g. cabin class, subcategory).
        context: Additional classification filters forwarded to the DB query
                 (e.g. ``{"category": "short_haul"}`` for flights,
                 ``{"country_code": "CH"}`` for trains).
        fallbacks: Fallback values for context keys when the exact match fails
                   (e.g. ``{"country_code": "RoW"}`` to fall back to a global factor).
    """

    data_entry_type: DataEntryTypeEnum
    kind: str | None = None
    subkind: str | None = None
    emission_type: EmissionType | None = (
        None  # Optional, can be used for additional filtering in repo queries
    )
    context: dict = field(default_factory=dict)
    fallbacks: dict = field(default_factory=dict)


@dataclass
class EmissionComputation:
    """Describes one emitted row and how to compute its kg_co2eq.

    Exactly one of ``factor_id`` (Strategy A) or ``factor_query`` (Strategy B)
    should be set.

    For simple formulas::

        kg_co2eq = ctx[quantity_key] * factor.values[formula_key]
                   * factor.values.get(multiplier_key, multiplier_default)

    For complex formulas, set ``formula_func`` and it takes precedence over
    the key-based approach::

        kg_co2eq = formula_func(ctx, factor.values)
    """

    emission_type: EmissionType

    # --- Factor retrieval ---
    # Strategy A: direct factor ID (primary_factor_id already resolved at creation)
    factor_id: int | None = None
    # Strategy B: classification query resolved at compute time
    factor_query: FactorQuery | None = None

    # --- Formula (key-based, simple) ---
    # Name of the factor value key giving the emission intensity
    formula_key: str = ""
    # Name of the context key giving the physical quantity
    quantity_key: str = ""
    # Optional second multiplier from factor values (e.g. "rfi_adjustement")
    multiplier_key: str | None = None
    # Value used when multiplier_key is absent from factor values
    multiplier_default: float = 1.0

    # --- Formula (callable, complex) ---
    # When set, takes precedence over key-based formula.
    # Signature: (ctx: dict, factor_values: dict) -> Optional[float]
    formula_func: Callable[[dict, dict], float | None] | None = None


####


class DataEntryEmissionBase(SQLModel):
    """Base data entry emission model with shared fields."""

    data_entry_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("data_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="Reference to the source data entry",
    )
    # EmissionType value
    emission_type_id: int = Field(
        nullable=False,
        index=True,
        description="Type of emission (equipment, food, waste, commute, etc.)",
    )
    # Primary factor used for calculation (main factor for traceability)
    primary_factor_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("factors.id", ondelete="CASCADE"), index=True
        ),
        description="Primary factor used for calculation (power, headcount,"
        "flight, etc.)",
    )
    # TODO: move to Decimal! (precision issues)
    kg_co2eq: float = Field(
        nullable=False,
        description="Computed emission value in kg CO2 equivalent",
    )
    additional_value: float | None = Field(
        default=None,
        sa_column=Column(
            Float,
            nullable=True,
            comment=(
                "Polymorphic physical quantity tied to this emission row. "
                "Unit is inferred from emission_type_id "
                "(e.g. km for commuting and travel, kg for food and waste)."
            ),
        ),
        description=(
            "Polymorphic physical quantity tied to this emission row. "
            "Unit is inferred from emission_type_id "
            "(e.g. km for commuting and travel, kg for food and waste)."
        ),
    )
    scope: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="Scope (1/2/3) for leaf rows; NULL for rollup rows",
    )
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Calculation inputs and factors_used array for full traceability",
    )
    computed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
        description="Timestamp when emission was computed",
    )


class DataEntryEmission(DataEntryEmissionBase, table=True):
    """Generic emission results table.

    Stores computed CO2 emissions for all module types. Supports:
    - Multiple emissions per data entry (headcount → food, waste, commute)
    - Single emission per data entry (equipment → equipment)
    - Multi-factor calculations (all factors stored in meta.factors_used)

    One data entry can produce N emission rows, one per emission_type.

    Factor storage:
    - primary_factor_id: Main calculation factor
        (for traceability and recalculation queries)
    - meta.factors_used: Array of all factors with roles
        [{id, role, factor_family, values}]

    For equipment calculations (2 factors):
    - primary_factor_id → power factor (watts)
    - meta.factors_used → [{role: 'primary', ...power},
        {role: 'emission'}]
    - Formula: kg_co2eq = annual_kwh x emission_factor.values.kg_co2eq_per_kwh

    For headcount calculations (1 factor per emission):
    - primary_factor_id → headcount factor for that emission_type
    - meta.factors_used → [{role: 'primary', ...headcount_factor}]
    - Formula: kg_co2eq = fte x factor.values.kg_co2eq_per_fte

    Category/treemaps: Use emission_type.name or emission_type.parent
    to derive categories (e.g., "professional_travel__planes__eco"
    ->  "Professional Travel")

    Versioning: All changes tracked via document_versions table.
    The row is always updated in place; history is in document_versions.

    Examples:
        Equipment emission (1 row):
            data_entry_id=42, emission_type_id=80100 (equipment__scientific),
            kg_co2eq=123.4, primary_factor_id=5 (power),
            meta={
                "annual_kwh": 3569.3,
                "factors_used": [
                    {"id": 5, "role": "primary",
                        "factor_family": "power", "values": {...}},
                    {"id": 10, "role": "emission",
                        "factor_family": "emission", "values": {...}}
                ]
            }

        Headcount emissions (4 rows):
            data_entry_id=77, emission_type_id=10000 (food), kg_co2eq=336.0,
            primary_factor_id=11 (food factor),
            meta={
                "fte": 0.8,
                "factors_used": [{"id": 11, "role": "primary", "values": {...}}]
            }
    """

    __tablename__ = "data_entry_emissions"

    id: int | None = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<DataEntryEmission data_entry={self.data_entry_id} "
            f"type={self.emission_type_id}: {self.kg_co2eq} kgCO2eq>"
        )
