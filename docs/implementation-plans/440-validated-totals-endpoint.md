# Validated Modules Totals — Two Endpoints

## Context

We need two new endpoints to display validated module emissions:

1. **WorkspaceSetupPage / YearSelector** — needs total tCO2eq per year (all years at once) for a given unit
2. **HomePage** — needs per-module breakdown of tCO2eq for a specific carbon report, plus the total and FTE from headcount

The existing aggregation endpoints only handle equipment and don't filter by validation status. Headcount has no `DataEntryEmission` records — FTE is stored in `DataEntry.data["fte"]` and must be queried separately via `DataEntryRepository`.

**Performance note:** The join chains are acceptable at ~50-200ms with proper indexes on FK columns. No denormalization — keep the normalized schema. If performance becomes an issue later, add `carbon_report_id` to `DataEntryEmission` or use a materialized aggregation table.

---

## Endpoint 1: Workspace — yearly totals

**Route:** `GET /unit/{unit_id}/validated-emissions`

**Purpose:** Feed the YearSelector with total tCO2eq per year.

**Response:**

```json
{
  "emissions_data": [
    { "year": 2022, "total_tonnes_co2eq": 37.5 },
    { "year": 2023, "total_tonnes_co2eq": 37.8 },
    { "year": 2024, "total_tonnes_co2eq": 38.1 }
  ]
}
```

### 1a. Repository: [data_entry_emission_repo.py](backend/app/repositories/data_entry_emission_repo.py)

Add `get_validated_totals_by_unit(unit_id: int) -> list[dict]`

- Start from `CarbonReport` to get years, join down to emissions: `CarbonReport → CarbonReportModule → DataEntry → DataEntryEmission`
- Filter: `CarbonReport.unit_id == unit_id`, `CarbonReportModule.status == ModuleStatus.VALIDATED`, `DataEntryEmission.kg_co2eq IS NOT NULL`
- Group by: `CarbonReport.year` (year comes from the carbon report)
- Aggregate: `SUM(DataEntryEmission.kg_co2eq)`
- Order by: year ascending
- No filter on `module_type_id` — sums across ALL module types
- Follows the same join pattern as `get_travel_evolution_over_time` (line 194)

### 1b. Service: [unit_totals_service.py](backend/app/services/unit_totals_service.py)

Add `get_validated_emissions_by_unit(unit_id: int) -> list[dict]`

- Calls the repo method
- Converts kg to tonnes (÷1000) for each year
- Returns list of `{"year": int, "total_tonnes_co2eq": float}`

### 1c. Endpoint: [unit_results.py](backend/app/api/v1/unit_results.py)

Add `GET /{unit_id}/validated-emissions` endpoint. Already mounted at `/unit` prefix (line 25 of `router.py`).

---

## Endpoint 2: HomePage — per-module breakdown

**Route:** `GET /modules-stats/{carbon_report_id}/validated-totals`

**Purpose:** Show per-module tCO2eq breakdown + total for a specific carbon report. Uses `carbon_report_id` directly (frontend already has it from `selectedCarbonReport.id`).

**Response:**

```json
{
  "modules": [
    { "module_type_id": 1, "total_fte": 25.5 },
    { "module_type_id": 2, "total_tonnes_co2eq": 15.0 },
    { "module_type_id": 4, "total_tonnes_co2eq": 41.7 },
    { "module_type_id": 7, "total_tonnes_co2eq": 5.0 }
  ],
  "total_tonnes_co2eq": 61.7,
  "total_fte": 25.5
}
```

- `modules` merges emission stats and FTE stats into one array
- Each item has `module_type_id` and either `total_tonnes_co2eq` or `total_fte`
- `total_tonnes_co2eq` / `total_fte` at root level are the sums

### 2a. Repository: [data_entry_emission_repo.py](backend/app/repositories/data_entry_emission_repo.py)

Add `get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='module_type_id', aggregate_field='kg_co2eq') -> dict[str, float]`

Follows the same pattern as existing `get_stats` but works across all validated modules in a carbon report:

- Join: `DataEntryEmission → DataEntry → CarbonReportModule` (join through DataEntry to get to CarbonReportModule)
- Filter: `CarbonReportModule.carbon_report_id == carbon_report_id`, `CarbonReportModule.status == VALIDATED`, `kg_co2eq IS NOT NULL`
- Group by: `CarbonReportModule.module_type_id`
- Aggregate: `SUM(DataEntryEmission.kg_co2eq)`
- Returns: `{"2": 15000.0, "4": 41700.0, "7": 5000.0}`

### 2b. Repository: [data_entry_repo.py](backend/app/repositories/data_entry_repo.py)

Add `get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='data_entry_type_id', aggregate_field='fte') -> dict[str, float]`

Same pattern but for DataEntry (FTE):

- Join: `DataEntry → CarbonReportModule` (join to get carbon_report_id and status)
- Filter: `CarbonReportModule.carbon_report_id == carbon_report_id`, `CarbonReportModule.status == VALIDATED`
- Group by: `aggregate_by` field
- Aggregate: `SUM(DataEntry.data[aggregate_field].as_float())`
- Returns: `{"1": 15.0, "2": 10.5}` (member + student FTE)
- Only headcount entries have FTE data; other modules' entries return null for `data["fte"]` and are excluded by SUM

### 2c. Endpoint: [carbon_report_module_stats.py](backend/app/api/v1/carbon_report_module_stats.py)

Add `GET /{carbon_report_id}/validated-totals` endpoint. Already mounted at `/modules-stats` prefix.

The endpoint:

- Calls `DataEntryEmissionService.get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='module_type_id', aggregate_field='kg_co2eq')`
- Calls `DataEntryService.get_stats_by_carbon_report_id(carbon_report_id, aggregate_by='data_entry_type_id', aggregate_field='fte')`
- Merges results: emission stats as `{"module_type_id": X, "total_tonnes_co2eq": Y}`, FTE stats as `{"module_type_id": 1, "total_fte": Z}`
- Computes `total_tonnes_co2eq = sum(emission_stats)` and `total_fte = sum(fte_stats)`

---

## Frontend

### API functions: [modules.ts](frontend/src/api/modules.ts)

**Function 1:** `getValidatedEmissions(unitId: number)` — calls `GET /unit/{unitId}/validated-emissions`, returns `{ emissions_data: Array<{year, total_tonnes_co2eq}> }`

**Function 2:** `getValidatedTotals(carbonReportId: number)` — calls `GET /modules-stats/{carbonReportId}/validated-totals`, returns `{ modules, total_tonnes_co2eq, total_fte }`

### Integration: WorkspaceSetupPage / YearSelector

Use `getValidatedEmissions` after unit selection to populate the tCO2eq column per year in YearSelector.

### Integration: HomePage

Use `getValidatedTotals` to display per-module validated emissions and the year total.

---

## Files Modified

| File                                                   | Change                                                                   |
| ------------------------------------------------------ | ------------------------------------------------------------------------ |
| `backend/app/repositories/data_entry_emission_repo.py` | Add `get_validated_totals_by_unit()` + `get_stats_by_carbon_report_id()` |
| `backend/app/repositories/data_entry_repo.py`          | Add `get_stats_by_carbon_report_id()`                                    |
| `backend/app/services/unit_totals_service.py`          | Add `get_validated_emissions_by_unit()`                                  |
| `backend/app/services/data_entry_emission_service.py`  | Add `get_stats_by_carbon_report_id()` (delegates to repo)                |
| `backend/app/services/data_entry_service.py`           | Add `get_stats_by_carbon_report_id()` (delegates to repo)                |
| `backend/app/api/v1/unit_results.py`                   | Add `GET /{unit_id}/validated-emissions` endpoint                        |
| `backend/app/api/v1/carbon_report_module_stats.py`     | Add `GET /{carbon_report_id}/validated-totals` endpoint                  |
| `frontend/src/api/modules.ts`                          | Add `getValidatedEmissions()` + `getValidatedTotals()` + interfaces      |

## Verification

1. Call `GET /api/v1/unit/{id}/validated-emissions` — verify response contains per-year totals from validated modules only
2. Call `GET /api/v1/modules-stats/{carbon_report_id}/validated-totals` — verify per-module breakdown with correct module_type_id keys
3. Non-validated modules (status 0 or 1) must not appear in either endpoint
4. Headcount FTE must come from `DataEntry.data["fte"]`, not from `DataEntryEmission`
5. A unit with no validated modules returns empty `emissions_data` array / zero totals
