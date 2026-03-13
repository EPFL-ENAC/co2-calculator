# Emission Pipeline Flow

> Reference documentation for the emission calculation pipeline.
> Describes how `DataEntryEmission` rows are produced from a `DataEntry`.

---

## Pipeline Overview

```mermaid
sequenceDiagram
    participant Router as API Router
    participant MHS as ModuleHandlerService
    participant DES as DataEntryService
    participant DEES as DataEntryEmissionService
    participant Handler as ModuleHandler
    participant FS as FactorService
    participant DB as Database

    Note over Router: POST /carbon-report-modules/{id}/items
    Router->>MHS: resolve_primary_factor_id(handler, payload)
    MHS->>FS: get_by_classification(kind, subkind)
    FS->>DB: SELECT Factor WHERE classification
    DB-->>FS: Factor
    FS-->>MHS: factor.id
    MHS-->>Router: payload + primary_factor_id

    Router->>DES: create(data_entry_create)
    DES->>DB: INSERT DataEntry
    DB-->>DES: DataEntry (with id)
    DES-->>Router: DataEntryResponse

    Router->>DEES: upsert_by_data_entry(response)
    DEES->>DEES: prepare_create(data_entry)

    Note over DEES: Step 1: Resolve emission types
    DEES->>DEES: resolve_emission_types(data_entry_type, data)

    Note over DEES: Step 2: Pre-compute (enrich ctx)
    DEES->>Handler: pre_compute(data_entry, session)
    Handler-->>DEES: extra ctx (e.g. distance_km)

    Note over DEES: Step 3: Resolve computations
    DEES->>Handler: resolve_computations(data_entry, emission_type, ctx)
    Handler-->>DEES: list[EmissionComputation]

    Note over DEES: Step 4: Fetch factors
    alt Strategy A — factor_id
        DEES->>FS: get(factor_id)
    else Strategy B — FactorQuery
        DEES->>FS: get_by_classification / get_factor
    end
    FS->>DB: SELECT Factor
    DB-->>FS: Factor
    FS-->>DEES: Factor (with .values)

    Note over DEES: Step 5: Apply formula
    DEES->>DEES: formula_func(ctx, factor.values) → kg_co2eq
    DEES->>DB: INSERT DataEntryEmission
```

---

## Pipeline Steps

### Step 1 — Resolve Emission Types

`resolve_emission_types(data_entry_type, data)` returns the list of
`EmissionType` leaves to produce for this data entry. Each leaf becomes one
(or more) `DataEntryEmission` row.

### Step 2 — Pre-compute (`handler.pre_compute`)

Enriches the context dict with values that require **DB access** or
**non-trivial arithmetic** from user data only. The returned dict is merged
into `ctx = {**data_entry.data, **pre_compute_result}`.

**Rule:** `pre_compute` must NOT read factor values. Factor data is only
available at Step 5 via `factor_values`.

### Step 3 — Resolve Computations (`handler.resolve_computations`)

Declares one `EmissionComputation` per factor lookup needed. Each computation
specifies either:

- **Strategy A** — `factor_id` (int): direct lookup by ID
- **Strategy B** — `factor_query` (FactorQuery): classification-based lookup

### Step 4 — Fetch Factors (`_fetch_factors`)

Retrieves `Factor` objects from the database using the strategy declared in
Step 3. For Strategy B, progressive fallbacks are attempted (see below).

### Step 5 — Apply Formula (`_apply_formula` / `formula_func`)

Computes `kg_co2eq` from `ctx` (user data + pre-computed values) and
`factor_values` (from the fetched Factor). Two approaches:

| Approach           | When                   | How                                                      |
| ------------------ | ---------------------- | -------------------------------------------------------- |
| **Key-based**      | Simple `quantity × ef` | `formula_key`, `quantity_key`, optional `multiplier_key` |
| **`formula_func`** | Complex logic          | `formula_func(ctx, factor_values) → float`               |

---

## Factor Retrieval Strategies

| Strategy                 | Trigger                                  | Returns      | Used by                                                                                                       |
| ------------------------ | ---------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------- |
| **A — direct factor_id** | `primary_factor_id` in `data_entry.data` | 1 factor     | Equipment, Purchase, Process Emissions, External Cloud/AI, Research Facilities, Energy Combustion , Buildings |
| **B — FactorQuery**      | `FactorQuery(kind, subkind, context)`    | 1..N factors | Travel (plane/train), Headcount (member/student)                                                              |

### Strategy B Fallback Order

1. Full classification (subkind + context + fallbacks)
2. Kind only (no subkind/context)
3. By emission_type → returns N factors
4. By data_entry_type → broadest

---

## Per-Module Breakdown

### Professional Travel — Plane

| Step                   | What happens                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `pre_compute`          | Fetches origin/destination `Location` from DB. Computes `distance_km` (haversine) and `haul_category` (short/medium/long) |
| `resolve_computations` | Strategy B — `FactorQuery(kind=haul_category)`                                                                            |
| Formula                | Key-based: `distance_km × ef_kg_co2eq_per_km × rfi_adjustment`                                                            |

### Professional Travel — Train

| Step                   | What happens                                                                             |
| ---------------------- | ---------------------------------------------------------------------------------------- |
| `pre_compute`          | Fetches origin/destination `Location` from DB. Computes `distance_km` and `country_code` |
| `resolve_computations` | Strategy B — `FactorQuery(kind=country_code, fallbacks={"kind": "RoW"})`                 |
| Formula                | Key-based: `distance_km × ef_kg_co2eq_per_km`                                            |

### Equipment Electric Consumption (IT / Scientific / Other)

| Step                   | What happens                                                                                                                                                                                                                                                                 |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pre_compute`          | Validates `active_usage_hours + standby_usage_hours ≤ 168`                                                                                                                                                                                                                   |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`                                                                                                                                                                                                                                 |
| Formula                | `formula_func`: reads `active_power_w`, `standby_power_w`, `ef_kg_co2eq_per_kwh` from `factor_values`; reads hours from `ctx`. Computes `annual_kwh = ((active_hours × active_power_w) + (standby_hours × standby_power_w)) × WEEKS_PER_YEAR / 1000`, then `annual_kwh × ef` |

### Buildings — Rooms

| Step                   | What happens                                                                                                                                                                                              |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pre_compute`          | No override (default returns `{}`)                                                                                                                                                                        |
| `resolve_computations` | Strategy B — `FactorQuery(kind=building_name, subkind=room_type)`. One computation per emission type (lighting, cooling, ventilation, heating_elec, heating_thermal)                                      |
| Formula                | `formula_func`: reads `kwh_per_square_meter` field (varies by emission type) from `factor_values`, multiplies by `room_surface_square_meter` from `ctx`, then `× ef_kg_co2eq_per_kwh × conversion_factor` |

### Buildings — Energy Combustion

| Step                   | What happens                                 |
| ---------------------- | -------------------------------------------- |
| `pre_compute`          | No override                                  |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id` |
| Formula                | Key-based: `quantity × kg_co2eq_per_unit`    |

### Headcount (Member / Student)

| Step                   | What happens                                                                           |
| ---------------------- | -------------------------------------------------------------------------------------- |
| `pre_compute`          | No override                                                                            |
| `resolve_computations` | Strategy B — `FactorQuery(data_entry_type, no kind/subkind)` → returns all sub-factors |
| Formula                | Key-based: `fte × ef_kg_co2eq_per_fte`                                                 |

### Purchase (Common)

| Step                   | What happens                                               |
| ---------------------- | ---------------------------------------------------------- |
| `pre_compute`          | No override                                                |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`               |
| Formula                | Key-based: `total_spent_amount × ef_kg_co2eq_per_currency` |

### Purchase (Additional)

| Step                   | What happens                                           |
| ---------------------- | ------------------------------------------------------ |
| `pre_compute`          | No override                                            |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`           |
| Formula                | `formula_func`: `annual_consumption × coef_to_kg × ef` |

### External Cloud

| Step                   | What happens                                         |
| ---------------------- | ---------------------------------------------------- |
| `pre_compute`          | No override                                          |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`         |
| Formula                | Key-based: `spent_amount × ef_kg_co2eq_per_currency` |

### External AI

| Step                   | What happens                                                   |
| ---------------------- | -------------------------------------------------------------- |
| `pre_compute`          | No override                                                    |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`                   |
| Formula                | `formula_func`: `frequency × 5 × 46 × users × factor_g / 1000` |

### Process Emissions

| Step                   | What happens                                        |
| ---------------------- | --------------------------------------------------- |
| `pre_compute`          | No override                                         |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id`        |
| Formula                | `formula_func`: `quantity_kg × gwp_kg_co2eq_per_kg` |

### Research Facilities

| Step                   | What happens                                 |
| ---------------------- | -------------------------------------------- |
| `pre_compute`          | No override                                  |
| `resolve_computations` | Strategy A — `factor_id = primary_factor_id` |
| Formula                | TBD — currently returns empty list           |

---

## Data Enrichment for LIST/GET Responses

The `get_submodule_data()` repository method enriches `data_entry.data` with
factor information for display purposes:

```python
data_entry.data = {
    **data_entry.data,
    "kg_co2eq": total_kg_co2eq,
    "primary_factor": {
        **factor.values,          # e.g. active_power_w, ef_kg_co2eq_per_kwh
        **factor.classification,  # e.g. kind, subkind
    }
}
```

This enriched `primary_factor` dict is used by `to_response()` to extract
display fields (e.g. `active_power_w` for equipment, `kwh_per_square_meter`
for buildings). It is **only available during LIST/GET**, NOT during emission
creation.

**Important:** `pre_compute` and `formula_func` must never rely on the
`primary_factor` dict in `data_entry.data`. Factor values are available via
`factor_values` parameter in `formula_func` / `_apply_formula`.
