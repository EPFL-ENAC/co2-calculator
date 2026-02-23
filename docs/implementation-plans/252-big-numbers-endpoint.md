# Results Page — Single Summary Endpoint

## Context

The ResultsPage displays two layers of "big number" cards (no charts in this scope):

1. **Unit-level totals** (3 cards at top) — total tCO2eq, tCO2eq per FTE, year-over-year %
2. **Per-module totals** (3 cards per expanded module) — same 3 metrics scoped to one module

Currently the page hardcodes most values (`"37'250"`, `"8.2"`, `"-11.3%"`). The existing `GET /unit/{unit_id}/{year}/totals` endpoint is incomplete — it only sums equipment and doesn't return FTE or per-module breakdown. We replace it with a single endpoint keyed by `carbon_report_id` that returns everything the ResultsPage needs in one call.

**Design principle:** One frontend call → one response with unit totals + per-module breakdown + year comparison. The backend reuses existing repo methods and only adds a service method + endpoint route.

---

## Endpoint: Results Summary

**Route:** `GET /modules-stats/{carbon_report_id}/results-summary`

**Purpose:** Feed all big-number cards on the ResultsPage with a single call.

**Response** (tonnes only, car-equivalent computed server-side):

```json
{
  "unit_totals": {
    "total_tonnes_co2eq": 37.25,
    "total_fte": 4532.0,
    "tonnes_co2eq_per_fte": 8.22,
    "equivalent_car_km": 109559,
    "previous_year_total_tonnes_co2eq": 42.0,
    "year_comparison_percentage": -11.3
  },
  "module_results": [
    {
      "module_type_id": 1,
      "total_tonnes_co2eq": 5.0,
      "total_fte": 4532.0,
      "tonnes_co2eq_per_fte": 1.1,
      "equivalent_car_km": 14706,
      "previous_year_total_tonnes_co2eq": 5.5,
      "year_comparison_percentage": -9.1
    },
    {
      "module_type_id": 2,
      "total_tonnes_co2eq": 15.0,
      "total_fte": null,
      "tonnes_co2eq_per_fte": 3.31,
      "equivalent_car_km": 44118,
      "previous_year_total_tonnes_co2eq": 17.0,
      "year_comparison_percentage": -11.8
    }
  ]
}
```

- `module_results` only includes validated modules (status = 2)
- `total_fte` is only set on module_type_id 1 (headcount); null for others
- `tonnes_co2eq_per_fte` uses the unit's total FTE from headcount as denominator
- `equivalent_car_km` = `kg_co2eq / 0.34` (0.34 kg CO2eq per km, backend constant)
- If headcount is not validated, FTE-related fields are null everywhere
- If previous year has no data, `previous_year_*` and `year_comparison_percentage` are null
- Year comparison is computed per-module too, not just at unit level

---

## 1. Repositories (reuse existing methods)

### Emissions: [data_entry_emission_repo.py](backend/app/repositories/data_entry_emission_repo.py) — `get_stats_by_carbon_report_id()` (line 158)

Already does exactly what we need:

- Joins `DataEntryEmission → DataEntry → CarbonReportModule`
- Filters: `carbon_report_id`, `status == VALIDATED`, `kg_co2eq IS NOT NULL`
- Groups by: `module_type_id`
- Returns: `{"2": 15000.0, "4": 41700.0}`

Called once for current year, once for previous year (if exists).

### FTE: [data_entry_repo.py](backend/app/repositories/data_entry_repo.py) — `get_stats_by_carbon_report_id()` (line 134)

Already does exactly what we need:

- Joins `DataEntry → CarbonReportModule`
- Filters: `carbon_report_id`, `status == VALIDATED`
- Default args: `aggregate_by="module_type_id"`, `aggregate_field="fte"`
- Returns: `{"1": 4532.0}` (headcount module FTE)

Called once for current year, once for previous year (if exists).

**No new repo methods needed.**

---

## 2. Service: [unit_totals_service.py](backend/app/services/unit_totals_service.py)

### Add `get_results_summary(carbon_report_id: int)`

1. Load `CarbonReport` by id to get `unit_id` and `year`
2. Look up previous year's `CarbonReport` via `CarbonReportRepository.get_by_unit_and_year(unit_id, year - 1)`
3. Call `DataEntryEmissionRepository.get_stats_by_carbon_report_id(carbon_report_id)` → current emissions per module
4. Call `DataEntryRepository.get_stats_by_carbon_report_id(carbon_report_id)` → current FTE per module
5. If prev report exists, repeat steps 3-4 for `prev_carbon_report_id`
6. Assemble response:
   - For each module in current emissions:
     - `total_tonnes_co2eq = kg / 1000`
     - `tonnes_co2eq_per_fte = (kg / 1000) / total_fte` (total_fte from headcount, key "1")
     - `equivalent_car_km = kg / CO2_PER_KM_KG` where `CO2_PER_KM_KG = 0.34`
     - `previous_year_total_tonnes_co2eq` from prev year emissions (same module)
     - `year_comparison_percentage = (current - prev) / prev * 100`
   - For headcount module: also set `total_fte`
   - Unit totals = sum across all modules

Total DB queries: 3 (load report + 2 stats) or 5 if previous year exists.

---

## 3. Endpoint: [carbon_report_module_stats.py](backend/app/api/v1/carbon_report_module_stats.py)

### Add `GET /{carbon_report_id}/results-summary`

Already mounted at `/modules-stats` prefix (consistent with existing `validated-totals` endpoint).

The endpoint:

- Calls `UnitTotalsService(db).get_results_summary(carbon_report_id)`
- Returns the response directly

---

## 4. Frontend: [ResultsPage.vue](frontend/src/pages/app/ResultsPage.vue)

### Update `fetchUnitTotals` → `fetchResultsSummary`

- Change API call to `modules-stats/${carbonReportId}/results-summary`
- Use `workspaceStore.selectedCarbonReport.id` as the `carbon_report_id`
- Update interface to match new response shape
- Wire top 3 BigNumber cards to `resultsSummary.unit_totals.*`
- Wire per-module BigNumber cards by matching `module_type_id` in `resultsSummary.module_results`
- Show "validate module" placeholder if module not in `module_results`
- Remove hardcoded `"37'250"`, `"8.2"`, `"-11.3%"` values
- Remove `calculateEquivalentKm` function (server-side now)

### Add typed API function: [modules.ts](frontend/src/api/modules.ts)

```ts
interface ResultsSummary {
  unit_totals: {
    total_tonnes_co2eq: number | null;
    total_fte: number | null;
    tonnes_co2eq_per_fte: number | null;
    equivalent_car_km: number | null;
    previous_year_total_tonnes_co2eq: number | null;
    year_comparison_percentage: number | null;
  };
  module_results: Array<{
    module_type_id: number;
    total_tonnes_co2eq: number;
    total_fte: number | null;
    tonnes_co2eq_per_fte: number | null;
    equivalent_car_km: number;
    previous_year_total_tonnes_co2eq: number | null;
    year_comparison_percentage: number | null;
  }>;
}

function getResultsSummary(carbonReportId: number): Promise<ResultsSummary>;
```

---

## Files Modified

| File                                               | Change                                        |
| -------------------------------------------------- | --------------------------------------------- |
| `backend/app/services/unit_totals_service.py`      | Add `get_results_summary(carbon_report_id)`   |
| `backend/app/api/v1/carbon_report_module_stats.py` | Add `GET /{carbon_report_id}/results-summary` |
| `frontend/src/pages/app/ResultsPage.vue`           | Wire big numbers to real API data             |
| `frontend/src/api/modules.ts`                      | Add `getResultsSummary()` + interfaces        |

## Verification

1. Call `GET /api/v1/modules-stats/{carbon_report_id}/results-summary` — verify `unit_totals` sums all validated modules
2. Verify `module_results` only contains validated modules (non-validated excluded)
3. Verify `total_fte` comes from headcount module's `DataEntry.data["fte"]`, not from emissions
4. Verify `equivalent_car_km` = kg_co2eq / 0.34 for both unit and module level
5. Verify `tonnes_co2eq_per_fte` = total_tonnes / total_fte using headcount FTE
6. Verify year comparison works: previous year null when no data exists
7. Verify a carbon report with zero validated modules returns null totals and empty `module_results`
8. Frontend big numbers display real values, no more hardcoded strings
