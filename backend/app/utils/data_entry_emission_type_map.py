# =============================================================================
# LEGACY STRING MAPPING — for ctrl-F / ctrl-R migration
# =============================================================================
#
# Old reference                          → New reference
# ---------------------------------------------------------------------------
# EmissionType.energy                    → EmissionType.energy (kept)
# EmissionType.equipment                 → (removed — use resolve_emission_types)
# EmissionType.food                      → EmissionType.food                    (kept)
# EmissionType.waste                     → EmissionType.waste                   (kept)
# EmissionType.commuting                 → EmissionType.commuting               (kept)
# EmissionType.plane                     → (removed — use resolve_emission_types)
# EmissionType.train                     → (removed — use resolve_emission_types)
# EmissionType.stockage                  → EmissionType.external__clouds__stockage
# EmissionType.virtualisation            → EmissionType.external__clouds__virtualisation
# EmissionType.calcul                    → EmissionType.external__clouds__calcul
# EmissionType.ai_provider               → EmissionType.external__ai__provider
# EmissionType.process_emissions         → (rm — resolved dynamically \v emitted_gas)
# EmissionType.purchase                  → (rm — resolved per purchase subtype)
# EmissionType["calcul"]                 → EmissionType.external__clouds__calcul
# EmissionType["stockage"]               → EmissionType.external__clouds__stockage
# EmissionType["virtualisation"]         → EmissionType.external__clouds__virtualisation
#
# emission_type_id=EmissionType.purchase.value          → use resolve_emission_types()
# emission_type_id=EmissionType.plane.value             → use resolve_emission_types()
# emission_type_id=EmissionType.train.value             → use resolve_emission_types()
# emission_type_id=EmissionType.process_emissions.value → use resolve_emission_types()
#
# subcategory = DataEntryTypeEnum(...).name             → remove: now derived
# from EmissionType.path


# Define HeatingEnergyType locally (legacy compatibility)
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType

# =============================================================================
# DATA_ENTRY_TYPE → EMISSION_TYPE mapping  (1-to-many)
#
# Most DataEntryTypeEnum values map to a single EmissionType leaf.
# Some (member, building) map to multiple — one EmissionType per row emitted.
# Dynamic types (plane, train, process_emissions, external_clouds) are None
# here and resolved at runtime by resolve_emission_types() below.
# =============================================================================

FACTOR_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, list[EmissionType] | None] = {
    # --- Additional Categories ------------------------------------------------
    # member/student each produce N rows — one per factor applied (food, waste,
    # commuting). kg_co2eq per row comes from each factor's own
    # formula; no splitting needed.
    DataEntryTypeEnum.building: [EmissionType.buildings__rooms],
    # --- Professional Travel — one factor per haul/country, not per cabin -----
    DataEntryTypeEnum.plane: [EmissionType.professional_travel__plane],
    DataEntryTypeEnum.train: [EmissionType.professional_travel__train],
}

DATA_ENTRY_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, list[EmissionType] | None] = {
    # --- Additional Categories ------------------------------------------------
    # member/student each produce N rows — one per factor applied (food, waste,
    # commuting). kg_co2eq per row comes from each factor's own
    # formula; no splitting needed.
    DataEntryTypeEnum.member: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
    ],
    DataEntryTypeEnum.student: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
    ],
    # --- Professional Travel — resolved at runtime (cabin_class key) ----------
    DataEntryTypeEnum.plane: None,  # → _resolve_plane()
    DataEntryTypeEnum.train: None,  # → _resolve_train()
    # --- Buildings (resolved at runtime for room-type granularity) ---------
    DataEntryTypeEnum.building: None,  # → _resolve_building_rooms()
    DataEntryTypeEnum.energy_combustion: None,  # → _resolve_combustion()
    DataEntryTypeEnum.building_embodied_energy: [
        EmissionType.buildings__embodied_energy
    ],  # embodied energy for buildings, scope 3
    # --- Process Emissions — resolved at runtime (emitted_gas key) ------------
    DataEntryTypeEnum.process_emissions: None,  # → _resolve_process_emissions()
    # --- Equipment -----------------------------------------------------------
    DataEntryTypeEnum.scientific: [EmissionType.equipment__scientific],
    DataEntryTypeEnum.it: [EmissionType.equipment__it],
    DataEntryTypeEnum.other: [EmissionType.equipment__other],
    # --- Purchases -----------------------------------------------------------
    DataEntryTypeEnum.scientific_equipment: [
        EmissionType.purchases__scientific_equipment
    ],
    DataEntryTypeEnum.it_equipment: [EmissionType.purchases__it_equipment],
    DataEntryTypeEnum.consumable_accessories: [
        EmissionType.purchases__consumable_accessories
    ],
    DataEntryTypeEnum.biological_chemical_gaseous_product: [
        EmissionType.purchases__biological_chemical_gaseous
    ],
    DataEntryTypeEnum.services: [EmissionType.purchases__services],
    DataEntryTypeEnum.vehicles: [EmissionType.purchases__vehicles],
    DataEntryTypeEnum.other_purchases: [EmissionType.purchases__other],
    DataEntryTypeEnum.additional_purchases: None,
    # --- Research Facilities -------------------------------------------------
    DataEntryTypeEnum.research_facilities: [
        EmissionType.research_facilities__facilities
    ],
    DataEntryTypeEnum.mice_and_fish_animal_facilities: [
        EmissionType.research_facilities__animal
    ],
    # --- External Clouds — resolved at runtime (sub_kind key) ----------------
    DataEntryTypeEnum.external_clouds: None,  # → _resolve_clouds()
    # --- External AI ---------------------------------------------------------
    DataEntryTypeEnum.external_ai: [
        EmissionType.external__ai__provider_google,
        EmissionType.external__ai__provider_mistral_ai,
        EmissionType.external__ai__provider_anthropic,
        EmissionType.external__ai__provider_openai,
        EmissionType.external__ai__provider_cohere,
        EmissionType.external__ai__provider_others,
    ],  # provider is a subcategory, not path
}


# =============================================================================
# Runtime resolvers — for types that need the data payload to pick the leaf
# =============================================================================

_CLOUD_SUBKIND_MAP: dict[str, EmissionType] = {
    "virtualisation": EmissionType.external__clouds__virtualisation,
    "compute": EmissionType.external__clouds__calcul,
    "storage": EmissionType.external__clouds__stockage,
}

_AI_USE_MAP: dict[str, EmissionType] = {
    "google": EmissionType.external__ai__provider_google,
    "mistral_ai": EmissionType.external__ai__provider_mistral_ai,
    "anthropic": EmissionType.external__ai__provider_anthropic,
    "openai": EmissionType.external__ai__provider_openai,
    "cohere": EmissionType.external__ai__provider_cohere,
    "others": EmissionType.external__ai__provider_others,
}

_PLANE_CABIN_MAP: dict[str, EmissionType] = {
    "first": EmissionType.professional_travel__plane__first,
    "business": EmissionType.professional_travel__plane__business,
    "eco": EmissionType.professional_travel__plane__eco,
}

_TRAIN_CLASS_MAP: dict[str, EmissionType] = {
    "first": EmissionType.professional_travel__train__class_1,
    "second": EmissionType.professional_travel__train__class_2,
}

_PROCESS_GAS_MAP: dict[str, EmissionType] = {
    "ch4": EmissionType.process_emissions__ch4,
    "co2": EmissionType.process_emissions__co2,
    "n2o": EmissionType.process_emissions__n2o,
    "refrigerants": EmissionType.process_emissions__refrigerants,
    "refrigerant": EmissionType.process_emissions__refrigerants,  # CSV spelling
}


def _resolve_plane(data: dict) -> list[EmissionType] | None:
    # no default return non if no cabin_class
    cabin = (data.get("cabin_class") or "").lower()
    et = _PLANE_CABIN_MAP.get(cabin)
    return [et] if et else None


def _resolve_train(data: dict) -> list[EmissionType] | None:
    cabin = (data.get("cabin_class") or "").lower()
    et = _TRAIN_CLASS_MAP.get(cabin)
    return [et] if et else None


def _resolve_clouds(data: dict) -> list[EmissionType] | None:
    # not defaulting to calcul — if sub_kind is missing/unknown, better to skip than to

    service_type = (data.get("service_type") or "").lower()
    et = _CLOUD_SUBKIND_MAP.get(service_type)
    return [et] if et else None


def _resolve_ai(data: dict) -> list[EmissionType] | None:
    ai_provider = (data.get("provider") or "").lower().replace(" ", "_")
    et = _AI_USE_MAP.get(ai_provider)
    # default to "others" if provider is missing/unknown
    return [et] if et else [EmissionType.external__ai__provider_others]


_VALID_ROOM_TYPES: frozenset[str] = frozenset(
    {
        "office",
        "laboratories",
        "archives",
        "libraries",
        "auditoriums",
        "miscellaneous",
    }
)

_ENERGY_TYPES: list[str] = [
    "lighting",
    "cooling",
    "ventilation",
    "heating_elec",
    "heating_thermal",
]


def _resolve_building_rooms(
    data: dict,
) -> list[EmissionType] | None:
    """Resolve building data entry to room-type-specific emission types.

    If room_type is set, returns 8-digit WW-level types (one per energy).
    Otherwise falls back to 6-digit ZZ-level types.
    """
    room_type = (data.get("room_type") or "").lower()
    if room_type in _VALID_ROOM_TYPES:
        result = []
        for energy in _ENERGY_TYPES:
            name = f"buildings__rooms__{energy}__{room_type}"
            try:
                result.append(EmissionType[name])
            except KeyError:
                # fallback to parent energy type
                result.append(EmissionType[f"buildings__rooms__{energy}"])
        return result

    # No room_type — use generic ZZ-level types
    return [
        EmissionType.buildings__rooms__lighting,
        EmissionType.buildings__rooms__cooling,
        EmissionType.buildings__rooms__ventilation,
        EmissionType.buildings__rooms__heating_elec,
        EmissionType.buildings__rooms__heating_thermal,
    ]


_COMBUSTION_FUEL_MAP: dict[str, EmissionType] = {
    "natural_gas": EmissionType.buildings__combustion__natural_gas,
    "heating_oil": EmissionType.buildings__combustion__heating_oil,
    "biomethane": EmissionType.buildings__combustion__biomethane,
    "pellets": EmissionType.buildings__combustion__pellets,
    "forest_chips": EmissionType.buildings__combustion__forest_chips,
    "wood_logs": EmissionType.buildings__combustion__wood_logs,
}


def _resolve_combustion(data: dict) -> list[EmissionType] | None:
    name = (data.get("name") or "").lower().replace(" ", "_")
    et = _COMBUSTION_FUEL_MAP.get(name)
    if et:
        return [et]
    # fallback to generic combustion for unknown fuel types
    return [EmissionType.buildings__combustion]


_ADDITIONAL_PURCHASES_MAP: dict[str, EmissionType] = {
    "ln2": EmissionType.purchases__additional__ln2,
}


def _resolve_additional_purchases(
    data: dict,
) -> list[EmissionType] | None:
    name = (data.get("name") or "").lower().replace(" ", "_")
    et = _ADDITIONAL_PURCHASES_MAP.get(name)
    if et:
        return [et]
    return [EmissionType.purchases__additional]


def _resolve_process_emissions(data: dict) -> list[EmissionType] | None:
    gas = data.get("category", (data.get("kind", "") or "")).lower()
    et = _PROCESS_GAS_MAP.get(gas)
    return [et] if et else None  # None = unknown gas, caller should warn + skip


def _resolve_headcount_factor(data: dict) -> list[EmissionType] | None:
    """Resolve a headcount factor row to a single EmissionType leaf.

    Builds the enum name from headcount_category / headcount_class /
    headcount_subclass and tries the most specific match first, then
    falls back to less specific names.
    """
    category = (data.get("headcount_category") or "").strip().lower()
    cls = (data.get("headcount_class") or "").strip().lower()
    subclass = (data.get("headcount_subclass") or "").strip().lower()

    if not category:
        return None

    # Try most specific: category__class__subclass
    if cls and subclass:
        try:
            return [EmissionType[f"{category}__{cls}__{subclass}"]]
        except KeyError:
            pass

    # Try category__class
    if cls:
        try:
            return [EmissionType[f"{category}__{cls}"]]
        except KeyError:
            pass

    # Try category only
    try:
        return [EmissionType[category]]
    except KeyError:
        return None


_RUNTIME_RESOLVERS = {
    DataEntryTypeEnum.plane: _resolve_plane,
    DataEntryTypeEnum.train: _resolve_train,
    DataEntryTypeEnum.building: _resolve_building_rooms,
    DataEntryTypeEnum.energy_combustion: _resolve_combustion,
    DataEntryTypeEnum.additional_purchases: _resolve_additional_purchases,
    DataEntryTypeEnum.external_ai: _resolve_ai,
    DataEntryTypeEnum.external_clouds: _resolve_clouds,
    DataEntryTypeEnum.process_emissions: _resolve_process_emissions,
    DataEntryTypeEnum.member: _resolve_headcount_factor,
    DataEntryTypeEnum.student: _resolve_headcount_factor,
}


# =============================================================================
# Public API
# =============================================================================


def resolve_factor_emission_type(
    data_entry_type: DataEntryTypeEnum,
    factor: dict,
) -> EmissionType | None:
    """
    Returns the single EmissionType for a factor row of the given DataEntryTypeEnum.

    For most types this is a simple static mapping. For some (plane, train,
    process_emissions, external_clouds), the emission type depends on the data
    payload and is resolved at runtime by resolve_emission_types().

    This function is for factor loading only — it returns a single EmissionType
    (or None if unknown) because each factor row must be associated with exactly
    one EmissionType. For emission rows, use resolve_emission_types() which can
    return multiple types for a single data entry.
    """
    factor_resolver = FACTOR_TO_EMISSION_TYPES.get(data_entry_type)
    if factor_resolver is not None:
        if len(factor_resolver) == 0:
            return None  # known type that intentionally emits nothing
        if len(factor_resolver) > 1:
            raise ValueError(
                f"Expected exactly one emission_type for factor: {data_entry_type},"
                f" but got multiple: {factor_resolver}"
                f" for row: {factor}"
            )
        return factor_resolver[0]
    # else we default to runtime resolver for dynamic types
    # (plane, train, process_emissions, external_clouds)
    resolver = _RUNTIME_RESOLVERS.get(data_entry_type)
    types = None
    if resolver:
        types = resolver(factor)
    if types is None:
        # static mapping (covers both single and multiple types)
        types = DATA_ENTRY_TO_EMISSION_TYPES.get(data_entry_type)
    if types is None:
        return None  # unknown type, caller should log and skip
    if len(types) == 0:
        return None  # known type that intentionally emits nothing
    if len(types) > 1:
        raise ValueError(
            f"Expected exactly one emission type for factor of type {data_entry_type},"
            f" but got multiple: {types}"
            f" for row: {factor}"
        )
    return types[0]


def resolve_emission_types(
    data_entry_type: DataEntryTypeEnum,
    data: dict,
) -> list[EmissionType] | None:
    """
    Returns the list of EmissionType leaves for a given DataEntryTypeEnum.

    Returns:
      list[EmissionType]  — one or more emission types; create one row per entry
      []                  — known type that intentionally emits nothing
      None                — unhandled / unknown type — caller should log and skip

    Usage in DataEntryEmissionService:

      emission_types = resolve_emission_types(data_entry.data_entry_type,
        data_entry.data)
      if emission_types is None:
          logger.warning(f"Unhandled emission type: {data_entry.data_entry_type}")
          return []
      for emission_type in emission_types:
          # create one DataEntryEmission row, with subcategory=emission_type.path
          ...
    """
    static = DATA_ENTRY_TO_EMISSION_TYPES.get(data_entry_type)
    if static is not None:
        return static  # covers both [] and [EmissionType, ...]

    resolver = _RUNTIME_RESOLVERS.get(data_entry_type)
    if resolver:
        return resolver(data)

    return None  # truly unhandled
