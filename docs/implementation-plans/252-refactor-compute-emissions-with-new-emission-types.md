# Emission Computation — Data Reference

## Factor Retrieval Strategies

Two strategies, mutually exclusive per `EmissionComputation`:

| Strategy                     | Trigger                                  | Returns      | Rows produced |
| ---------------------------- | ---------------------------------------- | ------------ | ------------- |
| **A — primary_factor_id**    | `primary_factor_id` in `data_entry.data` | 1 factor     | 1 row         |
| **B — classification query** | `FactorQuery(kind, subkind, **ctx)`      | 1..N factors | 1..N rows     |

---

## Pre-computation Layer

Some formula inputs are not in `data_entry.data` and must be derived before
factor retrieval. Handlers declare a `pre_compute` async hook that runs first
and returns an enriched `ctx` dict merged with `data_entry.data`.

| DataEntryType                 | Pre-computed key                                                   | Source                      | Pure?                                 |
| ----------------------------- | ------------------------------------------------------------------ | --------------------------- | ------------------------------------- |
| `scientific` / `it` / `other` | `annual_kwh` = `((active_w + standby_w) / 2) * hours / 1000`       | Arithmetic                  | ✅                                    |
| `professional_travel` (plane) | `distance_km` = `LocationService.calculate_distance(origin, dest)` | DB — `locations` table      | ❌                                    |
| `building`                    | `kwh_per_m2` per subcategory from `archibus_rooms`                 | DB — `archibus_rooms` table | ❌ (tech debt — will move to factors) |

---

## Full DataEntryType Matrix

### Headcount — `member` / `student`

| Field                | Value                                                        |
| -------------------- | ------------------------------------------------------------ |
| **EmissionTypes**    | `food`, `waste`, `commuting`, `grey_energy`                  |
| **Strategy**         | B — classification query                                     |
| **Factor query**     | `kind=emission_type.name`, `subkind=None`, `data_entry_type` |
| **Factors per type** | N (e.g. food → `food__vegetarian` + `food__non_vegetarian`)  |
| **Rows produced**    | 1 row per factor (food → 2 rows, waste → up to 15 rows)      |
| **Formula**          | `fte × kg_co2eq_per_fte`                                     |
| **Quantity key**     | `fte` from `data_entry.data`                                 |
| **Pre-compute**      | None                                                         |

---

### Professional Travel — Train

| Field                | Value                                                                            |
| -------------------- | -------------------------------------------------------------------------------- |
| **EmissionTypes**    | `professional_travel__train__class_1`, `professional_travel__train__class_2`     |
| **Resolution**       | Runtime — `cabin_class` in `data_entry.data` → leaf via `resolve_emission_types` |
| **Strategy**         | B — classification query                                                         |
| **Factor query**     | `kind="train"`, `subkind=class_name`, `country_code` from ctx                    |
| **Factors per type** | 1                                                                                |
| **Formula**          | `distance_km × kg_co2eq_per_km`                                                  |
| **Quantity key**     | `distance_km` from `data_entry.data`                                             |
| **Pre-compute**      | None (distance_km stored directly for train)                                     |

---

### Professional Travel — Plane

| Field                | Value                                                                                   |
| -------------------- | --------------------------------------------------------------------------------------- |
| **EmissionTypes**    | `plane__first`, `plane__business`, `plane__eco_plus`, `plane__eco`                      |
| **Resolution**       | Runtime — `cabin_class` in `data_entry.data` → leaf via `resolve_emission_types`        |
| **Strategy**         | B — classification query                                                                |
| **Factor query**     | `kind="plane"`, `subkind=cabin_class`, `distance_km` from ctx                           |
| **Factors per type** | 1                                                                                       |
| **Formula**          | `distance_km × kg_co2eq_per_km`                                                         |
| **Quantity key**     | `distance_km`                                                                           |
| **Pre-compute**      | ✅ `distance_km = LocationService.calculate_distance(origin_iata, dest_iata)` — DB call |

---

### Building

| Field                | Value                                                                                                 |
| -------------------- | ----------------------------------------------------------------------------------------------------- |
| **EmissionTypes**    | `buildings__rooms__lighting`, `cooling`, `ventilation`, `heating_elec`, `heating_thermal`             |
| **Strategy**         | B — classification query                                                                              |
| **Factor query**     | `kind=subcategory` (e.g. "heating"), `subkind=energy_type` ("elec"/"therm"), `building_name` from ctx |
| **Factors per type** | 1 per subcategory                                                                                     |
| **Formula**          | `kwh_per_m2 × surface_m2 × kg_co2eq_per_kwh`                                                          |
| **Quantity key**     | `kwh_per_m2` (pre-computed), `surface_m2` from data                                                   |
| **Pre-compute**      | ✅ `kwh_per_m2` per subcategory from `archibus_rooms` by `building_name` — DB call (tech debt)        |

---

### Energy Combustion

| Field             | Value                                                        |
| ----------------- | ------------------------------------------------------------ |
| **EmissionTypes** | Resolved via `resolve_emission_types(data_entry_type, data)` |
| **Strategy**      | A — `primary_factor_id`                                      |
| **Formula**       | TBD per fuel type                                            |
| **Pre-compute**   | None                                                         |

---

### Process Emissions

| Field             | Value                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------- |
| **EmissionTypes** | `process_emissions__ch4`, `co2`, `n2o`, `refrigerants` — resolved via `resolve_emission_types` |
| **Strategy**      | A — `primary_factor_id`                                                                        |
| **Formula**       | TBD                                                                                            |
| **Pre-compute**   | None                                                                                           |

---

### Equipment — `scientific` / `it` / `other`

| Field             | Value                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------- |
| **EmissionTypes** | `equipment__scientific`, `equipment__it`, `equipment__other` (1-1 mapping)                        |
| **Strategy**      | A — `primary_factor_id`                                                                           |
| **Factor**        | Embeds `ef_kg_co2eq_per_kwh` directly (no separate electricity factor needed)                     |
| **Formula**       | `annual_kwh × ef_kg_co2eq_per_kwh`                                                                |
| **Quantity key**  | `annual_kwh`                                                                                      |
| **Pre-compute**   | ✅ `annual_kwh = ((active_power_w + standby_power_w) / 2) * usage_hours / 1000` — pure arithmetic |

---

### Purchases

| Field             | Value                                                               |
| ----------------- | ------------------------------------------------------------------- |
| **EmissionTypes** | 1-1 with `DataEntryTypeEnum` (e.g. `purchases__goods_and_services`) |
| **Strategy**      | A — `primary_factor_id`                                             |
| **Formula**       | TBD                                                                 |
| **Pre-compute**   | None                                                                |

---

### Research Facilities

| Field             | Value                        |
| ----------------- | ---------------------------- |
| **EmissionTypes** | 1-1 with `DataEntryTypeEnum` |
| **Strategy**      | A — `primary_factor_id`      |
| **Formula**       | TBD                          |
| **Pre-compute**   | None                         |

---

### External Clouds & AI

| Field             | Value                                             |
| ----------------- | ------------------------------------------------- |
| **EmissionTypes** | Resolved dynamically via `resolve_emission_types` |
| **Strategy**      | A — `primary_factor_id`                           |
| **Formula**       | TBD                                               |
| **Pre-compute**   | None                                              |

---

## Flow Summary

```
prepare_create(data_entry)
│
├── resolve_emission_types(data_entry_type, data)   → list[EmissionType]
├── handler.pre_compute(data_entry, session)        → ctx dict  (may hit DB)
│       merged with data_entry.data
│
└── for each emission_type:
    │
    ├── handler.resolve_computations(data_entry, emission_type, ctx)
    │       → list[EmissionComputation]   (1 per factor)
    │
    └── for each computation:
        ├── fetch factor  (Strategy A: get(id) | Strategy B: get_by_classification(**query))
        ├── apply formula (ctx[quantity_key] × factor.values[formula_key])
        └── → DataEntryEmission row
```

---

## Implementation TODO

### Phase 1 — Core data structures

- [ ] `FactorQuery` dataclass: `data_entry_type`, `kind`, `subkind`, `context: dict`
- [ ] `EmissionComputation` dataclass: `emission_type`, `factor_id | None`,
      `factor_query | None`, `formula_key`, `quantity_key`
- [ ] `HandlerRegistry` — maps `DataEntryTypeEnum → BaseModuleHandler subclass`

### Phase 2 — Base handler contract

- [ ] `BaseModuleHandler.pre_compute(data_entry, session) -> dict` (default: `{}`)
- [ ] `BaseModuleHandler.resolve_computations(data_entry, emission_type, ctx)`
      `-> list[EmissionComputation]` — registered per `EmissionType` via decorator
- [ ] `@register(*emission_types)` class decorator on `BaseModuleHandler`

### Phase 3 — FactorService extension

- [ ] `get_by_classification(data_entry_type, kind, subkind, **ctx)`
      returns `list[Factor]` (not single)
- [ ] Add context filter support: `country_code`, `distance_km`, `building_name`

### Phase 4 — Handlers (one file each)

- [ ] `HeadcountHandler` — Strategy B, `kg_co2eq_per_fte`, registers food/waste/commuting/grey_energy
- [ ] `ProfessionalTravelHandler` — train (Strategy B, country_code) + plane (Strategy B, pre-computed distance_km)
- [ ] `BuildingHandler` — Strategy B, pre-computes kwh_per_m2 from archibus_rooms
- [ ] `EquipmentHandler` — Strategy A, pre-computes annual_kwh (pure arithmetic)
- [ ] `PurchasesHandler` — Strategy A, primary_factor_id
- [ ] `ProcessEmissionsHandler` — Strategy A, primary_factor_id
- [ ] `ExternalHandler` — Strategy A, primary_factor_id
- [ ] `ResearchFacilitiesHandler` — Strategy A, primary_factor_id
- [ ] `CombustionHandler` — Strategy A, primary_factor_id

### Phase 5 — EmissionService rewrite

- [ ] `prepare_create` — pure orchestrator, zero branching on `DataEntryType`
- [ ] `_fetch_factor(comp, session) -> list[Factor]` — dispatches A vs B
- [ ] `_apply_formula(ctx, factor_values, comp) -> float | None`

### Phase 6 — resolve_emission_types

- [ ] Ensure travel leaf resolved from `cabin_class` at call time

### Phase 7 — Tests

- [ ] Unit test each handler's `resolve_computations` (pure, no DB needed)
- [ ] Unit test `pre_compute` for plane and building (mock session)
- [ ] Unit test `_fetch_factor` for both strategies
- [ ] Unit test `_apply_formula` per formula_key variant
- [ ] Integration test `prepare_create` per DataEntryType (mock FactorService + session)
