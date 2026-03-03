"""Data entry emission models for storing computed emission results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from sqlalchemy import ForeignKey
from sqlmodel import JSON, TIMESTAMP, Column, Field, Integer, SQLModel

from app.models.data_entry import DataEntryTypeEnum


class EmissionType(int, Enum):
    """
    6-digit positional scheme: XX YY ZZ
      - XX = category      (01-99)
      - YY = subcategory   (01-99, 00 = category-level leaf)
      - ZZ = item          (01-99, 00 = subcategory-level leaf)

    Example:
      050000 = Professional Travel (category)
      050100 = Professional Travel > Trains (subcategory)
      050101 = Professional Travel > Trains > Class 1 (item)

    Possible to go 8-digits if needed
    (e.g., 05010101 for "Professional Travel > Trains > Class 1 > CFF")
    but currently 6 digits is sufficient for all planned levels.,
    """

    # -------------------------------------------------------------------------
    # Root categories (level 0)
    # not used directly emissions only for special factors
    # that are used in calculations but don't have their own emission rows
    # -------------------------------------------------------------------------
    energy = 1  # conversion factor for kWh → kgCO2eq

    # -------------------------------------------------------------------------
    # Additional Categories — flat leaves (no subcategory)
    # -------------------------------------------------------------------------
    food = 10000
    waste = 20000
    commuting = 30000
    grey_energy = 40000

    # -------------------------------------------------------------------------
    # Professional Travel
    # -------------------------------------------------------------------------
    professional_travel = 50000
    professional_travel__train = 50100
    professional_travel__train__class_1 = 50101
    professional_travel__train__class_2 = 50102
    professional_travel__plane = 50200
    professional_travel__plane__first = 50201
    professional_travel__plane__business = 50202
    professional_travel__plane__eco_plus = 50203
    professional_travel__plane__eco = 50204

    # -------------------------------------------------------------------------
    # Buildings
    # -------------------------------------------------------------------------
    buildings = 60000
    buildings__rooms = 60100
    buildings__rooms__lighting = 60101
    buildings__rooms__cooling = 60102
    buildings__rooms__ventilation = 60103
    buildings__rooms__heating_elec = 60104
    buildings__rooms__heating_thermal = 60105
    buildings__combustion = 60200  # scope 1 — direct fuel combustion

    # -------------------------------------------------------------------------
    # Process Emissions
    # -------------------------------------------------------------------------
    process_emissions = 70000
    process_emissions__ch4 = 70100
    process_emissions__co2 = 70200
    process_emissions__n2o = 70300
    process_emissions__refrigerants = 70400

    # -------------------------------------------------------------------------
    # Equipment
    # -------------------------------------------------------------------------
    equipment = 80000
    equipment__scientific = 80100
    equipment__it = 80200
    equipment__other = 80300

    # -------------------------------------------------------------------------
    # Purchases
    # -------------------------------------------------------------------------
    purchases = 90000
    purchases__goods_and_services = 90100
    purchases__scientific_equipment = 90200
    purchases__it_equipment = 90300
    purchases__consumable_accessories = 90400
    purchases__biological_chemical_gaseous = 90500
    purchases__services = 90600
    purchases__vehicles = 90700
    purchases__other = 90800
    purchases__additional = 90900

    # -------------------------------------------------------------------------
    # Research Facilities
    # -------------------------------------------------------------------------
    research_facilities = 100000
    research_facilities__facilities = 100100
    research_facilities__animal = 100200

    # -------------------------------------------------------------------------
    # External Clouds & AI
    # -------------------------------------------------------------------------
    external = 110000
    external__clouds = 110100
    external__clouds__virtualisation = 110101
    external__clouds__calcul = 110102
    external__clouds__stockage = 110103
    external__ai = 110200
    external__ai__provider_google = 110201
    external__ai__provider_mistral_ai = 110202
    external__ai__provider_anthropic = 110203
    external__ai__provider_openai = 110204
    external__ai__provider_cohere = 110205
    external__ai__provider_others = 110206

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @property
    def level(self) -> int:
        v = self.value
        if v % 100 != 0:
            return 2
        if v % 10000 != 0:
            return 1
        return 0

    @property
    def path(self) -> str:
        """Human-readable path derived from the enum name."""
        return self.name

    @property
    def parent_value(self) -> int | None:
        """Returns the int value of the logical parent, or None if root."""
        v = self.value
        if v % 100 != 0:
            # item → subcategory
            return (v // 100) * 100
        if v % 10000 != 0:
            # subcategory → category
            return (v // 10000) * 10000
        return None

    @property
    def parent(self) -> "EmissionType | None":
        pv = self.parent_value
        if pv is None:
            return None
        try:
            return EmissionType(pv)
        except ValueError:
            return None

    def children(self) -> list["EmissionType"]:
        """Returns direct children (one level down)."""
        results = []
        for e in type(self):
            if e.parent_value == self.value and e != self:
                results.append(e)
        return results


# =============================================================================
# Scope
# =============================================================================


class Scope(int, Enum):
    scope1 = 1
    scope2 = 2
    scope3 = 3


EMISSION_SCOPE: dict[EmissionType, Scope] = {
    # Additional Categories — scope 3
    EmissionType.food: Scope.scope3,
    EmissionType.waste: Scope.scope3,
    EmissionType.commuting: Scope.scope3,
    EmissionType.grey_energy: Scope.scope3,
    # Professional Travel — all scope 3
    EmissionType.professional_travel__train__class_1: Scope.scope3,
    EmissionType.professional_travel__train__class_2: Scope.scope3,
    EmissionType.professional_travel__plane__first: Scope.scope3,
    EmissionType.professional_travel__plane__business: Scope.scope3,
    EmissionType.professional_travel__plane__eco_plus: Scope.scope3,
    EmissionType.professional_travel__plane__eco: Scope.scope3,
    # Buildings — scope 2 except heating_thermal (scope 1)
    EmissionType.buildings__rooms__lighting: Scope.scope2,
    EmissionType.buildings__rooms__cooling: Scope.scope2,
    EmissionType.buildings__rooms__ventilation: Scope.scope2,
    EmissionType.buildings__rooms__heating_elec: Scope.scope2,
    EmissionType.buildings__rooms__heating_thermal: Scope.scope1,  # confirmed
    EmissionType.buildings__combustion: Scope.scope1,  # direct fuel combustion
    # Process Emissions — all scope 1
    EmissionType.process_emissions__ch4: Scope.scope1,
    EmissionType.process_emissions__co2: Scope.scope1,
    EmissionType.process_emissions__n2o: Scope.scope1,
    EmissionType.process_emissions__refrigerants: Scope.scope1,
    # Equipment — all scope 2
    EmissionType.equipment__scientific: Scope.scope2,
    EmissionType.equipment__it: Scope.scope2,
    EmissionType.equipment__other: Scope.scope2,
    # Purchases — scope 3 except additional (scope 1)
    EmissionType.purchases__goods_and_services: Scope.scope3,
    EmissionType.purchases__scientific_equipment: Scope.scope3,
    EmissionType.purchases__it_equipment: Scope.scope3,
    EmissionType.purchases__consumable_accessories: Scope.scope3,
    EmissionType.purchases__biological_chemical_gaseous: Scope.scope3,
    EmissionType.purchases__services: Scope.scope3,
    EmissionType.purchases__vehicles: Scope.scope3,
    EmissionType.purchases__other: Scope.scope3,
    EmissionType.purchases__additional: Scope.scope1,
    # Research Facilities — all scope 3
    EmissionType.research_facilities__facilities: Scope.scope3,
    EmissionType.research_facilities__animal: Scope.scope3,
    # External Clouds & AI — all scope 3
    EmissionType.external__clouds__virtualisation: Scope.scope3,
    EmissionType.external__clouds__calcul: Scope.scope3,
    EmissionType.external__clouds__stockage: Scope.scope3,
    EmissionType.external__ai__provider_google: Scope.scope3,
    EmissionType.external__ai__provider_mistral_ai: Scope.scope3,
    EmissionType.external__ai__provider_anthropic: Scope.scope3,
    EmissionType.external__ai__provider_openai: Scope.scope3,
    EmissionType.external__ai__provider_cohere: Scope.scope3,
    EmissionType.external__ai__provider_others: Scope.scope3,
}


def get_scope(e: EmissionType) -> Scope | None:
    """
    Returns the scope for a leaf emission type.
    For non-leaf (category/subcategory) nodes, returns None — scope only
    makes sense at the leaf level where data is actually recorded.
    """
    return EMISSION_SCOPE.get(e)


### =============================================================================
# DataEntryEmission model
# =============================================================================


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
    kind: Optional[str] = None
    subkind: Optional[str] = None
    emission_type: Optional[EmissionType] = (
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
    factor_id: Optional[int] = None
    # Strategy B: classification query resolved at compute time
    factor_query: Optional[FactorQuery] = None

    # --- Formula (key-based, simple) ---
    # Name of the factor value key giving the emission intensity
    formula_key: str = ""
    # Name of the context key giving the physical quantity
    quantity_key: str = ""
    # Optional second multiplier from factor values (e.g. "rfi_adjustement")
    multiplier_key: Optional[str] = None
    # Value used when multiplier_key is absent from factor values
    multiplier_default: float = 1.0

    # --- Formula (callable, complex) ---
    # When set, takes precedence over key-based formula.
    # Signature: (ctx: dict, factor_values: dict) -> Optional[float]
    formula_func: Optional[Callable[[dict, dict], Optional[float]]] = None


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
    primary_factor_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("factors.id", ondelete="CASCADE"), index=True
        ),
        description="Primary factor used for calculation (power, headcount,"
        "flight, etc.)",
    )
    # Scope (1, 2, or 3) for fast filtering/aggregation
    scope: Optional[int] = Field(
        default=None,
        description="Scope (1=direct, 2=indirect, 3=other) for aggregations",
    )
    # TODO: move to Decimal! (precision issues)
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
    - primary_factor_id: Main calculation factor
        (for traceability and recalculation queries)
    - meta.factors_used: Array of all factors with roles
        [{id, role, factor_family, values}]

    For equipment calculations (2 factors):
    - primary_factor_id → power factor (watts)
    - meta.factors_used → [{role: 'primary', ...power},
        {role: 'emission', ...energy_mix}]
    - Formula: kg_co2eq = annual_kwh x emission_factor.values.kg_co2eq_per_kwh

    For headcount calculations (1 factor per emission):
    - primary_factor_id → headcount factor for that emission_type
    - meta.factors_used → [{role: 'primary', ...headcount_factor}]
    - Formula: kg_co2eq = fte x factor.values.kg_co2eq_per_fte

    Scope-based queries:
    ```sql
    SELECT scope, SUM(kg_co2eq) FROM data_entry_emissions GROUP BY scope
    ```

    Category/treemaps: Use emission_type.path or emission_type.parent
    to derive categories (e.g., "professional_travel__planes__eco"
    ->  "Professional Travel")

    Versioning: All changes tracked via document_versions table.
    The row is always updated in place; history is in document_versions.

    Examples:
        Equipment emission (1 row):
            data_entry_id=42, emission_type_id=80100 (equipment__scientific),
            kg_co2eq=123.4, primary_factor_id=5 (power), scope=2,
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
            primary_factor_id=11 (food factor), scope=3,
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
            f"""type={self.emission_type_id}
                scope={self.scope}: {self.kg_co2eq} kgCO2eq>"""
        )
