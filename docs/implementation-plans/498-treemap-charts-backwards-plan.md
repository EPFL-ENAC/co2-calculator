# Treemap Charts Revert — Implementation Plan

## Context

The `498-featresults-charts-charts-per-module-treemaps` and `fix/chart-corrections` branches introduced per-module treemap charts and moved treemap hierarchy-building from frontend composables into the backend. This plan covers reverting to the architecture where:

- **Frontend composables** (`useEmissionTreemap.ts`, `useModuleChartData.ts`) own treemap hierarchy construction from flat emission rows
- **Backend** `/emission-breakdown` returns only the original flat structure — no `module_treemap` or `module_breakdown_parents` keys
- **`ModuleCharts.vue`** uses `useModuleChartData()` composable, not inline watchers and tree-building functions

Key decisions:

- **No backend treemap logic**: `emission_breakdown.py` keeps only the original chart key derivation and `build_chart_breakdown()` returning the flat breakdown. All new treemap helper functions are out of scope.
- **Composable-owned hierarchy**: `useEmissionTreemap.ts` exposes `buildModuleTreemapData()` and `buildResultsTreemapData()`; `useModuleChartData.ts` wraps fetching + tree-building with a cache guard.
- **Original `allValueKeys`**: `ModuleCarbonFootprintChart.vue` uses the original 11-key list. YY subcategory keys (`co2`, `ch4`, `n2o`, `refrigerants`, `combustion`, `clouds`, `ai`, etc.) are not needed.
- **No YY colour system**: `GenericEmissionTreeMapChart.vue` uses simple colour assignment; the multi-level `levelColor`/`getCategoryScale`/`getFixedSubcategoryColor` functions and `CHART_CATEGORY_COLOR_SCALES`/`CHART_SUBCATEGORY_COLOR_SCHEMES` constants are not part of this implementation.
- **Validation via `HIDDEN_MAIN_CATEGORIES`**: `ModuleCarbonFootprintChart.vue` skips the `Energy combustion` category rather than zero-filling unvalidated categories.

---

## Approach

### `GET /{carbon_report_id}/emission-breakdown`

The endpoint response shape stays as defined in `252-chart-results-endpoint.md`. No new keys are added.

```json
{
  "module_breakdown": [...],
  "additional_breakdown": [...],
  "per_person_breakdown": {...},
  "validated_categories": [...],
  "total_tonnes_co2eq": 61.7,
  "total_fte": 25.5
}
```

Frontend composables consume this flat structure and build the treemap hierarchy locally.

---

## Step 1: Update `emission_breakdown.py`

**`backend/app/utils/emission_breakdown.py`** — the file should only contain the original helpers and constants from the `252-chart-results-endpoint` implementation:

- `_is_headcount_only()`, `_get_category()`, `_to_chart_key()` (original signature)
- `build_chart_breakdown()` returning only: `module_breakdown`, `additional_breakdown`, `per_person_breakdown`, `validated_categories`, `total_tonnes_co2eq`, `total_fte`

Functions not in scope: `_resolve_emission_type`, `_num`, `_node_value`, `_sum_node_values`, `_sum_object_values`, `_primary_or_sum`, `_apply_chart_aggregates`, `_apply_percentages`, `_build_category_treemap_nodes`.

`CATEGORY_CHART_KEYS` should use the original flat keys:

```python
CATEGORY_CHART_KEYS: dict[str, list[str]] = {
    "Processes": [],
    "Buildings energy consumption": ["energy"],
    "Buildings room": ["grey_energy"],
    "Equipment": ["scientific", "it", "other"],
    "External cloud & AI": ["stockage", "virtualisation", "calcul", "ai_provider"],
    "Purchases": [],
    "Research facilities": [],
    "Professional travel": ["plane", "train"],
}
```

`build_chart_breakdown()` should not include:

- Parent-child hierarchy tracking
- Energy combustion merge
- Multi-gas process emission aggregation
- AI provider aggregation
- Cloud subcategory aggregation

---

## Step 2: Revert Minor Backend Changes

**`backend/app/api/v1/carbon_report_module.py`** — the module save handlers should not call `recompute_stats()`; remove those 3 calls.

**`backend/app/repositories/data_entry_repo.py`**, **`data_entry_emission_repo.py`**, **`data_entry_emission_service.py`**, **`data_entry_emission_type_map.py`**, **`distance_geography.py`**, **`professional_travel/schemas.py`** — revert to state before these branches.

---

## Step 3: Create `useEmissionTreemap.ts`

**New file** `frontend/src/composables/useEmissionTreemap.ts`:

```typescript
export interface EmissionTreemapChild {
  name: string
  value: number
  percentage: number
}

export interface EmissionTreemapCategory {
  name: string
  value: number
  percentage: number
  children: EmissionTreemapChild[]
}

// Builds treemap hierarchy from flat module_breakdown rows returned by the API.
// Uses categoryChartKeys to know which keys are children of each category.
export function buildModuleTreemapData(
  rows: Array<{ category: string; [key: string]: number | string }>,
  categoryChartKeys: Record<string, string[]>,
): EmissionTreemapCategory[] { ... }

// Builds treemap for the results summary page from module_breakdown totals.
export function buildResultsTreemapData(
  moduleBreakdown: Array<{ category: string; [key: string]: number | string }>,
): EmissionTreemapCategory[] { ... }
```

---

## Step 4: Create `useModuleChartData.ts`

**New file** `frontend/src/composables/useModuleChartData.ts`:

```typescript
export function useModuleChartData() {
  // Cache guard — avoids re-fetching when the carbon report has not changed
  const emissionBreakdownCarbonReportId = ref<number | null>(null);

  async function fetchAndBuildChartData(carbonReportId: number) {
    // 1. Call moduleStore.getEmissionBreakdown(carbonReportId)
    // 2. Build EmissionTreemapCategory[] via buildModuleTreemapData() from useEmissionTreemap
    // 3. Update emissionBreakdownCarbonReportId to the fetched id
  }

  return { fetchAndBuildChartData, emissionBreakdownCarbonReportId };
}
```

---

## Step 5: Update `ModuleCharts.vue`

**`frontend/src/components/organisms/module/ModuleCharts.vue`**:

- Import and use `useModuleChartData()` composable
- Remove inline `buildTreemapFromRows()` and `buildModuleTreemapData()` functions
- Remove watchers on `selectedCarbonReport?.value?.id` and `emissionBreakdownRefreshSequence`

```typescript
import { useModuleChartData } from "@/composables/useModuleChartData";
const { fetchAndBuildChartData } = useModuleChartData();
```

---

## Step 6: Update `GenericEmissionTreeMapChart.vue`

**`frontend/src/components/charts/GenericEmissionTreeMapChart.vue`**:

- Import types from the composable rather than defining them inline:

```typescript
import type {
  EmissionTreemapChild,
  EmissionTreemapCategory,
} from "@/composables/useEmissionTreemap";
```

- Treemap node generation consumes the `EmissionTreemapCategory[]` structure produced by the composable — no level-based colour logic needed
- Not in scope: `TREEMAP_LABEL_KEY_MAP`, `resolveLabel`, `getCategoryScale`, `levelColor`, `getFixedSubcategoryColor`, `toTreemapNode`

---

## Step 7: Update `ModuleCarbonFootprintChart.vue`

**`frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`**:

**`allValueKeys`** — use the original 11-key list:

```typescript
const allValueKeys = [
  "process_emissions",
  "energy",
  "scientific",
  "it",
  "other",
  "plane",
  "train",
  "stockage",
  "virtualisation",
  "calcul",
  "ai_provider",
];
```

**Validation** — use `HIDDEN_MAIN_CATEGORIES` to skip `Energy combustion`:

```typescript
const HIDDEN_MAIN_CATEGORIES = new Set(["Energy combustion"]);
```

**`getPrimaryOrSum()`** — restore:

```typescript
function getPrimaryOrSum(
  entry: Record<string, number>,
  primaryKey: string,
  subKeys: string[],
): number {
  if (entry[primaryKey] !== undefined) return entry[primaryKey];
  return subKeys.reduce((sum, k) => sum + (entry[k] ?? 0), 0);
}
```

Not in scope: `normalizeBreakdownEntry`, `zeroNumericValues`, `isCategoryValidated`, `getSubcategoryColor`.

---

## Step 8: Update `constant/charts.ts`

**`frontend/src/constant/charts.ts`** — not in scope for this implementation:

- `CHART_CATEGORY_COLOR_SCALES`
- `CHART_SUBCATEGORY_COLOR_SCHEMES`
- `getChartSubcategoryColor()`

---

## Step 9: Update `stores/modules.ts`

**`frontend/src/stores/modules.ts`** — the module store should not include an emission breakdown refresh sequence. Not in scope:

- `emissionBreakdownRefreshSequence` state
- `invalidateEmissionBreakdown()` method
- `consumeEmissionBreakdownRefreshRequest()` method

---

## Step 10: Update `i18n/results.ts`

**`frontend/src/i18n/results.ts`** — YY subcategory label keys are not needed. The following keys (and their French equivalents) should not be present:

```
co2, ch4, n2o, refrigerants, combustion, clouds, ai,
scientific_equipment, it_equipment, consumable_accessories,
biological_chemical_gaseous, services, vehicles, additional
```

---

## Step 11: Tests

Remove test cases that cover treemap-specific logic introduced by these branches:

- `backend/tests/unit/utils/test_emission_breakdown.py` — remove treemap helper tests; keep the original `build_chart_breakdown` tests from `252-chart-results-endpoint`
- `backend/tests/unit/repositories/test_data_entry_emission_repo.py` — remove tests added in these branches

---

## Files Modified

| File                                                                    | Change                                                                             |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `backend/app/utils/emission_breakdown.py`                               | Remove treemap helpers, revert `build_chart_breakdown()` and `CATEGORY_CHART_KEYS` |
| `backend/app/api/v1/carbon_report_module.py`                            | Remove 3 `recompute_stats()` calls                                                 |
| `backend/app/repositories/data_entry_repo.py`                           | Revert ~22 added lines                                                             |
| `backend/app/repositories/data_entry_emission_repo.py`                  | Restore 1 deleted line                                                             |
| `backend/app/services/data_entry_emission_service.py`                   | Revert 10 lines                                                                    |
| `backend/app/utils/data_entry_emission_type_map.py`                     | Revert 15 lines                                                                    |
| `backend/app/utils/distance_geography.py`                               | Revert 33 lines                                                                    |
| `backend/app/modules/professional_travel/schemas.py`                    | Revert 49 lines                                                                    |
| `frontend/src/composables/useEmissionTreemap.ts`                        | **NEW** — ~105 lines                                                               |
| `frontend/src/composables/useModuleChartData.ts`                        | **NEW** — ~42 lines                                                                |
| `frontend/src/components/organisms/module/ModuleCharts.vue`             | Use `useModuleChartData()` composable; remove inline tree-building                 |
| `frontend/src/components/charts/GenericEmissionTreeMapChart.vue`        | Import types from composable; remove level-colour system                           |
| `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue` | Restore `getPrimaryOrSum()`, `HIDDEN_MAIN_CATEGORIES`, original `allValueKeys`     |
| `frontend/src/stores/modules.ts`                                        | Remove refresh sequence state and methods                                          |
| `frontend/src/constant/charts.ts`                                       | Remove colour scale constants                                                      |
| `frontend/src/i18n/results.ts`                                          | Remove YY subcategory label keys                                                   |
| `backend/tests/unit/utils/test_emission_breakdown.py`                   | Remove treemap-specific tests                                                      |
| `backend/tests/unit/repositories/test_data_entry_emission_repo.py`      | Remove branch-specific tests                                                       |

---

## Verification

1. `pytest backend/tests/` passes
2. `GET /api/v1/modules-stats/{id}/emission-breakdown` response has no `module_treemap` or `module_breakdown_parents` keys
3. `CATEGORY_CHART_KEYS` has exactly the original 8 categories with the original flat keys
4. `useEmissionTreemap.ts` exports `EmissionTreemapCategory`, `buildModuleTreemapData`, `buildResultsTreemapData`
5. `ModuleCharts.vue` calls `useModuleChartData()` — no inline tree-building functions
6. `GenericEmissionTreeMapChart.vue` imports types from the composable — no `levelColor` or `getCategoryScale`
7. `ModuleCarbonFootprintChart.vue` `allValueKeys` has exactly 11 entries
8. Module store has no `emissionBreakdownRefreshSequence`, `invalidateEmissionBreakdown`, or `consumeEmissionBreakdownRefreshRequest`
9. `constant/charts.ts` has no `CHART_CATEGORY_COLOR_SCALES` or `CHART_SUBCATEGORY_COLOR_SCHEMES`
10. Frontend charts render without console errors
