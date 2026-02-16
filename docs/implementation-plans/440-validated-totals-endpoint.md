# Validated Modules Totals — Two Endpoints

## Context

We need two new endpoints to display validated module emissions:

1. **WorkspaceSetupPage / YearSelector** — needs total tCO2eq per year (all years at once) for a given unit
2. **HomePage** — needs per-module breakdown of tCO2eq for a specific carbon report, plus the total and FTE from headcount

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

## Frontend

### Store: [modules.ts](frontend/src/stores/modules.ts)

Both API functions live in the **Pinia store** (`useModuleStore`), not in `api/modules.ts`. They call the backend via `api.get()` directly.

**Interfaces:**

```typescript
interface ValidatedTotalsResponse {
  modules: Record<number, number>;
  total_tonnes_co2eq: number;
  total_fte: number;
}

interface YearlyValidatedEmission {
  year: number;
  total_tonnes_co2eq: number;
}
```

**Function 1:** `getYearlyValidatedEmissions(unitId: number)` — calls `GET /unit/{unitId}/yearly-validated-emissions`, stores result in `state.yearlyValidatedEmissions` (`YearlyValidatedEmission[]`).

**Function 2:** `getValidatedTotals(carbonReportId: number)` — calls `GET /modules-stats/{carbonReportId}/validated-totals`, stores result in `state.validatedTotals` (`ValidatedTotalsResponse | null`). Caches by `carbonReportId` to avoid redundant fetches.

### Integration: WorkspaceSetupPage / YearSelector

- `WorkspaceSetupPage.vue` calls `moduleStore.getYearlyValidatedEmissions(unit.id)` in `handleUnitSelect`, alongside fetching carbon reports
- A `yearRows` computed property maps `state.yearlyValidatedEmissions` into `YearData[]` by matching each year's emissions to the available carbon report years
- The `YearSelector.vue` component receives `yearRows` as a prop and displays tCO2eq per year in a table column

### Integration: HomePage

- `HomePage.vue` calls `moduleStore.getValidatedTotals(carbonReportId)` reactively via a computed property (triggers when `currentCarbonReportId` changes)
- `validatedTotals?.total_tonnes_co2eq` is displayed as the year total
- A `moduleCardTotals` computed maps `validatedTotals.modules` to per-module-card values using `getModuleTypeId(module)` lookups

---

## Files Modified

| File                                                   | Change                                                                              |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `backend/app/repositories/data_entry_emission_repo.py` | Add `get_validated_totals_by_unit()` + `get_stats_by_carbon_report_id()`            |
| `backend/app/repositories/data_entry_repo.py`          | Add `get_stats_by_carbon_report_id()`                                               |
| `backend/app/services/unit_totals_service.py`          | Add `get_validated_emissions_by_unit()`                                             |
| `backend/app/services/data_entry_emission_service.py`  | Add `get_stats_by_carbon_report_id()` (delegates to repo)                           |
| `backend/app/services/data_entry_service.py`           | Add `get_stats_by_carbon_report_id()` (delegates to repo)                           |
| `backend/app/api/v1/unit_results.py`                   | Add `GET /{unit_id}/yearly-validated-emissions` endpoint                            |
| `backend/app/api/v1/carbon_report_module_stats.py`     | Add `GET /{carbon_report_id}/validated-totals` endpoint                             |
| `frontend/src/stores/modules.ts`                       | Add `getYearlyValidatedEmissions()` + `getValidatedTotals()`, interfaces, and state |
| `frontend/src/pages/app/WorkspaceSetupPage.vue`        | Call `getYearlyValidatedEmissions` on unit selection, compute `yearRows`            |
| `frontend/src/pages/app/HomePage.vue`                  | Call `getValidatedTotals` reactively, display totals and per-module cards           |

## Verification

1. Call `GET /api/v1/unit/{id}/yearly-validated-emissions` — verify response is a plain JSON array of per-year totals from validated modules only
2. Call `GET /api/v1/modules-stats/{carbon_report_id}/validated-totals` — verify `modules` is a map keyed by `module_type_id` (int) with correct values
3. Non-validated modules (status 0 or 1) must not appear in either endpoint
4. Headcount FTE must come from `DataEntry.data["fte"]`, not from `DataEntryEmission`
5. A unit with no validated modules returns an empty array / zero totals
