# Emission Type Subcategory Granularity — Implementation Plan

**Issue:** #577 (referenced from #207 schema update)
**Covers:** All modules — per-leaf chart granularity aligned with #207 schema
**Status:** Partially implemented — see scope table below.

---

## Iteration Scope

| Area                                                                                               | In scope (this PR)                                                                   | Deferred                                                                |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Professional Travel — per cabin-class chart keys                                                   | ✅ already in `EmissionTypeEnum` and `emission_breakdown.py`                         | —                                                                       |
| Buildings Rooms — per usage-type chart keys (lighting, cooling, ventilation, heating elec/thermal) | ✅ `EmissionTypeEnum` done; chart aggregation keys missing                           | —                                                                       |
| Buildings Rooms — scope split (elec=scope2, thermal=scope1)                                        | ✅ already in `EMISSION_SCOPE`                                                       | —                                                                       |
| Buildings Combustion — per-fuel chart granularity via `slug`                                       | ✅ implement `slug` backfill + breakdown                                             | —                                                                       |
| Process Emissions — per-gas chart keys (ch4, co2, n2o, refrigerants)                               | ✅ backend aggregation already done; expose individual keys in `CATEGORY_CHART_KEYS` | —                                                                       |
| Equipment — per-type keys (scientific, it, other)                                                  | ✅ already correct in breakdown                                                      | —                                                                       |
| Purchases — scope audit (`purchases__additional`: scope1 → scope3)                                 | ✅ bug fix                                                                           | —                                                                       |
| Research Facilities — chart keys (`facilities`, `animal`)                                          | ✅ emit correct keys; `CATEGORY_CHART_KEYS` is empty `[]`                            | —                                                                       |
| External Clouds — per-service keys (stockage, virtualisation, calcul)                              | ✅ already correct                                                                   | —                                                                       |
| Headcount — Food, Waste, Commuting, Grey Energy (additional breakdown)                             | ✅ already complete — separate `additional_breakdown` chart, all keys present        | —                                                                       |
| External AI — dynamic provider CRUD + backoffice                                                   | —                                                                                    | ❌ **DEFERRED**: AI providers remain hardcoded against existing factors |
| External AI — collapse `EmissionTypeEnum` 110201–110206 → 110200                                   | —                                                                                    | ❌ **DEFERRED**                                                         |
| Backoffice CRUD for AI providers                                                                   | —                                                                                    | ❌ **DEFERRED**                                                         |
| Backoffice CRUD for combustion fuel types                                                          | —                                                                                    | ❌ **DEFERRED**                                                         |

---

## Problem Statement: All Modules

The #207 schema defines per-leaf emission types and scopes for all 8 modules. The current codebase has the `EmissionTypeEnum` values and `EMISSION_SCOPE` mappings correct for most modules, but chart granularity and one scope assignment are wrong.

### Confirmed scope assignments from #207

| Module                 | Subcategory                                                                  | Scope                                |
| ---------------------- | ---------------------------------------------------------------------------- | ------------------------------------ |
| Professional Travel    | Train class 1, class 2                                                       | 3                                    |
| Professional Travel    | Plane first, business, eco, eco+                                             | 3                                    |
| Buildings / Rooms      | Lighting, cooling, ventilation, heating elec                                 | 2                                    |
| Buildings / Rooms      | Heating thermal (district heat)                                              | 1                                    |
| Buildings / Combustion | Natural gas, heating oil, biomethane, pellets, forest chips, wood logs       | 1                                    |
| Process Emissions      | CH4, CO2, N2O, Refrigerants                                                  | 1                                    |
| Equipment              | Scientific, IT, Other                                                        | 2                                    |
| Purchases              | 7 standard submodules                                                        | 3                                    |
| Purchases / Additional | LN2                                                                          | 3 (**bug: currently mapped scope1**) |
| Research Facilities    | Animal facilities, IT facilities, Others                                     | 3                                    |
| External Clouds        | Virtualisation, storage, compute                                             | 3                                    |
| External AI            | Providers (hardcoded: Google, Mistral AI, Anthropic, OpenAI, Cohere, Others) | 3                                    |
| Headcount              | Food                                                                         | 3                                    |
| Headcount              | Waste                                                                        | 3                                    |
| Headcount              | Commuting                                                                    | 3                                    |
| Headcount              | Grey Energy                                                                  | 3                                    |

### Known gap per module (this iteration)

| Module                 | EmissionTypeEnum                                            | EMISSION_SCOPE                                                   | Chart granularity                                                                                                                                                                         |
| ---------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Professional Travel    | ✅ Complete                                                 | ✅ Correct                                                       | ⚠️ Only `plane`/`train` totals exposed — per-class keys missing from `CATEGORY_CHART_KEYS`                                                                                                |
| Buildings / Rooms      | ✅ Complete                                                 | ✅ Correct                                                       | ⚠️ Only `energy` aggregate; per-usage-type keys (`lighting`, `cooling`, etc.) missing                                                                                                     |
| Buildings / Combustion | ✅ Single leaf `60200`                                      | ✅ Correct                                                       | ❌ No per-fuel breakdown; `slug` field missing from `Factor.classification`                                                                                                               |
| Process Emissions      | ✅ Complete                                                 | ✅ Correct                                                       | ⚠️ `CATEGORY_CHART_KEYS` only has `["process_emissions"]`; per-gas keys (`ch4`, `co2`, `n2o`, `refrigerants`) not listed                                                                  |
| Equipment              | ✅ Complete                                                 | ✅ Correct                                                       | ✅ Already correct (`scientific`, `it`, `other`)                                                                                                                                          |
| Purchases              | ✅ Complete                                                 | ⚠️ `purchases__additional` wrongly `scope1` — should be `scope3` | ✅ Individual subtype keys already generated                                                                                                                                              |
| Research Facilities    | ✅ `facilities`, `animal`                                   | ✅ Correct                                                       | ❌ `CATEGORY_CHART_KEYS` is `[]` — no keys registered for chart                                                                                                                           |
| External Clouds        | ✅ Complete                                                 | ✅ Correct                                                       | ✅ Already correct                                                                                                                                                                        |
| External AI            | ⚠️ Per-provider values `110201–110206` are hardcoded        | ✅ Correct (all scope3)                                          | ⚠️ Hardcoded provider list in `_apply_chart_aggregates`                                                                                                                                   |
| Headcount              | ✅ Flat leaves: `food`, `waste`, `commuting`, `grey_energy` | ✅ All `scope3`                                                  | ✅ Complete — routed to `additional_breakdown` (separate chart); keys `food`, `waste`, `commuting`, `greyEnergy` fully registered in `HEADCOUNT_KEY_MAP` and `ADDITIONAL_BREAKDOWN_ORDER` |

---

## Current Data Flow

### Headcount (Food, Waste, Commuting, Grey Energy)

```
DataEntry (member / student) → 4 simultaneous emission rows:
  EmissionType.food       (10000) → additional_breakdown key "food"       scope3
  EmissionType.waste      (20000) → additional_breakdown key "waste"      scope3
  EmissionType.commuting  (30000) → additional_breakdown key "commuting"  scope3
  EmissionType.grey_energy(40000) → additional_breakdown key "greyEnergy" scope3

Routed by _is_headcount_only() → NOT included in main module breakdown chart.
Accumulated separately in additional_breakdown via HEADCOUNT_KEY_MAP.
Zero-fill provided by ADDITIONAL_BREAKDOWN_ORDER = ["Commuting", "Food", "Waste", "Grey Energy"].

Status: ✅ Fully implemented — no changes needed in this iteration.
```

### Professional Travel

```
DataEntry.data.cabin_class ("class_1" | "class_2" | "first" | "business" | "eco" | "eco_plus")
  └─► _resolve_plane() / _resolve_train()
        └─► EmissionType.professional_travel__plane__eco (50204) etc.
              └─► emission_breakdown: chart_key = "eco", "eco_plus", "business", "first", "class_1", "class_2"
                    └─► _apply_chart_aggregates: "plane" = sum(eco, eco_plus, business, first)
                                                 "train" = sum(class_1, class_2)
                          └─► CATEGORY_CHART_KEYS["Professional travel"] = ["plane", "train"]
                                (per-class keys not exposed — missing from list)
```

### Buildings / Rooms

```
DataEntry (building) → produces 5 emission rows simultaneously:
  buildings__rooms__lighting (60101)      → chart_key "lighting"   scope2
  buildings__rooms__cooling (60102)       → chart_key "cooling"    scope2
  buildings__rooms__ventilation (60103)   → chart_key "ventilation" scope2
  buildings__rooms__heating_elec (60104)  → chart_key "heating_elec" scope2
  buildings__rooms__heating_thermal (60105)→ chart_key "heating_thermal" scope1

emission_breakdown: "energy" = sum of all five
  └─► CATEGORY_CHART_KEYS["Buildings energy consumption"] = ["energy"]
        (per-usage-type keys not listed — chart can only show total)
```

### Buildings / Combustion

```
CSV seed file (seed_buildings_combustion_factors.csv)
  └─► Factor rows: classification={"kind": "Natural gas"}, emission_type_id=60200

DataEntry.data.heating_type ("Natural gas")
  └─► buildings__combustion (60200) — always the same leaf
        └─► emission_breakdown: single chart_key "combustion"
              (no per-fuel breakdown — Factor.classification["slug"] field absent)
```

### Process Emissions

```
DataEntry.data.emitted_gas ("ch4" | "co2" | "n2o" | "refrigerants")
  └─► _resolve_process_emissions()
        └─► EmissionType.process_emissions__ch4 (70100) etc.
              └─► chart_key: "ch4", "co2", "n2o", "refrigerants"
                    └─► _apply_chart_aggregates: "process_emissions" = sum of all four
                          └─► CATEGORY_CHART_KEYS["Process Emissions"] = ["process_emissions"]
                                (per-gas keys not listed — prevents zero-fill of individual keys)
```

### Research Facilities

```
DataEntry → research_facilities__facilities (100100) or research_facilities__animal (100200)
  └─► chart_key: "facilities" or "animal"
        └─► CATEGORY_CHART_KEYS["Research facilities"] = []
              (empty — no keys registered for chart rendering)
```

### External AI (hardcoded, deferred)

```
DataEntry.data.ai_provider ("google" | "mistral_ai" | ...)
  └─► _resolve_ai() looks up _AI_USE_MAP
        └─► EmissionType.external__ai__provider_google (110201)
              └─► chart_key computed from emission_type.name → "provider_google" etc.
                    └─► _apply_chart_aggregates: hardcoded list of 6 provider keys
```

---

## Implementation Steps (This Iteration)

### Step 1 — Fix scope bug: `purchases__additional` scope1 → scope3

**File:** `backend/app/models/data_entry_emission.py`

Per #207 schema, Additional Purchases (LN2) is scope 3.

```python
# BEFORE
EmissionType.purchases__additional: Scope.scope1,

# AFTER
EmissionType.purchases__additional: Scope.scope3,
```

### Step 2 — Expose per-leaf chart keys in `CATEGORY_CHART_KEYS`

**File:** `backend/app/utils/emission_breakdown.py`

Update the dict to list all individual leaf keys so zero-fill works per leaf,
not just at the aggregate level:

```python
CATEGORY_CHART_KEYS: dict[str, list[str]] = {
    "Process Emissions": [
        "process_emissions",   # aggregate
        "ch4", "co2", "n2o", "refrigerants",  # per-gas leaves
    ],
    "Buildings energy consumption": [
        "energy",              # aggregate
        "lighting", "cooling", "ventilation", "heating_elec", "heating_thermal",  # per-usage-type
    ],
    "Energy combustion": [
        "combustion",          # aggregate — per-fuel keys added dynamically (Step 4)
    ],
    "Equipment": ["scientific", "it", "other"],
    "External cloud & AI": [
        "stockage", "virtualisation", "calcul",
        "ai_provider",         # aggregate for AI
        # per-provider keys (google, mistral_ai, …) are hardcoded here until Part B (deferred)
        "provider_google", "provider_mistral_ai", "provider_anthropic",
        "provider_openai", "provider_cohere", "provider_others",
    ],
    "Purchases": [
        "scientific_equipment", "it_equipment", "consumable_accessories",
        "biological_chemical_gaseous", "services", "vehicles", "other", "additional",
    ],
    "Research facilities": [
        "facilities", "animal",   # both registered so zero-fill works
    ],
    "Professional travel": [
        "plane", "train",          # aggregates
        "eco", "eco_plus", "business", "first",   # plane leaves
        "class_1", "class_2",                     # train leaves
    ],
}
```

### Step 3 — Research Facilities: emit correct chart keys

**File:** `backend/app/utils/emission_breakdown.py`

The `_to_chart_key_from_path()` function already derives `"facilities"` from
`research_facilities__facilities` and `"animal"` from `research_facilities__animal`.
No change needed in the key derivation. The only fix is registering the keys
in `CATEGORY_CHART_KEYS` (Step 2 above) so the frontend receives zero-filled
entries when a subcategory has no data yet.

### Step 4 — Buildings Combustion: add `slug` to Factor classification

**File:** `backend/app/seed/seed_building_factors.py`

Add `slug` to classification when seeding new factors. `slug` is
`kind.lower().replace(" ", "_")`.

```python
classification = {
    "kind": row["name"],
    "slug": row["name"].lower().replace(" ", "_"),  # e.g. "natural_gas"
}
```

**Alembic migration** — backfill existing factor rows:

```sql
UPDATE factor
SET classification = classification || jsonb_build_object(
    'slug',
    lower(replace(classification->>'kind', ' ', '_'))
)
WHERE data_entry_type_id = 31;  -- energy_combustion
-- Results: {"kind": "Natural gas", "slug": "natural_gas"}, etc.
```

### Step 5 — Buildings Combustion: per-fuel chart key in breakdown

**File:** `backend/app/utils/emission_breakdown.py`

Extend `_apply_chart_aggregates` for `"Energy combustion"` to emit one key per
fuel slug derived from the factor joined to the emission row. The raw row
accumulation loop must pass the factor slug through.

The breakdown service joins `data_entry_emission → factor` to get
`factor.classification["slug"]`. When accumulating into `category_data`:

```python
# In the row accumulation loop, for emissions under buildings__combustion:
if emission_type_id == EmissionType.buildings__combustion.value:
    fuel_slug = factor_classification.get("slug")
    if fuel_slug:
        fuel_key = f"combustion__{fuel_slug}"
        category_data[cat][fuel_key] = category_data[cat].get(fuel_key, 0.0) + kg_co2eq
```

In `_apply_chart_aggregates` for `"Energy combustion"`:

```python
if category_name == "Energy combustion":
    # Collect all combustion__* keys present in entry
    fuel_keys = [k for k in entry if k.startswith("combustion__") and not k.endswith("StdDev")]
    entry["combustion"] = _primary_or_sum(entry, "combustion", fuel_keys)
    entry["combustionStdDev"] = _primary_or_sum(
        entry, "combustionStdDev", [f"{k}StdDev" for k in fuel_keys]
    )
    return
```

`CATEGORY_CHART_KEYS["Energy combustion"]` keeps only `["combustion"]` as the
static entry; the per-fuel keys are dynamic and not zero-filled (they appear
only when data exists for that fuel).

### Step 6 — Frontend: expose per-leaf series in chart colour config

**File:** `frontend/src/constant/charts.ts`

Add per-leaf keys to the colour maps for all modules affected by Steps 2–3
so the chart component can render individual series when the backend sends them.

**Buildings energy consumption** — per usage type:

```typescript
'Buildings energy consumption': {
  energy: colors.value.lilac.default,           // aggregate fallback
  lighting: colors.value.lilac.darker,
  cooling: colors.value.lilac.dark,
  ventilation: colors.value.lilac.default,
  heating_elec: colors.value.lilac.light,
  heating_thermal: colors.value.lilac.lighter,  // scope 1 — distinct shade
},
```

**Energy combustion** — per fuel:

```typescript
'Energy combustion': {
  combustion: colors.value.lilac.light,         // aggregate fallback
  combustion__natural_gas: colors.value.lilac.darkest,
  combustion__heating_oil: colors.value.lilac.darker,
  combustion__biomethane: colors.value.lilac.dark,
  combustion__pellets: colors.value.lilac.default,
  combustion__forest_chips: colors.value.lilac.light,
  combustion__wood_logs: colors.value.lilac.lighter,
},
```

**Process Emissions** — per gas:

```typescript
'Process Emissions': {
  process_emissions: colors.value.apricot.default,  // aggregate
  co2: colors.value.apricot.darker,
  ch4: colors.value.apricot.dark,
  n2o: colors.value.apricot.default,
  refrigerants: colors.value.apricot.light,
},
```

**Research facilities** — per subtype:

```typescript
'Research facilities': {
  facilities: colors.value.babyBlue.dark,
  animal: colors.value.babyBlue.default,
},
```

**Professional travel** — per cabin class:

```typescript
'Professional travel': {
  plane: colors.value.babyBlue.darker,          // aggregate
  train: colors.value.babyBlue.dark,            // aggregate
  first: colors.value.babyBlue.darkest,
  business: colors.value.babyBlue.darker,
  eco_plus: colors.value.babyBlue.dark,
  eco: colors.value.babyBlue.default,
  class_1: colors.value.babyBlue.light,
  class_2: colors.value.babyBlue.lighter,
},
```

---

## Risks & Considerations

1. **Combustion per-fuel dynamic keys and zero-fill:** Per-fuel keys (`combustion__natural_gas`, …) appear only when data exists for that fuel. The `CATEGORY_CHART_KEYS` static list keeps only `"combustion"` for zero-fill; per-fuel zero-fill is not needed (fuel not entered = no bar). Frontend must tolerate sparse key sets across years.

2. **Chart key naming collision:** `combustion__*` keys must not collide with the `"combustion"` aggregate. The aggregate always rolls up all per-fuel keys present in the entry.

3. **Buildings scope split in scope breakdown:** `heating_thermal` is scope 1 while all other room usage types are scope 2 — both come from a single `DataEntry (building)` that produces 5 emission rows simultaneously. The scope breakdown must attribute each row to its own scope, not the module-level default.

4. **Purchases additional scope fix is a breaking change for existing reports:** Any report that already has additional purchase emissions computed as scope 1 will have its scope breakdown updated after this fix. This is correct behaviour, not a regression.

5. **Research facilities sub-grouping:** The schema lists "IT" and "Others" as facilities sub-types. Both currently map to `research_facilities__facilities (100100)`. Until a finer `EmissionTypeEnum` leaf is added (not in this iteration), they aggregate under `"facilities"` on the chart.

6. **Deferred AI dynamic providers:** `_AI_USE_MAP`, per-provider `EmissionTypeEnum` values, and hardcoded provider keys in `_apply_chart_aggregates` must not be removed until the deferred migration is executed and validated. Legacy code paths remain intentionally until Part B is implemented.
