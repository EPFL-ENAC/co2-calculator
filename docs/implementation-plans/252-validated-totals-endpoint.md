# Validated Modules Totals & Results Summary

## Context

We need endpoints to display validated module emissions:

1. **WorkspaceSetupPage / YearSelector** — needs total tCO2eq per year (all years at once) for a given unit
2. **HomePage** — needs per-module breakdown of tCO2eq for a specific carbon report, plus the total and FTE from headcount
3. **ResultsPage** — needs a rich per-module summary with tonnes, FTE per FTE, equivalent car km, and year-over-year comparison

The existing aggregation endpoints only handle equipment and don't filter by validation status. Headcount has no `DataEntryEmission` records — FTE is stored in `DataEntry.data["fte"]` and must be queried separately via `DataEntryRepository`.

**Performance note:** The join chains are acceptable at ~50-200ms with proper indexes on FK columns. No denormalization — keep the normalized schema. If performance becomes an issue later, add `carbon_report_id` to `DataEntryEmission` or use a materialized aggregation table.

---

## Endpoint 1: Workspace — yearly totals

**Route:** `GET /unit/{unit_id}/yearly-validated-emissions`

**Purpose:** Feed the YearSelector with total tCO2eq per year.

**Response:** plain JSON array (no wrapper object):

```json
[
  { "year": 2022, "total_tonnes_co2eq": 37.5 },
  { "year": 2023, "total_tonnes_co2eq": 37.8 },
  { "year": 2024, "total_tonnes_co2eq": 38.1 }
]
```

### 1a. Repository: [data_entry_emission_repo.py](backend/app/repositories/data_entry_emission_repo.py)

`get_validated_totals_by_unit(unit_id: int) -> list[dict]`

- Start from `CarbonReport` to get years, join down to emissions: `CarbonReport → CarbonReportModule → DataEntry → DataEntryEmission`
- Filter: `CarbonReport.unit_id == unit_id`, `CarbonReportModule.status == ModuleStatus.VALIDATED`, `DataEntryEmission.kg_co2eq IS NOT NULL`
- Group by: `CarbonReport.year` (year comes from the carbon report)
- Aggregate: `SUM(DataEntryEmission.kg_co2eq)`
- Order by: year ascending
- No filter on `module_type_id` — sums across ALL module types
- Returns: `[{"year": 2023, "kg_co2eq": 61700.0}, ...]` (still in kg)

### 1b. Service: [unit_totals_service.py](backend/app/services/unit_totals_service.py)

`get_validated_emissions_by_unit(unit_id: int) -> list[dict]`

- Delegates to the repo method and returns its result as-is (no conversion)
- Returns: `[{"year": 2023, "kg_co2eq": 61700.0}, ...]`

### 1c. Endpoint: [unit_results.py](backend/app/api/v1/unit_results.py)

`GET /{unit_id}/yearly-validated-emissions` — mounted at `/unit` prefix.

- Calls `UnitTotalsService.get_validated_emissions_by_unit(unit_id)`
- Converts kg → tonnes (÷1000) in the response list comprehension
- Returns `list[dict]` directly (no wrapper object)

---

## Endpoint 2: HomePage — per-module breakdown

**Route:** `GET /modules-stats/{carbon_report_id}/validated-totals`

**Purpose:** Show per-module tCO2eq breakdown + total for a specific carbon report. Uses `carbon_report_id` directly (frontend already has it from `selectedCarbonReport.id`).

**Response:** `modules` is a **map** keyed by `module_type_id` (int), not an array:

```json
{
  "modules": { "1": 25.5, "2": 15.0, "4": 41.7, "7": 5.0 },
  "total_tonnes_co2eq": 61.7,
  "total_fte": 25.5
}
```

- `modules` maps `module_type_id → value` where the value is **FTE** for headcount (`ModuleTypeEnum.headcount`) and **tonnes CO2eq** for all other module types
- `total_tonnes_co2eq` is the sum of all emission stats (÷1000) across all modules
- `total_fte` is the sum of all FTE stats

### 2a. Repository: [data_entry_emission_repo.py](backend/app/repositories/data_entry_emission_repo.py)

`get_stats_by_carbon_report_id(carbon_report_id: int) -> dict[str, float]`

No `aggregate_by`/`aggregate_field` parameters — always groups by `module_type_id` and sums `kg_co2eq`:

- Join: `DataEntryEmission → DataEntry → CarbonReportModule` (join through DataEntry to get to CarbonReportModule)
- Filter: `CarbonReportModule.carbon_report_id == carbon_report_id`, `CarbonReportModule.status == VALIDATED`, `kg_co2eq IS NOT NULL`
- Group by: `CarbonReportModule.module_type_id`
- Aggregate: `SUM(DataEntryEmission.kg_co2eq)`
- Returns: `{"2": 15000.0, "4": 41700.0, "7": 5000.0}` (kg, string keys)

### 2b. Repository: [data_entry_repo.py](backend/app/repositories/data_entry_repo.py)

`get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='module_type_id', aggregate_field='fte') -> dict[str, float]`

Generic aggregation method. Repo defaults are `aggregate_by='module_type_id'` and `aggregate_field='fte'`, but the **service** overrides `aggregate_by` to `'data_entry_type_id'` (see 2c):

- Join: `DataEntry → CarbonReportModule` (join to get carbon_report_id and status)
- Filter: `CarbonReportModule.carbon_report_id == carbon_report_id`, `CarbonReportModule.status == VALIDATED`
- Group by: resolved `aggregate_by` field (column from `CarbonReportModule`, `DataEntry`, or JSON key)
- Aggregate: `SUM(DataEntry.data[aggregate_field].as_float())` (or column if it exists on `DataEntry`)
- Returns: `{"1": 15.0, "2": 10.5}` (keyed by `data_entry_type_id`)
- Only headcount entries have FTE data; other modules' entries return null for `data["fte"]` and are excluded by SUM

### 2c. Endpoint: [carbon_report_module_stats.py](backend/app/api/v1/carbon_report_module_stats.py)

`GET /{carbon_report_id}/validated-totals` — mounted at `/modules-stats` prefix.

The endpoint:

- Calls `DataEntryEmissionService(db).get_stats_by_carbon_report_id(carbon_report_id)` → `emission_stats` (dict keyed by `module_type_id` as string)
- Calls `DataEntryService(db).get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='module_type_id')` → `fte_stats` (explicitly groups by `module_type_id` so keys align with `emission_stats`)
- Merges both dicts into a single `modules: dict[int, float]` map:
  - For the headcount `module_type_id`: uses FTE value from `fte_stats`
  - For all other `module_type_id`s: converts kg → tonnes (÷1000) from `emission_stats`
- Computes `total_tonnes_co2eq = sum(emission_stats values) / 1000` and `total_fte = sum(fte_stats values)`

---

## Endpoint 3: ResultsPage — full results summary

**Route:** `GET /modules-stats/{carbon_report_id}/results-summary`

**Purpose:** Provide a comprehensive results summary for the dedicated ResultsPage, including unit-wide totals, per-module breakdowns with car-km equivalents and year-over-year comparison.

**Response:**

```json
{
  "unit_totals": {
    "total_tonnes_co2eq": 61.7,
    "total_fte": 25.5,
    "tonnes_co2eq_per_fte": 2.42,
    "equivalent_car_km": 181470.6,
    "previous_year_total_tonnes_co2eq": 58.2,
    "year_comparison_percentage": 6.01
  },
  "co2_per_km_kg": 0.34,
  "module_results": [
    {
      "module_type_id": 2,
      "total_tonnes_co2eq": 15.0,
      "total_fte": null,
      "tonnes_co2eq_per_fte": 0.59,
      "equivalent_car_km": 44117.6,
      "previous_year_total_tonnes_co2eq": 14.2,
      "year_comparison_percentage": 5.63
    }
  ]
}
```

- `co2_per_km_kg` is the configurable `CO2_PER_KM_KG` env variable (default `0.34`), returned so the frontend can display the conversion factor in tooltips
- `unit_totals` aggregates across all validated modules
- `module_results` is a list of per-module entries; headcount module includes `total_fte`, others have `total_fte: null`
- `year_comparison_percentage` is `null` when no previous year data exists
- `equivalent_car_km = kg_co2eq / CO2_PER_KM_KG`

### 3a. Service: [unit_totals_service.py](backend/app/services/unit_totals_service.py)

`get_results_summary(carbon_report_id: int) -> dict`

Orchestrates all data fetching (3–5 DB queries total):

1. Loads `CarbonReport` by id → gets `unit_id` and `year`
2. Looks up previous year's `CarbonReport` via `CarbonReportRepository.get_by_unit_and_year(unit_id, year - 1)`
3. Fetches current emissions per module: `DataEntryEmissionRepository.get_stats_by_carbon_report_id(carbon_report_id)`
4. Fetches current FTE per module: `DataEntryRepository.get_stats_by_carbon_report_id(carbon_report_id)`
5. If previous report exists, fetches previous emissions per module

Returns raw data dict for the endpoint to format:

```python
{
    "current_emissions": {"2": 15000.0, "4": 41700.0},   # module_type_id → kg
    "current_fte": {"1": 25.5},                            # module_type_id → fte
    "prev_emissions": {"2": 14200.0, "4": 40000.0},       # empty dict if no prev year
}
```

### 3b. Endpoint: [carbon_report_module_stats.py](backend/app/api/v1/carbon_report_module_stats.py)

`GET /{carbon_report_id}/results-summary` — mounted at `/modules-stats` prefix.

The endpoint handles all formatting/conversion:

- Calls `UnitTotalsService(db).get_results_summary(carbon_report_id)` for raw data
- For each module in `current_emissions`, computes:
  - `total_tonnes = kg_co2eq / 1000`
  - `tonnes_per_fte = total_tonnes / total_fte` (if FTE available)
  - `equivalent_car_km = kg_co2eq / settings.CO2_PER_KM_KG`
  - `year_comparison = (current - prev) / prev * 100` (if previous year exists)
- Aggregates `unit_totals` by summing across all modules
- Returns `co2_per_km_kg` from `Settings.CO2_PER_KM_KG` so the frontend can display it

### 3c. Configuration: `CO2_PER_KM_KG`

New environment variable in `backend/app/core/config.py`:

```python
CO2_PER_KM_KG: float = Field(
    default=0.34,
    description="CO2 per km in kg",
)
```

Also documented in `.env.example`.

---

## Frontend

### API layer: [modules.ts](frontend/src/api/modules.ts)

The API module defines TypeScript interfaces and fetch functions:

**Interfaces:**

```typescript
interface ModuleResult {
  module_type_id: number;
  total_tonnes_co2eq: number;
  total_fte: number | null;
  tonnes_co2eq_per_fte: number | null;
  equivalent_car_km: number;
  previous_year_total_tonnes_co2eq: number | null;
  year_comparison_percentage: number | null;
}

interface ResultsSummary {
  unit_totals: {
    total_tonnes_co2eq: number | null;
    total_fte: number | null;
    tonnes_co2eq_per_fte: number | null;
    equivalent_car_km: number | null;
    previous_year_total_tonnes_co2eq: number | null;
    year_comparison_percentage: number | null;
  };
  co2_per_km_kg: number;
  module_results: ModuleResult[];
}
```

**Function:** `getResultsSummary(carbonReportId: number)` — calls `GET /modules-stats/{carbonReportId}/results-summary`.

### Store: [modules.ts](frontend/src/stores/modules.ts)

The Pinia store (`useModuleStore`) contains functions for endpoint 1 (yearly emissions):

**Function:** `getYearlyValidatedEmissions(unitId: number)` — calls `GET /unit/{unitId}/yearly-validated-emissions`, stores result in `state.yearlyValidatedEmissions`.

### ResultsPage: [ResultsPage.vue](frontend/src/pages/app/ResultsPage.vue)

Dedicated results page that consumes the `results-summary` endpoint:

- Calls `getResultsSummary(carbonReportId)` on mount and when `selectedCarbonReport` changes
- **Unit-wide totals section** with 3 `BigNumber` cards:
  - Total carbon footprint (tonnes CO2eq) with car-km equivalent
  - Carbon footprint per FTE with Paris Agreement reference (2 tonnes)
  - Year-over-year % change with previous year comparison
- **Per-module breakdown** using expansion panels for each module (excluding headcount):
  - Each module shows 3 `BigNumber` cards (same metrics as unit totals but module-scoped)
  - Professional travel modules additionally show `ModuleCharts` when validated
  - Non-validated modules show a placeholder card prompting validation
- `co2_per_km_kg` value from the response is used in tooltips to explain the car-km conversion factor
- Supports colorblind mode toggle, uncertainty badges, and year comparison toggle
- PDF download via `window.print()`

---

## Files Modified

| File                                                   | Change                                                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `backend/app/core/config.py`                           | Add `CO2_PER_KM_KG` setting (default 0.34)                                                 |
| `backend/.env.example`                                 | Document `CO2_PER_KM_KG`                                                                   |
| `backend/app/repositories/data_entry_emission_repo.py` | Add `get_validated_totals_by_unit()` + `get_stats_by_carbon_report_id()`                   |
| `backend/app/repositories/data_entry_repo.py`          | Add `get_stats_by_carbon_report_id()`                                                      |
| `backend/app/repositories/carbon_report_repo.py`       | Add `get_by_unit_and_year()`                                                               |
| `backend/app/services/unit_totals_service.py`          | Add `get_validated_emissions_by_unit()` + `get_results_summary()`                          |
| `backend/app/services/data_entry_emission_service.py`  | Add `get_stats_by_carbon_report_id()` (delegates to repo)                                  |
| `backend/app/services/data_entry_service.py`           | Add `get_stats_by_carbon_report_id()` (delegates to repo)                                  |
| `backend/app/api/v1/unit_results.py`                   | Add `GET /{unit_id}/yearly-validated-emissions` endpoint                                   |
| `backend/app/api/v1/carbon_report_module_stats.py`     | Add `GET /{carbon_report_id}/validated-totals` + `GET /{carbon_report_id}/results-summary` |
| `frontend/src/api/modules.ts`                          | Add `ResultsSummary`, `ModuleResult` interfaces + `getResultsSummary()` function           |
| `frontend/src/stores/modules.ts`                       | Add `getYearlyValidatedEmissions()`, interfaces, and state                                 |
| `frontend/src/pages/app/ResultsPage.vue`               | Full results page consuming `results-summary` endpoint                                     |
| `frontend/src/types.ts`                                | Add `ModuleResult` type reference                                                          |

## Verification

1. Call `GET /api/v1/unit/{id}/yearly-validated-emissions` — verify response is a plain JSON array of per-year totals from validated modules only
2. Call `GET /api/v1/modules-stats/{carbon_report_id}/validated-totals` — verify `modules` is a map keyed by `module_type_id` (int) with correct values
3. Call `GET /api/v1/modules-stats/{carbon_report_id}/results-summary` — verify `unit_totals`, `module_results[]`, and `co2_per_km_kg` are present and correctly computed
4. Non-validated modules (status 0 or 1) must not appear in any endpoint
5. Headcount FTE must come from `DataEntry.data["fte"]`, not from `DataEntryEmission`
6. A unit with no validated modules returns an empty array / zero totals
7. `equivalent_car_km` uses the configurable `CO2_PER_KM_KG` value (default 0.34)
8. Year-over-year comparison returns `null` when no previous year data exists
9. ResultsPage displays placeholder cards for modules that are not yet validated
