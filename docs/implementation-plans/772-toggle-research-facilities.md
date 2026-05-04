# Toggle Research Facilities

## Overview

Add a "Show Research Facilities" checkbox to the results page header (below "View Uncertainties") that shows/hides research facilities data in the carbon footprint charts and summary totals.

Filtering is done **backend-side** via a generic `exclude_modules` query param (a list of `module_type_id` integers). The research facilities toggle passes `ModuleTypeEnum.research_facilities = 6` into that list when off.

---

## Tasks

### 1. Backend — add `exclude_modules` query param to the endpoint

**File**: `backend/app/api/v1/carbon_report_module_stats.py`

```python
from fastapi import Query

@router.get("/{carbon_report_id}/emission-breakdown")
async def get_emission_breakdown(
    carbon_report_id: int,
    exclude_modules: list[int] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ...
    return build_chart_breakdown(
        rows=emission_rows,
        total_fte=total_fte,
        headcount_validated=headcount_validated,
        validated_module_type_ids=validated_module_type_ids,
        exclude_module_type_ids=set(exclude_modules),
    )
```

FastAPI serialises repeated query params automatically: `?exclude_modules=6&exclude_modules=2`.

---

### 2. Backend — filter in `build_chart_breakdown`

**File**: `backend/app/utils/emission_category.py`

**2a.** Add `exclude_module_type_ids: set[int] = frozenset()` parameter to `build_chart_breakdown` (line 493).

**2b.** Skip rows whose `module_type_id` is in the exclusion set in the row-processing loop (lines 537–553):

```python
for row in rows:
    module_type_id, emission_type_id, kg_co2eq = row
    if module_type_id in exclude_module_type_ids:   # <-- new guard
        continue
    emission_type = _resolve_emission_type(emission_type_id)
    ...
```

Filtering by `module_type_id` directly (rather than by derived category) is simpler and guarantees all emission types belonging to that module are excluded. The exclusion cascades automatically through `module_breakdown`, `per_person_breakdown` (via `module_totals_kg`), `validated_categories`, and `total_tonnes_co2eq`.

---

### 3. Backend — add unit test

**File**: `backend/tests/unit/utils/test_emission_category.py`

Add a test that calls `build_chart_breakdown` with `exclude_module_type_ids={6}` (research facilities) and asserts:

- No row in `module_breakdown` has `category_key == 'research_facilities'`
- `per_person_breakdown['research_facilities'] == 0.0`
- `total_tonnes_co2eq` is lower than the same call without exclusions

Also add a test for excluding multiple modules to verify the generic behaviour.

---

### 4. Frontend — update the store action

**File**: `frontend/src/stores/modules.ts`

Update `getEmissionBreakdown` to accept an optional set of module type IDs to exclude and serialise them as repeated query params:

```ts
async getEmissionBreakdown(carbonReportId: number, excludeModules: number[] = []) {
  const params = new URLSearchParams()
  excludeModules.forEach((id) => params.append('exclude_modules', String(id)))
  const qs = params.toString() ? `?${params.toString()}` : ''
  // fetch from `modules-stats/${carbonReportId}/emission-breakdown${qs}`
}
```

Invalidate the cache (`invalidateEmissionBreakdown()`) before re-fetching when the excluded set changes.

---

### 5. Frontend — add i18n key

**File**: `frontend/src/i18n/en.ts` (and other locale files)

```ts
results_show_research_facilities: "Show Research Facilities";
```

---

### 6. Frontend — add toggle checkbox to ResultsPage

**File**: `frontend/src/pages/app/ResultsPage.vue`

**6a.** Add reactive ref near `viewUncertainties` (around line 110):

```ts
const showResearchFacilities = ref(true);
```

**6b.** Derive the excluded modules list from all toggles:

```ts
const excludedModules = computed(() => {
  const ids: number[] = [];
  if (!showResearchFacilities.value) ids.push(6); // ModuleTypeEnum.research_facilities
  return ids;
});
```

**6c.** Watch and re-fetch when the excluded set changes:

```ts
watch(
  excludedModules,
  async (ids) => {
    moduleStore.invalidateEmissionBreakdown();
    await moduleStore.getEmissionBreakdown(carbonReportId, ids);
  },
  { deep: true },
);
```

**6d.** Add checkbox in the template directly below the `viewUncertainties` checkbox (around line 177):

```vue
<q-checkbox
  v-model="showResearchFacilities"
  :label="$t('results_show_research_facilities')"
  color="accent"
  class="text-weight-medium"
  size="xs"
/>
```

The `excludedModules` computed means future module toggles only need to push their `module_type_id` into the array — no other changes required.

---

### 7. Frontend — recalculate scope rects in `ModuleCarbonFootprintChart`

**File**: `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`

The chart overlays three `graphic` rects that mark GHG scope boundaries. Their pixel positions and widths are hardcoded in the `scopeConfig` computed (line 48) based on the assumption of **8 main-category bars**:

| Scope | Bars covered                                                                   | Current width |
| ----- | ------------------------------------------------------------------------------ | ------------- |
| 1     | process_emissions, buildings_room                                              | 108 px        |
| 2     | buildings_energy_combustion, equipment                                         | 108 px        |
| 3     | external_cloud_and_ai, purchases, professional_travel, **research_facilities** | 330 px        |

When `research_facilities` is hidden the dataset shrinks to **7 bars**. Because ECharts distributes bar width evenly across the plot area, every bar becomes wider and the scope 3 rect must cover only 3 bars instead of 4. Neither of these adjustments happen automatically.

**Why hardcoded values break**: the existing `scopeConfig` bakes in pixel positions for exactly 8 or 12 bars. Every change in visible category count (research_facilities toggle, additional-data toggle, future new modules) requires new hardcoded values. Instead, use ECharts' `convertToPixel` API to derive positions from the actual rendered bar centers, making the rects self-adjusting for any combination of toggles.

**7a.** Add a `showResearchFacilities` prop:

```ts
const props = defineProps<{
  breakdownData?: EmissionBreakdownResponse | null;
  title?: string;
  showResearchFacilities?: boolean;
}>();
```

**7b.** Declare the static scope membership map (raw category keys → GHG scope):

```ts
const CATEGORY_SCOPE: Record<string, 1 | 2 | 3 | "additional"> = {
  process_emissions: 1,
  buildings_room: 1,
  buildings_energy_combustion: 2,
  equipment: 2,
  external_cloud_and_ai: 3,
  purchases: 3,
  professional_travel: 3,
  research_facilities: 3,
  commuting: "additional",
  food: "additional",
  waste: "additional",
  embodied_energy: "additional",
};
```

**7c.** Build a reverse map from translated label → raw category key so `datasetSource` entries (which carry translated labels) can be looked up in `CATEGORY_SCOPE`:

```ts
const labelToKey = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {};
  for (const [key, i18nKey] of Object.entries(CATEGORY_LABEL_MAP)) {
    map[t(i18nKey)] = key;
  }
  return map;
});
```

**7d.** Replace `scopeConfig` with a reactive `scopeRects` ref and a `recalculateScopeRects()` function that runs after every chart render:

```ts
interface ScopeRect {
  left: number;
  width: number;
}
interface ScopeRects {
  scope1: ScopeRect | null;
  scope2: ScopeRect | null;
  scope3: ScopeRect | null;
  dividerX: number | null; // x pixel of main/additional divider line
}

const scopeRects = ref<ScopeRects>({
  scope1: null,
  scope2: null,
  scope3: null,
  dividerX: null,
});

function recalculateScopeRects() {
  const chart = chartRef.value?.chart;
  if (!chart) return;

  const items = datasetSource.value;
  if (items.length < 2) return;

  // convertToPixel returns x-pixel of the category center relative to the chart canvas
  const getX = (label: string): number =>
    chart.convertToPixel({ xAxisIndex: 0 }, label) as number;

  // Half a bar-slot width = half the distance between adjacent bar centers
  const step =
    getX(String(items[1].category)) - getX(String(items[0].category));
  const halfStep = step / 2;

  // Group translated labels by scope using the reverse map
  const groups: Record<string, string[]> = {
    "1": [],
    "2": [],
    "3": [],
    additional: [],
  };
  for (const item of items) {
    const label = String(item.category);
    const key = labelToKey.value[label] ?? "";
    const scope = String(CATEGORY_SCOPE[key] ?? "additional");
    groups[scope].push(label);
  }

  const toRect = (labels: string[]): ScopeRect | null => {
    if (!labels.length) return null;
    const left = getX(labels[0]) - halfStep;
    const right = getX(labels[labels.length - 1]) + halfStep;
    return { left, width: right - left };
  };

  scopeRects.value = {
    scope1: toRect(groups["1"]),
    scope2: toRect(groups["2"]),
    scope3: toRect(groups["3"]),
    dividerX: groups["additional"].length
      ? getX(groups["additional"][0]) - halfStep
      : null,
  };
}
```

Register it on the chart's `finished` event (fires after every render including resize, because the component already uses `autoresize`):

```ts
watch(
  chartRef,
  (chart) => {
    chart?.chart?.on("finished", recalculateScopeRects);
  },
  { immediate: true },
);
```

The recalculation trigger chain on toggle:

1. `breakdownData` changes (research_facilities absent) → `datasetSource` computed drops that category → `chartOption` computed re-runs → ECharts re-renders the bars
2. ECharts fires `finished` → `recalculateScopeRects()` calls `convertToPixel` on the new bar layout → `scopeRects` ref updates
3. `scopeRects` change → `chartOption` re-runs (graphic array now has correct positions) → ECharts updates the overlays
4. ECharts fires `finished` again → `recalculateScopeRects()` runs but `scopeRects` values are identical → no further updates (stable)

The same chain fires on container resize (step 1 is replaced by the resize event, rest is identical).

**7e.** Rewrite the `graphic` array in `chartOption` to consume `scopeRects` instead of the old `scopeConfig` numbers. Each scope rect maps directly to an overlay element:

```ts
graphic: [
  // Scope 1
  ...(scopeRects.value.scope1 ? [{
    type: 'rect',
    left: scopeRects.value.scope1.left,
    top: '15px',
    shape: { width: scopeRects.value.scope1.width, height: 300 },
    style: { fill: new graphic.LinearGradient(...) },
  }, {
    type: 'text',
    left: scopeRects.value.scope1.left + 10,
    top: '30px',
    style: { text: t('charts-scope') + ' 1', ... },
  }] : []),
  // Scope 2 — same pattern
  // Scope 3 — same pattern
  // Additional-data divider line
  ...(scopeRects.value.dividerX !== null && toggleAdditionalData.value ? [{
    type: 'rect', // vertical divider
    left: scopeRects.value.dividerX,
    ...
  }] : []),
],
```

This eliminates all four hardcoded branches. Adding or removing any visible category — research_facilities toggle, additional-data toggle, or any future module toggle — automatically repositions the rects without any code changes to the chart component.

**7f.** No prop threading needed from `ResultsPage` for this task — the chart already reacts to `breakdownData` changing (research_facilities absent from data → absent from `datasetSource` → `recalculateScopeRects` fires on next `finished` event). The `showResearchFacilities` prop added in 7a is only needed if the chart must render a placeholder or style differently when the module is hidden; if not, it can be omitted.

> **Note on `CarbonFootPrintPerPersonChart`**: that chart has a single horizontal bar row ("My unit"), so its background rect spans the full bar group and requires no adjustment.

---

## Data Flow

```
User toggles "Show Research Facilities" checkbox
  ↓
showResearchFacilities ref changes → excludedModules computed = [6]
  ↓
watcher invalidates store cache + calls getEmissionBreakdown(id, [6])
  ↓
GET /modules-stats/{id}/emission-breakdown?exclude_modules=6
  ↓
build_chart_breakdown() skips all rows where module_type_id == 6
  ↓
Response has no research_facilities in module_breakdown / per_person / totals
  ↓
Store updates → charts re-render automatically
```

---

## Affected Files

| File                                                                    | Change                                                                                             |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module_stats.py`                      | Add `exclude_modules` query param, forward as `exclude_module_type_ids`                            |
| `backend/app/utils/emission_category.py`                                | Add `exclude_module_type_ids` param to `build_chart_breakdown`, skip rows                          |
| `backend/tests/unit/utils/test_emission_category.py`                    | Add tests for single and multiple module exclusions                                                |
| `frontend/src/stores/modules.ts`                                        | Accept `excludeModules: number[]`, serialise as repeated query params                              |
| `frontend/src/i18n/en.ts` (+ other locales)                             | Add `results_show_research_facilities` key                                                         |
| `frontend/src/pages/app/ResultsPage.vue`                                | Add ref, `excludedModules` computed, watcher, checkbox; pass prop to chart                         |
| `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue` | Replace hardcoded `scopeConfig` with `convertToPixel`-based `scopeRects`; add scope membership map |
