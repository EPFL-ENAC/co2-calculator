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
    (3, EmissionType.buildings__rooms): "Buildings room",
    (3, EmissionType.buildings__rooms__heating_thermal): "Buildings energy combustion",
    (3, EmissionType.buildings__combustion): "Buildings energy combustion",
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
    3: "buildings",
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
    "Buildings energy combustion",
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
    "Buildings energy combustion": ["heating_thermal", "combustion"],
    "Buildings room": ["lighting", "cooling", "ventilation", "heating_elec"],
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
    # 1) Exact override (module + emission type)
    override = _MODULE_EMISSION_CATEGORY.get((module_type_id, emission_type_id))
    if override is not None:
        return override

    # 2) Ancestor override (module + parent emission types)
    #    Required for leaves like buildings__rooms__lighting which should
    #    inherit the category from buildings__rooms.
    emission_type = _resolve_emission_type(emission_type_id)
    parent = emission_type.parent if emission_type is not None else None
    while parent is not None:
        inherited = _MODULE_EMISSION_CATEGORY.get((module_type_id, parent.value))
        if inherited is not None:
            return inherited
        parent = parent.parent

    # 3) Generic module-level fallback
    return MODULE_TYPE_TO_CATEGORY.get(module_type_id)


def _resolve_emission_type(emission_type_id: int) -> EmissionType | None:
    """Safely convert raw emission_type_id into EmissionType enum."""
    try:
        return EmissionType(emission_type_id)
    except ValueError:
        return None


def _num(entry: dict[str, object], key: str) -> float:
    value = entry.get(key, 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _node_value(node: dict[str, object]) -> float:
    value = node.get("value", 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _sum_node_values(nodes: list[dict[str, object]]) -> float:
    total = 0.0
    for node in nodes:
        total += _node_value(node)
    return total


def _sum_object_values(values: list[object]) -> float:
    total = 0.0
    for value in values:
        if isinstance(value, bool):
            total += float(value)
            continue
        if isinstance(value, (int, float, str)):
            try:
                total += float(value)
            except (TypeError, ValueError):
                continue
    return total


def _primary_or_sum(
    entry: dict[str, object], primary: str, fallback: list[str]
) -> float:
    primary_value = _num(entry, primary)
    if primary_value != 0:
        return primary_value
    return sum(_num(entry, key) for key in fallback)


def _apply_chart_aggregates(entry: dict[str, object], category_name: str) -> None:
    """Add canonical chart keys so frontend can consume backend-ready rows."""
    if category_name == "Process Emissions":
        entry["process_emissions"] = _primary_or_sum(
            entry, "process_emissions", ["co2", "ch4", "n2o", "refrigerants"]
        )
        entry["process_emissionsStdDev"] = _primary_or_sum(
            entry,
            "process_emissionsStdDev",
            ["co2StdDev", "ch4StdDev", "n2oStdDev", "refrigerantsStdDev"],
        )
        return

    if category_name == "External cloud & AI":
        entry["clouds"] = _primary_or_sum(
            entry, "clouds", ["stockage", "virtualisation", "calcul"]
        )
        entry["cloudsStdDev"] = _primary_or_sum(
            entry,
            "cloudsStdDev",
            ["stockageStdDev", "virtualisationStdDev", "calculStdDev"],
        )
        entry["ai"] = _primary_or_sum(
            entry,
            "ai",
            [
                "ai_provider",
                "provider_others",
                "provider_google",
                "provider_mistral_ai",
                "provider_anthropic",
                "provider_openai",
                "provider_cohere",
            ],
        )
        entry["aiStdDev"] = _primary_or_sum(
            entry,
            "aiStdDev",
            [
                "ai_providerStdDev",
                "provider_othersStdDev",
                "provider_googleStdDev",
                "provider_mistral_aiStdDev",
                "provider_anthropicStdDev",
                "provider_openaiStdDev",
                "provider_cohereStdDev",
            ],
        )
        entry["ai_provider"] = _primary_or_sum(
            entry,
            "ai_provider",
            [
                "provider_others",
                "provider_google",
                "provider_mistral_ai",
                "provider_anthropic",
                "provider_openai",
                "provider_cohere",
            ],
        )
        entry["ai_providerStdDev"] = _primary_or_sum(
            entry,
            "ai_providerStdDev",
            [
                "provider_othersStdDev",
                "provider_googleStdDev",
                "provider_mistral_aiStdDev",
                "provider_anthropicStdDev",
                "provider_openaiStdDev",
                "provider_cohereStdDev",
            ],
        )
        return

    if category_name == "Professional travel":
        entry["plane"] = _primary_or_sum(
            entry, "plane", ["eco", "eco_plus", "business", "first"]
        )
        entry["planeStdDev"] = _primary_or_sum(
            entry,
            "planeStdDev",
            ["ecoStdDev", "eco_plusStdDev", "businessStdDev", "firstStdDev"],
        )
        entry["train"] = _primary_or_sum(entry, "train", ["class_1", "class_2"])
        entry["trainStdDev"] = _primary_or_sum(
            entry, "trainStdDev", ["class_1StdDev", "class_2StdDev"]
        )


def _apply_percentages(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    total = _sum_node_values(nodes)
    if total <= 0:
        return nodes

    out: list[dict[str, object]] = []
    for node in nodes:
        value = _node_value(node)
        enriched: dict[str, object] = {**node, "percentage": (value / total) * 100.0}
        children = node.get("children")
        if isinstance(children, list) and children:
            child_nodes = [c for c in children if isinstance(c, dict)]
            enriched["children"] = _apply_percentages(child_nodes)
        out.append(enriched)
    return out


def _build_category_treemap_nodes(
    values_tonnes: dict[str, float],
    parent_map: dict[str, str],
) -> list[dict[str, object]]:
    leaves = [
        {"name": key, "value": value}
        for key, value in values_tonnes.items()
        if value > 0.0
    ]
    if not leaves:
        return []

    parent_to_children: dict[str, list[dict[str, object]]] = {}
    for leaf in leaves:
        leaf_name = str(leaf["name"])
        parent = parent_map.get(leaf_name)
        if not parent:
            continue
        parent_to_children.setdefault(parent, []).append(dict(leaf))

    grouped_children: list[dict[str, object]] = []
    consumed_children: set[str] = set()
    for parent_name, child_nodes in parent_to_children.items():
        if not child_nodes:
            continue
        consumed_children.update(str(node["name"]) for node in child_nodes)
        grouped_children.append(
            {
                "name": parent_name,
                "value": _sum_object_values(
                    [node.get("value", 0.0) for node in child_nodes]
                ),
                "children": child_nodes,
            }
        )

    parent_keys = set(parent_to_children.keys())
    for leaf in leaves:
        leaf_name = str(leaf["name"])
        if leaf_name not in consumed_children and leaf_name not in parent_keys:
            grouped_children.append(dict(leaf))

    return _apply_percentages(grouped_children)


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
    # Per-category child -> parent map derived from EmissionType hierarchy.
    category_parents: dict[str, dict[str, str]] = {}

    for module_type_id, emission_type_id, scope, kg_co2eq in rows:
        if kg_co2eq is None:
            continue
        if _is_headcount_only(emission_type_id, module_type_id):
            continue

        cat = _get_category(module_type_id, emission_type_id)
        if cat is None:
            continue

        emission_type = _resolve_emission_type(emission_type_id)
        if emission_type is None:
            continue

        chart_key = _to_chart_key_from_path(emission_type)
        if chart_key is None:
            continue

        if cat not in category_data:
            category_data[cat] = {}
        if cat not in category_parents:
            category_parents[cat] = {}
        category_data[cat][chart_key] = (
            category_data[cat].get(chart_key, 0.0) + kg_co2eq
        )

        # Preserve emission hierarchy for treemap rendering:
        # category (level 0) -> subcategory (level 1) -> item (level 2).
        if (
            emission_type is not None
            and emission_type.level == 2
            and emission_type.parent is not None
        ):
            parent_key = emission_type.parent.name.split("__")[-1]
            category_data[cat][parent_key] = (
                category_data[cat].get(parent_key, 0.0) + kg_co2eq
            )
            category_parents[cat][chart_key] = parent_key

    # Build module_breakdown: one dict per category, ordered
    module_breakdown: list[dict] = []
    module_treemap: list[dict[str, object]] = []
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
        _apply_chart_aggregates(entry, cat_name)
        module_breakdown.append(entry)

        values_tonnes = {
            key: value / 1000.0
            for key, value in category_data.get(cat_name, {}).items()
        }
        treemap_children = _build_category_treemap_nodes(
            values_tonnes=values_tonnes,
            parent_map=category_parents.get(cat_name, {}),
        )
        if treemap_children:
            module_treemap.append(
                {
                    "name": cat_name,
                    "value": _sum_object_values(
                        [child.get("value", 0.0) for child in treemap_children]
                    ),
                    "children": treemap_children,
                }
            )

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
        "module_breakdown_parents": category_parents,
        "module_treemap": module_treemap,
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
