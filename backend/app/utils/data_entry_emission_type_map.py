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
# EmissionType.grey_energy               → EmissionType.grey_energy             (kept)
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

DATA_ENTRY_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, list[EmissionType] | None] = {
    # --- Additional Categories ------------------------------------------------
    # member/student each produce N rows — one per factor applied (food, waste,
    # commuting, grey_energy). kg_co2eq per row comes from each factor's own
    # formula; no splitting needed. Grey_energy rows will be added once factors exist.
    DataEntryTypeEnum.member: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
        EmissionType.grey_energy,
    ],
    DataEntryTypeEnum.student: [
        EmissionType.food,
        EmissionType.waste,
        EmissionType.commuting,
        EmissionType.grey_energy,
    ],
    # --- Professional Travel — resolved at runtime (cabin_class key) ----------
    DataEntryTypeEnum.plane: None,  # → _resolve_plane()
    DataEntryTypeEnum.train: None,  # → _resolve_train()
    # --- Buildings (dynamic: kg_co2eq bypass → single aggregate row) ---------
    DataEntryTypeEnum.building: None,  # → _resolve_building_data_entry()
    DataEntryTypeEnum.energy_combustion: [
        EmissionType.buildings__combustion
    ],  # scope 1
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
    DataEntryTypeEnum.additional_purchases: [EmissionType.purchases__additional],
    # --- Research Facilities -------------------------------------------------
    DataEntryTypeEnum.research_facilities: [
        EmissionType.research_facilities__facilities
    ],
    DataEntryTypeEnum.mice_and_fish_animal_facilities: [
        EmissionType.research_facilities__animal
    ],
    DataEntryTypeEnum.other_research_facilities: [
        EmissionType.research_facilities__facilities
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
    # --- Internal / special --------------------------------------------------
    # energy_mix is a conversion factor only, never produces emission rows
    DataEntryTypeEnum.energy_mix: [],
}


# =============================================================================
# Runtime resolvers — for types that need the data payload to pick the leaf
# =============================================================================

_CLOUD_SUBKIND_MAP: dict[str, EmissionType] = {
    "virtualisation": EmissionType.external__clouds__virtualisation,
    "calcul": EmissionType.external__clouds__calcul,
    "stockage": EmissionType.external__clouds__stockage,
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
    "eco_plus": EmissionType.professional_travel__plane__eco_plus,
    "eco": EmissionType.professional_travel__plane__eco,
}

_TRAIN_CLASS_MAP: dict[str, EmissionType] = {
    "class_1": EmissionType.professional_travel__train__class_1,
    "class_2": EmissionType.professional_travel__train__class_2,
}

_PROCESS_GAS_MAP: dict[str, EmissionType] = {
    "ch4": EmissionType.process_emissions__ch4,
    "co2": EmissionType.process_emissions__co2,
    "n2o": EmissionType.process_emissions__n2o,
    "refrigerants": EmissionType.process_emissions__refrigerants,
}


def _resolve_plane(data: dict) -> list[EmissionType] | None:
    # no default return non if no cabin_class
    cabin = (data.get("cabin_class") or "").lower()
    et = _PLANE_CABIN_MAP.get(cabin)
    return [et] if et else None


def _resolve_train(data: dict) -> list[EmissionType] | None:
    # trains also use cabin_class (class_1 / class_2)
    # no default, return None if no cabin_class or
    # unknown value — caller should log and skip
    cabin = (data.get("cabin_class") or "").lower()
    et = _TRAIN_CLASS_MAP.get(cabin)
    return [et] if et else None


def _resolve_clouds(data: dict) -> list[EmissionType] | None:
    # not defaulting to calcul — if sub_kind is missing/unknown, better to skip than to

    service_type = (data.get("service_type") or "").lower()
    et = _CLOUD_SUBKIND_MAP.get(service_type)
    return [et] if et else None


def _resolve_ai(data: dict) -> list[EmissionType] | None:
    ai_provider = (data.get("ai_provider") or "").lower().replace(" ", "_")
    et = _AI_USE_MAP.get(ai_provider)
    # default to "others" if provider is missing/unknown
    return [et] if et else [EmissionType.external__ai__provider_others]


def _resolve_process_emissions(data: dict) -> list[EmissionType] | None:
    gas = data.get("emitted_gas", (data.get("kind", "") or "")).lower()
    et = _PROCESS_GAS_MAP.get(gas)
    return [et] if et else None  # None = unknown gas, caller should warn + skip


# Used for factor emission type resolution (single category per factor row)
def _resolve_building(data: dict) -> list[EmissionType] | None:
    category = (data.get("category") or "").lower()
    energy_type = (data.get("energy_type") or "").lower()
    if category == "heating":
        if energy_type == "elec":
            return [EmissionType.buildings__rooms__heating_elec]
        elif energy_type == "thermal":
            return [EmissionType.buildings__rooms__heating_thermal]
    if category == "cooling":
        return [EmissionType.buildings__rooms__cooling]
    if category == "ventilation":
        return [EmissionType.buildings__rooms__ventilation]
    if category == "lighting":
        return [EmissionType.buildings__rooms__lighting]

    return None  # unknown category or energy type


def _resolve_building_data_entry(data: dict) -> list[EmissionType]:
    """For data entries: bypass to single aggregate row when kg_co2eq is set."""
    if data.get("kg_co2eq") is not None:
        return [EmissionType.buildings__rooms]
    return [
        EmissionType.buildings__rooms__lighting,
        EmissionType.buildings__rooms__cooling,
        EmissionType.buildings__rooms__ventilation,
        EmissionType.buildings__rooms__heating_elec,
        EmissionType.buildings__rooms__heating_thermal,
    ]


_RUNTIME_RESOLVERS = {
    DataEntryTypeEnum.plane: _resolve_plane,
    DataEntryTypeEnum.train: _resolve_train,
    # Factor resolution uses _resolve_building (single emission type per factor row)
    # Data entry resolution is handled by _resolve_building_data_entry (see below)
    DataEntryTypeEnum.building: _resolve_building,
    DataEntryTypeEnum.external_ai: _resolve_ai,
    DataEntryTypeEnum.external_clouds: _resolve_clouds,
    DataEntryTypeEnum.process_emissions: _resolve_process_emissions,
}

# Separate resolver used by resolve_emission_types() for data entries
_DATA_ENTRY_RESOLVERS = {
    **_RUNTIME_RESOLVERS,
    DataEntryTypeEnum.building: _resolve_building_data_entry,
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
        return None  # known type that intentionally emits nothing (e.g. energy_mix)
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
            (e.g. energy_mix)
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

    resolver = _DATA_ENTRY_RESOLVERS.get(data_entry_type)
    if resolver:
        return resolver(data)

    return None  # truly unhandled
