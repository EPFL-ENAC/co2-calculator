# Updated Charts Implementation Plan

## 1. Build New Chart

- New Chart is a horiziontal barcharts with each bar having segment similarly to Carbon Footprint chart
- It should use Emission types to get data from each module
- Their should be a switch to toggle between Emission Breakdown and new charts
- It should integrate in results page, The module page and the reporting tab in Backoffice

---

## Detailed Implementation Plan

### Overview

The new chart ("Emission Type Breakdown Chart") is a **horizontal stacked bar chart per module** based on the EmissionType 6-digit scheme (`XX YY ZZ`):

- Each **bar** represents an **XX category** (e.g., for Professional Travel: `Trains`, `Planes`)
- Each **segment** within a bar represents a **YY subcategory** (e.g., for Planes: `first`, `business`, `eco`)
- The orientation is **horizontal** (category axis = Y, value axis = X)

**Mapping to EmissionType hierarchy:**

```
XX YY ZZ scheme:
  XX = category   → becomes a BAR on Y axis
  YY = subcategory → becomes a SEGMENT within that bar
  ZZ = item       → aggregated into its YY parent
```

**Examples per module:**
| Module | Bars (XX categories) | Segments (YY subcategories) |
|---|---|---|
| Professional Travel | Trains, Planes | class_1, class_2 / first, business, eco |
| Buildings | Rooms, Combustion | lighting, cooling, ventilation, heating_elec / heating_thermal |
| Equipment | (single XX) | scientific, it, other |
| Process Emissions | (single XX) | co2, ch4, n2o, refrigerants |
| Purchases | (single XX) | goods_and_services, scientific_equipment, it_equipment, consumable_accessories, biological_chemical_gaseous, services, vehicles, additional, other |
| External Cloud & AI | Clouds, AI | virtualisation, calcul, stockage / provider_google, provider_openai, ... |

For modules with a **single XX category** (e.g., Equipment), the chart shows one bar with YY subcategories as segments.
For modules with **multiple XX categories** (e.g., Professional Travel), each XX is a separate bar.

The chart reuses the **same `EmissionBreakdownResponse` data** already fetched by `moduleStore.getEmissionBreakdown()`. The `emissions` array in each `EmissionBreakdownCategoryRow` provides `key` (YY leaf), `value`, and optional `parent_key` (XX category) — which maps directly to this bar/segment structure. **No new backend endpoint is needed**.

---

### Step 1: Create the New Chart Component

**File:** `frontend/src/components/charts/results/EmissionTypeBreakdownChart.vue`

**What it does:**

- Renders a **horizontal** ECharts `BarChart` for a **single module's category row(s)**
- Y axis (bars) = parent emission type keys or leaf keys (e.g., `plane`, `train` for Professional Travel)
- Stacked segments per bar = child emission type keys when 2-level types exist (e.g., `first`, `business`, `eco` under `plane`)
- Colors use existing `CHART_SUBCATEGORY_COLOR_SCHEMES` / `getChartSubcategoryColor()` from `constant/charts.ts`

**Props:**

```ts
defineProps<{
  categoryRows: EmissionBreakdownCategoryRow[]; // filtered rows for this module
  categoryKey: string; // e.g. 'professional_travel' — for color lookup
  validated: boolean;
}>();
```

**Data transformation logic:**

1. Take `categoryRows[].emissions` (each has `key` = YY subcategory, `value`, optional `parent_key` = XX category)
2. Group emissions by `parent_key` (XX category). If no `parent_key`, the emission itself is an XX-level leaf — use the `category_key` as the single bar
3. Each XX group becomes a **bar** on the Y axis (e.g., `plane`, `train`)
4. Within each XX group, each YY emission becomes a **segment** (e.g., `first`, `business`, `eco`)
5. Build ECharts dataset:
   ```
   source = [
     { xx_category: 'plane', first: 1.2, business: 3.5, eco: 2.1 },
     { xx_category: 'train', class_1: 0.8, class_2: 0.5 },
   ]
   ```
6. Build series dynamically from all unique YY keys found across all bars

**ECharts config:**
| Setting | Value |
|---|---|
| Orientation | Horizontal: `yAxis: { type: 'category' }`, `xAxis: { type: 'value' }` |
| Stack | All series stacked (`stack: 'total'`) |
| Y axis labels | Translated XX category names (e.g., "Planes", "Trains") |
| Tooltip | Show YY segment breakdown + bar total |
| No scope overlays | Not applicable for per-module view |

**Key implementation details:**

- Series are **built dynamically** based on the YY subcategory keys present in the data (not hardcoded like `ModuleCarbonFootprintChart`)
- Color lookup: `getChartSubcategoryColor(categoryKey, yyKey, fallback)`
- Include download PNG/CSV buttons (copy pattern from existing chart)
- For modules with a single XX category (e.g., Equipment): one bar with `scientific`, `it`, `other` as segments
- For modules with multiple XX categories (e.g., Professional Travel): multiple bars, each with its own YY segments

---

### Step 2: Add Chart Toggle Switch

**Where:** Inside each integration point (Results page, Module page, Backoffice)

**Behavior:**

- `q-btn-toggle` with two options:
  - **"Emission Breakdown"** → shows existing chart (vertical stacked bar / treemap)
  - **"Emission Type"** → shows new per-module horizontal charts
- Default view: "Emission Breakdown" (preserves current behavior)
- Toggle state is local (per page), stored in a `ref`

**Implementation pattern (Results page example):**

```vue
<q-btn-toggle
  v-model="chartView"
  :options="[
    { label: t('charts-emission-breakdown'), value: 'breakdown' },
    { label: t('charts-emission-type'), value: 'type' },
  ]"
/>
<!-- Existing view -->
<ModuleCarbonFootprintChart
  v-if="chartView === 'breakdown'"
  :breakdown-data="breakdownData"
/>
<!-- New view: one EmissionTypeBreakdownChart per module category -->
<template v-else>
  <EmissionTypeBreakdownChart
    v-for="row in breakdownData.module_breakdown"
    :key="row.category_key"
    :category-rows="[row]"
    :category-key="row.category_key"
    :validated="breakdownData.validated_categories.includes(row.category_key)"
  />
</template>
```

---

### Step 3: Integrate in Results Page

**File:** `frontend/src/pages/app/ResultsPage.vue`

**Changes:**

1. Import `EmissionTypeBreakdownChart`
2. Add a `chartView` ref (`'breakdown' | 'type'`)
3. Add toggle UI above the chart area (next to existing download buttons)
4. When `'breakdown'`: show existing `ModuleCarbonFootprintChart` (unchanged)
5. When `'type'`: loop over `breakdownData.module_breakdown` and render one `EmissionTypeBreakdownChart` per category row — each chart shows that module's emission types as horizontal bars
6. The `CarbonFootPrintPerPersonChart` below remains unchanged (always visible)

**No data flow changes** — both views consume the same `moduleStore.state.emissionBreakdown`.

---

### Step 4: Integrate in Module Page

**File:** `frontend/src/components/organisms/module/ModuleCharts.vue`

**Changes:**

1. Add toggle between existing `GenericEmissionTreeMapChart` and the new `EmissionTypeBreakdownChart`
2. Filter `breakdownData.module_breakdown` to only the categories relevant to the current module (using existing `MODULE_TO_CATEGORIES` from `constant/charts.ts`)
3. Pass the filtered category rows to `EmissionTypeBreakdownChart`

**Example:** On the Professional Travel module page, the chart shows 2 bars (plane, train) with class segments — giving a detailed view of where emissions come from within that module.

---

### Step 5: Integrate in Backoffice Reporting Tab

**File:** `frontend/src/pages/back-office/ReportingPage.vue`

**Changes:**

1. The reporting page currently shows unit tables with completion status — it does **not** currently display emission charts
2. Add a new section/card to the reporting page that shows the `EmissionTypeBreakdownChart`
3. This requires fetching `emissionBreakdown` for the selected unit(s) — will need to call `moduleStore.getEmissionBreakdown(carbonReportId)` when a unit is selected
4. Add the same toggle switch between breakdown and emission type views
5. If multiple units are selected, either:
   - Show chart for the first/selected unit only, or
   - Aggregate data across units (requires a new backend endpoint — **defer to Phase 2**)

**Recommended approach for Phase 1:** Show chart when a single unit row is expanded/selected in the table, using that unit's `carbon_report_id`.

---

### Step 6: i18n Keys

**File:** `frontend/src/i18n/` (relevant locale files)

**New keys needed:**

- `charts-emission-breakdown` → "Emission Breakdown"
- `charts-emission-type` → "Emission Type"
- `charts-emission-type-title` → "Emission Type Breakdown" (chart title)

---

### Step 7: Testing & QA Checklist

- [ ] New chart renders correctly with real data (all modules populated)
- [ ] New chart handles empty/zero data gracefully (no bars shown)
- [ ] Toggle switches correctly between views without losing state
- [ ] Unvalidated modules appear greyed out (same as existing chart)
- [ ] Additional data toggle (commuting/food/waste) works on new chart
- [ ] Download PNG works for new chart
- [ ] Download CSV works for new chart
- [ ] Tooltip shows correct subcategory breakdown per bar
- [ ] Colorblind mode applies correctly (existing `colors` computed ref handles this)
- [ ] Chart appears in Results page, Module page, and Backoffice reporting
- [ ] Responsive: chart resizes properly (autoresize from vue-echarts)

---

### File Change Summary

| File                                                                    | Action                                                                                              |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `frontend/src/components/charts/results/EmissionTypeBreakdownChart.vue` | **CREATE** — new per-module horizontal stacked bar chart                                            |
| `frontend/src/pages/app/ResultsPage.vue`                                | **EDIT** — add toggle, render one chart per module in "type" view                                   |
| `frontend/src/components/organisms/module/ModuleCharts.vue`             | **EDIT** — add toggle + new chart option (filtered to current module)                               |
| `frontend/src/pages/back-office/ReportingPage.vue`                      | **EDIT** — add chart section with toggle                                                            |
| `frontend/src/i18n/*.ts`                                                | **EDIT** — add new i18n keys                                                                        |
| Backend                                                                 | **NO CHANGES** — reuses existing `emission-breakdown` endpoint + `emissions[].parent_key` structure |
