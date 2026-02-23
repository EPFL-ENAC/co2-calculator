"""Pure functions for transforming raw emission data into chart-ready format.

Used by the emission-breakdown endpoint to serve both
ModuleCarbonFootprintChart and CarbonFootPrintPerPersonChart.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.data_entry_emission import EmissionTypeEnum
from app.models.module_type import ModuleTypeEnum

mod = ModuleTypeEnum
etype = EmissionTypeEnum

# ---------------------------------------------------------------------------
# Single source of truth: one entry per (module, emission_type) mapping.
# Order within the list determines bar ordering in the chart.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChartBar:
    """One segment mapping: (module_type, emission_type) -> chart category."""

    category: str
    module_type: int
    emission_type: int | None
    chart_keys: tuple[str, ...] | None = None
    headcount: bool = False
    per_fte_kg: float | None = None


BARS: list[ChartBar] = [
    # Scope 1
    ChartBar("Process Emissions", mod.process_emissions, etype.process_emissions),
    ChartBar("Buildings energy consumption", mod.buildings, etype.energy),
    # Scope 2
    ChartBar("Energy combustion", mod.buildings, etype.combustion),
    ChartBar(
        "Equipment",
        mod.equipment_electric_consumption,
        etype.equipment,
        chart_keys=("scientific", "it", "other"),
    ),
    # Scope 3
    ChartBar("External cloud & AI", mod.external_cloud_and_ai, etype.stockage),
    ChartBar("External cloud & AI", mod.external_cloud_and_ai, etype.virtualisation),
    ChartBar("External cloud & AI", mod.external_cloud_and_ai, etype.calcul),
    ChartBar("External cloud & AI", mod.external_cloud_and_ai, etype.ai_provider),
    ChartBar("Purchases", mod.purchase, None),
    ChartBar("Research facilities", mod.internal_services, None),
    ChartBar("Professional travel", mod.professional_travel, etype.plane),
    ChartBar("Professional travel", mod.professional_travel, etype.train),
    # Headcount (additional breakdown)
    ChartBar(
        "Commuting", mod.commuting, etype.commuting, headcount=True, per_fte_kg=1375.0
    ),
    ChartBar("Food", mod.food, etype.food, headcount=True, per_fte_kg=420.0),
    ChartBar("Waste", mod.waste, etype.waste, headcount=True, per_fte_kg=125.0),
    ChartBar(
        "Grey Energy",
        mod.grey_energy,
        etype.grey_energy,
        headcount=True,
        per_fte_kg=500.0,
    ),
]

# ---------------------------------------------------------------------------
# Derived lookups (all from BARS)
# ---------------------------------------------------------------------------

MODULE_BREAKDOWN_ORDER: list[str] = list(
    dict.fromkeys(b.category for b in BARS if not b.headcount)
)
ADDITIONAL_BREAKDOWN_ORDER: list[str] = list(
    dict.fromkeys(b.category for b in BARS if b.headcount)
)

_LOOKUP: dict[tuple[int, int | None], ChartBar] = {
    (b.module_type, b.emission_type): b for b in BARS
}

_HEADCOUNT_ETYPES: set[int] = {
    b.emission_type for b in BARS if b.headcount and b.emission_type is not None
}

# TODO: replace mock per-FTE values with actual emission calculations
HEADCOUNT_PER_FTE_KG: dict[int, float] = {
    b.emission_type: b.per_fte_kg
    for b in BARS
    if b.headcount and b.emission_type is not None and b.per_fte_kg is not None
}

MODULE_TYPE_TO_PER_PERSON_KEY: dict[int, str] = {
    mod.buildings: "buildings",
    mod.equipment_electric_consumption: "equipment",
    mod.internal_services: "researchFacilities",
    mod.professional_travel: "professionalTravel",
    mod.purchase: "purchases",
    mod.external_cloud_and_ai: "externalCloudAndAI",
    mod.process_emissions: "processEmissions",
}

CATEGORY_TO_MODULE_TYPE_IDS: dict[str, list[int]] = {}
for _b in BARS:
    if _b.headcount:
        continue
    CATEGORY_TO_MODULE_TYPE_IDS.setdefault(_b.category, [])
    if _b.module_type not in CATEGORY_TO_MODULE_TYPE_IDS[_b.category]:
        CATEGORY_TO_MODULE_TYPE_IDS[_b.category].append(_b.module_type)


def _build_category_chart_keys() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {cat: [] for cat in MODULE_BREAKDOWN_ORDER}
    for b in BARS:
        if b.emission_type is None or b.category not in result:
            continue
        if b.chart_keys:
            result[b.category].extend(
                k for k in b.chart_keys if k not in result[b.category]
            )
        else:
            key = etype(b.emission_type).name
            if key not in result[b.category]:
                result[b.category].append(key)
    return result


CATEGORY_CHART_KEYS: dict[str, list[str]] = _build_category_chart_keys()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_headcount_only(emission_type_id: int, module_type_id: int) -> bool:
    """True when this emission should route to additional_breakdown."""
    if emission_type_id not in _HEADCOUNT_ETYPES:
        return False
    if module_type_id == mod.headcount:
        return True
    return (module_type_id, emission_type_id) not in _LOOKUP


def _resolve(module_type_id: int, emission_type_id: int) -> ChartBar | None:
    """Find the ChartBar for a (module, emission_type) pair, with fallback."""
    b = _LOOKUP.get((module_type_id, emission_type_id))
    if b is not None:
        return b
    return _LOOKUP.get((module_type_id, None))


def _chart_key_for(
    b: ChartBar, emission_type_id: int, subcategory: str | None
) -> str | None:
    """Derive the chart key for a row, using subcategory split when applicable."""
    if b.chart_keys and subcategory and subcategory.lower() in b.chart_keys:
        return subcategory.lower()
    try:
        return etype(emission_type_id).name
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# build_chart_breakdown — decomposed into focused steps
# ---------------------------------------------------------------------------

_Row = tuple[int, int, str | None, float | None]


def _accumulate_module_data(
    rows: list[_Row],
) -> dict[str, dict[str, float]]:
    """Sum kg values by (category, chart_key), skipping headcount rows."""
    category_data: dict[str, dict[str, float]] = {}
    for module_type_id, emission_type_id, subcategory, kg_co2eq in rows:
        if kg_co2eq is None:
            continue
        if _is_headcount_only(emission_type_id, module_type_id):
            continue
        b = _resolve(module_type_id, emission_type_id)
        if b is None:
            continue
        chart_key = _chart_key_for(b, emission_type_id, subcategory)
        if chart_key is None:
            continue
        bucket = category_data.setdefault(b.category, {})
        bucket[chart_key] = bucket.get(chart_key, 0.0) + kg_co2eq
    return category_data


def _build_module_breakdown(
    category_data: dict[str, dict[str, float]],
) -> list[dict]:
    """One dict per module category, zero-filled and converted to tonnes."""
    breakdown: list[dict] = []
    for cat_name in MODULE_BREAKDOWN_ORDER:
        entry: dict[str, object] = {"category": cat_name}
        for ck in CATEGORY_CHART_KEYS.get(cat_name, []):
            entry[ck] = 0.0
            entry[f"{ck}StdDev"] = 0.0
        for chart_key, kg in category_data.get(cat_name, {}).items():
            entry[chart_key] = kg / 1000.0
            entry[f"{chart_key}StdDev"] = 0.0
        breakdown.append(entry)
    return breakdown


def _build_additional_breakdown(
    total_fte: float,
    headcount_validated: bool,
) -> tuple[list[dict], dict[str, float]]:
    """Headcount-derived bars and their totals in kg (for per-person reuse)."""
    headcount_totals_kg: dict[str, float] = {}
    if headcount_validated and total_fte > 0:
        for etype_id, per_fte_kg in HEADCOUNT_PER_FTE_KG.items():
            headcount_totals_kg[etype(etype_id).name] = per_fte_kg * total_fte

    breakdown: list[dict] = []
    for b in BARS:
        if not b.headcount or b.emission_type is None:
            continue
        if b.category in [e["category"] for e in breakdown]:
            continue
        chart_key = etype(b.emission_type).name
        tonnes = headcount_totals_kg.get(chart_key, 0.0) / 1000.0
        breakdown.append(
            {
                "category": b.category,
                chart_key: tonnes,
                f"{chart_key}StdDev": 0.0,
            }
        )
    return breakdown, headcount_totals_kg


def _build_per_person(
    rows: list[_Row],
    total_fte: float,
    headcount_totals_kg: dict[str, float],
) -> dict[str, float]:
    """Per-person values: module-level kg / FTE / 1000."""
    module_totals_kg: dict[int, float] = {}
    for module_type_id, emission_type_id, _, kg_co2eq in rows:
        if kg_co2eq is None or _is_headcount_only(emission_type_id, module_type_id):
            continue
        module_totals_kg[module_type_id] = (
            module_totals_kg.get(module_type_id, 0.0) + kg_co2eq
        )

    per_person: dict[str, float] = {}
    for mod_type_id, pp_key in MODULE_TYPE_TO_PER_PERSON_KEY.items():
        kg = module_totals_kg.get(mod_type_id, 0.0)
        per_person[pp_key] = (kg / total_fte / 1000.0) if total_fte > 0 else 0.0
    for chart_key, kg in headcount_totals_kg.items():
        per_person[chart_key] = (kg / total_fte / 1000.0) if total_fte > 0 else 0.0
    per_person["stdDev"] = 0
    return per_person


def _compute_validated(
    validated_module_type_ids: set[int],
    headcount_validated: bool,
) -> list[str]:
    validated: list[str] = []
    for cat_name in MODULE_BREAKDOWN_ORDER:
        mod_ids = CATEGORY_TO_MODULE_TYPE_IDS.get(cat_name, [])
        if mod_ids and all(mid in validated_module_type_ids for mid in mod_ids):
            validated.append(cat_name)
    if headcount_validated:
        validated.extend(ADDITIONAL_BREAKDOWN_ORDER)
    return validated


def build_chart_breakdown(
    rows: list[_Row],
    total_fte: float = 0.0,
    headcount_validated: bool = False,
    validated_module_type_ids: set[int] | None = None,
) -> dict:
    """Transform raw DB emission rows into chart-ready format."""
    category_data = _accumulate_module_data(rows)
    additional_breakdown, headcount_totals_kg = _build_additional_breakdown(
        total_fte,
        headcount_validated,
    )

    real_kg = sum(
        kg
        for mtype, etype, _, kg in rows
        if kg is not None and not _is_headcount_only(etype, mtype)
    )
    total_tonnes = (real_kg + sum(headcount_totals_kg.values())) / 1000.0

    return {
        "module_breakdown": _build_module_breakdown(category_data),
        "additional_breakdown": additional_breakdown,
        "per_person_breakdown": _build_per_person(rows, total_fte, headcount_totals_kg),
        "validated_categories": _compute_validated(
            validated_module_type_ids or set(),
            headcount_validated,
        ),
        "total_tonnes_co2eq": total_tonnes,
        "total_fte": total_fte,
    }


# ---------------------------------------------------------------------------
# Treemap (unchanged)
# ---------------------------------------------------------------------------


def build_treemap(rows: list[tuple[str, float]]) -> list[dict]:
    """Build treemap data from (name, kg_co2eq) pairs.

    Returns: [{"name": str, "value": float, "percentage": float}]
    """
    total = sum(kg for _, kg in rows if kg > 0)
    if total <= 0:
        return []
    return [
        {
            "name": name,
            "value": kg,
            "percentage": (kg / total * 100) if total > 0 else 0.0,
        }
        for name, kg in rows
        if kg > 0
    ]
