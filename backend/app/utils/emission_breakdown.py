"""Pure functions for transforming raw emission data into chart-ready format.

Used by the emission-breakdown endpoint to serve both
ModuleCarbonFootprintChart and CarbonFootPrintPerPersonChart.

Uses emission_type.path for chart keys and emission_type.parent for categories.
"""

from app.models.data_entry_emission import EmissionType

# module_type_id → chart category (x-axis grouping)
# Building (module_type_id=3) is split by emission type; see _MODULE_EMISSION_CATEGORY
MODULE_TYPE_TO_CATEGORY: dict[int, str] = {
    4: "Equipment",
    6: "Research facilities",
    2: "Professional travel",
    5: "Purchases",
    7: "External cloud & AI",
    8: "Process Emissions",
}

# (module_type_id, emission_type_id) → category override
# Splits Building into two separate x-axis bars by emission type
# TODO fix this without harcoding!
_MODULE_EMISSION_CATEGORY: dict[tuple[int, int], str] = {
    (3, EmissionType.buildings__rooms): "Buildings energy consumption",
    (3, EmissionType.buildings__combustion): "Energy combustion",
    (3, EmissionType.grey_energy): "Buildings room",
}

# Headcount emission types — routed to additional_breakdown, not the main chart
HEADCOUNT_EMISSION_TYPES: set[int] = {
    EmissionType.food,
    EmissionType.waste,
    EmissionType.commuting,
    EmissionType.grey_energy,
}

# Headcount key names (camelCase for frontend)
HEADCOUNT_KEY_MAP: dict[int, str] = {
    EmissionType.food: "food",
    EmissionType.waste: "waste",
    EmissionType.commuting: "commuting",
    EmissionType.grey_energy: "greyEnergy",
}

# Maps module_type_id → per-person chart key
MODULE_TYPE_TO_PER_PERSON_KEY: dict[int, str] = {
    3: "infrastructure",
    4: "equipment",
    6: "researchFacilities",
    2: "professionalTravel",
    5: "purchases",
    7: "externalCloudAndAI",
    8: "processEmissions",
}

# Maps chart category → module_type_ids (for validation status lookup)
CATEGORY_TO_MODULE_TYPE_IDS: dict[str, list[int]] = {
    cat: [mid for mid, c in MODULE_TYPE_TO_CATEGORY.items() if c == cat]
    for cat in MODULE_TYPE_TO_CATEGORY.values()
}
for (_mid, _etype), _cat in _MODULE_EMISSION_CATEGORY.items():
    CATEGORY_TO_MODULE_TYPE_IDS.setdefault(_cat, [])
    if _mid not in CATEGORY_TO_MODULE_TYPE_IDS[_cat]:
        CATEGORY_TO_MODULE_TYPE_IDS[_cat].append(_mid)

# Headcount placeholder per-FTE values (kg CO2eq per FTE per year)
HEADCOUNT_PER_FTE_KG: dict[EmissionType, float] = {
    EmissionType.food: 420.0,
    EmissionType.waste: 125.0,
    EmissionType.commuting: 1375.0,
    EmissionType.grey_energy: 500.0,
}

# Category order for consistent display
MODULE_BREAKDOWN_ORDER = [
    # Scope 1
    "Process Emissions",
    "Buildings energy consumption",
    "Energy combustion",
    # Scope 2
    "Buildings room",
    "Equipment",
    # Scope 3
    "External cloud & AI",
    "Purchases",
    "Research facilities",
    "Professional travel",
]

# Expected chart keys per category for zero-filling.
# Now uses emission_type.name (path) for all modules.
CATEGORY_CHART_KEYS: dict[str, list[str]] = {
    "Process Emissions": ["process_emissions"],
    "Buildings energy consumption": ["energy"],
    "Energy combustion": ["combustion"],
    "Buildings room": ["grey_energy"],
    "Equipment": ["scientific", "it", "other"],
    "External cloud & AI": ["stockage", "virtualisation", "calcul", "ai_provider"],
    "Purchases": [
        "scientific_equipment",
        "it_equipment",
        "consumable_accessories",
        "biological_chemical_gaseous",
        "services",
        "vehicles",
        "other",
        "additional",
    ],
    "Research facilities": [],
    "Professional travel": ["plane", "train"],
}

ADDITIONAL_BREAKDOWN_ORDER = ["Commuting", "Food", "Waste", "Grey Energy"]

_HEADCOUNT_KEY_TO_CATEGORY: dict[str, str] = {
    "commuting": "Commuting",
    "food": "Food",
    "waste": "Waste",
    "greyEnergy": "Grey Energy",
}


def _is_headcount_only(emission_type_id: int, module_type_id: int) -> bool:
    """Return True if this emission should be routed to additional_breakdown.

    Headcount emission types (food, waste, commuting, grey_energy) are
    normally headcount-derived.  However, if the (module, emission_type)
    pair has a specific category override in _MODULE_EMISSION_CATEGORY,
    it is real module data (e.g. grey_energy on Building → "Buildings room").
    """
    if emission_type_id not in HEADCOUNT_EMISSION_TYPES:
        return False
    return (module_type_id, emission_type_id) not in _MODULE_EMISSION_CATEGORY


def _get_category_from_emission_type(emission_type: EmissionType) -> str | None:
    """Resolve the chart category from an EmissionType using parent.

    For leaf emission types, returns the parent category name.
    For example: "professional_travel__planes__eco" → "Professional Travel"
    """
    parent = emission_type.parent
    if parent is None:
        return None
    # Convert "professional_travel" → "Professional Travel"
    return parent.name.replace("_", " ").title()


def _to_chart_key_from_path(emission_type: EmissionType) -> str | None:
    """Derive chart key from emission_type.path.

    Uses the last part of the path for all modules.
    For example: "professional_travel__planes__eco" → "eco"
    """
    return emission_type.name.split("__")[-1]


def _get_category(module_type_id: int, emission_type_id: int) -> str | None:
    """Resolve the chart category for a (module, emission_type) pair.

    Checks _MODULE_EMISSION_CATEGORY overrides first (e.g. Building split),
    then falls back to MODULE_TYPE_TO_CATEGORY.
    """
    override = _MODULE_EMISSION_CATEGORY.get((module_type_id, emission_type_id))
    if override is not None:
        return override
    return MODULE_TYPE_TO_CATEGORY.get(module_type_id)


def _to_chart_key(
    emission_type_id: int,
    subcategory: str | None,
    module_type_id: int,
) -> str | None:
    """Derive chart key automatically from the row data.

    For modules in _SUBCATEGORY_PREFERRED_MODULES (Equipment, Travel),
    uses the subcategory field. For everything else, uses EmissionType.name.
    """
    # Use parent path for chart key
    try:
        emission_type = EmissionType(emission_type_id)
        # Get last part of path (e.g., "professional_travel__planes__eco" → "eco")
        return emission_type.name.split("__")[-1]
    except ValueError:
        return None


def build_chart_breakdown(
    rows: list[
        tuple[int, int, int | None, float | None]
    ],  # (module_type_id, emission_type_id, scope, kg_co2eq)
    total_fte: float = 0.0,
    headcount_validated: bool = False,
    validated_module_type_ids: set[int] | None = None,
) -> dict:
    """Transform raw DB emission rows into chart-ready format.

    Chart key is derived from emission_type.path (last segment).
    Category is derived from emission_type.parent.name.

    Args:
        rows: List of (module_type_id, emission_type_id, scope, kg_co2eq)
        total_fte: Total FTE count for per-person calculations
        headcount_validated: Whether headcount data is validated
        validated_module_type_ids: Set of validated module type IDs
    """
    # Accumulate by (category, chart_key)
    category_data: dict[str, dict[str, float]] = {}

    for module_type_id, emission_type_id, scope, kg_co2eq in rows:
        if kg_co2eq is None:
            continue
        if _is_headcount_only(emission_type_id, module_type_id):
            continue

        cat = _get_category(module_type_id, emission_type_id)
        if cat is None:
            continue

        chart_key = _to_chart_key(emission_type_id, None, module_type_id)
        if chart_key is None:
            continue

        if cat not in category_data:
            category_data[cat] = {}
        category_data[cat][chart_key] = (
            category_data[cat].get(chart_key, 0.0) + kg_co2eq
        )

    # Build module_breakdown: one dict per category, ordered
    module_breakdown: list[dict] = []
    for cat_name in MODULE_BREAKDOWN_ORDER:
        entry: dict[str, object] = {"category": cat_name}
        # Zero-fill expected keys
        for ck in CATEGORY_CHART_KEYS.get(cat_name, []):
            entry[ck] = 0.0
            entry[f"{ck}StdDev"] = 0.0
        # Overlay actual data (converted to tonnes)
        for chart_key, kg in category_data.get(cat_name, {}).items():
            entry[chart_key] = kg / 1000.0
            entry[f"{chart_key}StdDev"] = 0.0
        module_breakdown.append(entry)

    # Build additional_breakdown (headcount-derived)
    additional_breakdown: list[dict] = []
    headcount_totals_kg: dict[str, float] = {}

    if headcount_validated and total_fte > 0:
        for hc_emission_type, per_fte_kg in HEADCOUNT_PER_FTE_KG.items():
            hc_key = HEADCOUNT_KEY_MAP[hc_emission_type]
            headcount_totals_kg[hc_key] = per_fte_kg * total_fte

    for cat_name in ADDITIONAL_BREAKDOWN_ORDER:
        matched_key = next(
            (k for k, v in _HEADCOUNT_KEY_TO_CATEGORY.items() if v == cat_name),
            None,
        )
        if matched_key is None:
            continue
        tonnes = headcount_totals_kg.get(matched_key, 0.0) / 1000.0
        additional_breakdown.append(
            {
                "category": cat_name,
                matched_key: tonnes,
                f"{matched_key}StdDev": 0.0,
            }
        )

    # Build per_person_breakdown (module-level aggregation)
    per_person: dict[str, float] = {}

    module_totals_kg: dict[int, float] = {}
    for module_type_id, emission_type_id, _scope, kg_co2eq in rows:
        if kg_co2eq is None:
            continue
        if _is_headcount_only(emission_type_id, module_type_id):
            continue
        module_totals_kg[module_type_id] = (
            module_totals_kg.get(module_type_id, 0.0) + kg_co2eq
        )

    for mod_type_id, pp_key in MODULE_TYPE_TO_PER_PERSON_KEY.items():
        kg = module_totals_kg.get(mod_type_id, 0.0)
        per_person[pp_key] = (kg / total_fte / 1000.0) if total_fte > 0 else 0.0

    for hc_key, kg in headcount_totals_kg.items():
        per_person[hc_key] = (kg / total_fte / 1000.0) if total_fte > 0 else 0.0

    per_person["stdDev"] = 0

    # Total tonnes
    real_kg = sum(
        kg_co2eq
        for mtype, etype, _, kg_co2eq in rows
        if kg_co2eq is not None and not _is_headcount_only(etype, mtype)
    )
    headcount_kg = sum(headcount_totals_kg.values())
    total_tonnes = (real_kg + headcount_kg) / 1000.0

    validated_ids = validated_module_type_ids or set()
    validated_categories: list[str] = []
    for cat_name in MODULE_BREAKDOWN_ORDER:
        mod_ids = CATEGORY_TO_MODULE_TYPE_IDS.get(cat_name, [])
        if mod_ids and all(mid in validated_ids for mid in mod_ids):
            validated_categories.append(cat_name)

    if headcount_validated:
        validated_categories.extend(ADDITIONAL_BREAKDOWN_ORDER)

    return {
        "module_breakdown": module_breakdown,
        "additional_breakdown": additional_breakdown,
        "per_person_breakdown": per_person,
        "validated_categories": validated_categories,
        "total_tonnes_co2eq": total_tonnes,
        "total_fte": total_fte,
    }


def build_treemap(
    rows: list[tuple[str, float]],
) -> list[dict]:
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
