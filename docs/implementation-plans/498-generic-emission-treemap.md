# Generic Emission Treemap Chart — Implementation Plan

## Context

Currently, `TreeMapModuleChart.vue` exists but is purpose-built for Professional Travel
(single color scheme, travel cabin-class hierarchy). Every other module in the Results page
expansion sections and on individual module pages shows either nothing or only a placeholder.

The goal is a **generic treemap** that:

- Works for every module (Equipment, Purchases, Buildings, External cloud & AI, Process Emissions,
  Research Facilities, Professional Travel)
- Appears both in the **Results page** module expansion sections and on each **module's own page**
  (via `ModuleCharts.vue`)
- Uses the **emission type hierarchy** (6-digit positional scheme already in `EmissionTypeEnum`)
- Applies **consistent colors** matching `ModuleCarbonFootprintChart.vue`'s existing color mappings

No backend changes are needed: the existing `/modules-stats/{id}/emission-breakdown` endpoint
already returns `module_breakdown` — an array of `{category, key1: float, key2: float, ...}`
rows that maps perfectly onto treemap categories → children.

Also fixes a **stale data bug** where the Professional Travel treemap does not update after
data entry saves (only after page reload).

---

## Files to Create

### 1. `frontend/src/components/charts/GenericEmissionTreeMapChart.vue`

A multi-color treemap replacing and generalising `TreeMapModuleChart.vue`.

**Props:**

```ts
defineProps<{
  data: EmissionTreemapCategory[]; // structured, pre-colored data
  height?: string; // default '200px'
  showEvolutionDialog?: boolean; // keep for professional travel compat
}>();

interface EmissionTreemapCategory {
  name: string; // i18n key or raw label
  value: number; // sum of children (tonnes)
  color: string; // hex — from CHART_CATEGORY_COLOR_SCHEMES
  children: {
    name: string;
    value: number;
    percentage?: number;
  }[];
}
```

**Behaviour differences from existing `TreeMapModuleChart.vue`:**

- Each top-level node gets its **own** `itemStyle.color` (not shared from one prop scheme)
- Children inherit their parent's color (same as existing)
- Legend is generated per category with its associated color
- Evolution dialog is kept but only shown when `showEvolutionDialog=true` (Professional Travel)
- Empty/zero-value categories are filtered out (same as existing)

---

## Files to Modify

### 2. `frontend/src/constant/charts.ts`

Add two new exports **below** the existing `colors` object:

```ts
// Maps chart category name → hex color for treemap (matches ModuleCarbonFootprintChart)
export const CHART_CATEGORY_COLOR_SCHEMES: Record<string, string> = {
  "Process Emissions": colors.value.apricot.darker,
  "Buildings energy consumption": colors.value.lilac.darker,
  "Energy combustion": colors.value.lilac.dark,
  "Buildings room": colors.value.skyBlue.darker,
  Equipment: colors.value.mauve.darker,
  "External cloud & AI": colors.value.paleYellowGreen.darker,
  Purchases: colors.value.lavender.darker,
  "Research facilities": colors.value.peach.darker,
  "Professional travel": colors.value.babyBlue.darker,
  Commuting: colors.value.aqua.darker,
  Food: colors.value.mint.darker,
  Waste: colors.value.periwinkle.darker,
  "Grey Energy": colors.value.skyBlue.dark,
};

// Maps Module enum key → category names present in module_breakdown
export const MODULE_TO_CATEGORIES: Record<string, string[]> = {
  "process-emissions": ["Process Emissions"],
  buildings: [
    "Buildings energy consumption",
    "Energy combustion",
    "Buildings room",
  ],
  equipment: ["Equipment"],
  purchase: ["Purchases"],
  "research-facilities": ["Research facilities"],
  "external-cloud-and-ai": ["External cloud & AI"],
  "professional-travel": ["Professional travel"],
};
```

> `colors` is a computed ref; both maps should be wrapped in `computed()` (or used inside
> computed properties in their consumers) to stay reactive to colorblind mode.

### 3. `frontend/src/composables/useEmissionTreemap.ts` _(new)_

Pure transformation utilities (no store calls):

```ts
// Build treemap data for the full results overview (all categories)
function buildResultsTreemapData(
  breakdown: EmissionBreakdownResponse,
): EmissionTreemapCategory[];

// Build treemap data filtered to one module's categories
function buildModuleTreemapData(
  breakdown: EmissionBreakdownResponse,
  moduleKey: string, // Module enum value, e.g. 'equipment'
): EmissionTreemapCategory[];
```

Both functions:

1. Filter `module_breakdown` by relevant categories (using `MODULE_TO_CATEGORIES`)
2. For each category row, extract chart key values (skip `*StdDev` and `category` fields)
3. Compute `children: [{ name: key, value, percentage }]` — filter zero-value keys
4. Look up `CHART_CATEGORY_COLOR_SCHEMES[category]` for the color
5. Compute `value` as sum of children
6. Return `EmissionTreemapCategory[]`

### 4. `frontend/src/composables/useModuleChartData.ts`

**Bug fix — treemap not updating after data entry saves:**

Currently the composable only watches `selectedUnit?.id` and `selectedYear`. When a user
adds/edits/deletes travel entries, `ModuleTable.vue` calls `moduleStore.getModuleData()` which
updates `moduleStore.state.data.retrieved_at`, but `getTravelStatsByClass` (and future chart
fetchers) is never re-triggered.

Add a second watcher on `moduleStore.state.data?.retrieved_at`:

```ts
watch(
  () => moduleStore.state.data?.retrieved_at,
  () => {
    const unitId = workspaceStore.selectedUnit?.id;
    const year = workspaceStore.selectedYear;
    fetchChartData(unitId, year);
  },
);
```

This piggybacks on the existing post-save refresh: every CRUD operation in `ModuleTable.vue`
already calls `moduleStore.getModuleData()`, so no changes are needed in `ModuleTable.vue` or
`SubModuleSection.vue`.

**Also in this file** — fetch `emissionBreakdown` on initialisation so module pages have
chart data without the user visiting the Results page first:

```ts
const carbonReportId = workspaceStore.selectedCarbonReport?.id;
if (carbonReportId && !moduleStore.state.emissionBreakdown) {
  moduleStore.getEmissionBreakdown(carbonReportId);
}
```

### 5. `frontend/src/components/organisms/module/ModuleCharts.vue`

Replace the `professional-travel`-only treemap branch with a generic treemap for **all**
non-headcount modules:

```vue
<template v-else>
  <generic-emission-tree-map-chart
    v-if="moduleTreemapData.length"
    :data="moduleTreemapData"
    :show-evolution-dialog="type === MODULES.ProfessionalTravel"
  />
  <span v-else class="text-body2 text-secondary">
    {{ $t("no-chart-data") }}
  </span>
</template>
```

`moduleTreemapData` is a computed ref built with
`buildModuleTreemapData(moduleStore.state.emissionBreakdown, type)`.

> Remove the existing `TreeMapModuleChart` import and usage. Professional Travel is
> now handled by the generic component with `showEvolutionDialog=true`.

### 6. `frontend/src/pages/app/ResultsPage.vue`

Add a full-unit treemap card between the two summary charts and the "Results by category"
expansion section. `moduleStore.state.emissionBreakdown` is already fetched here — just pass
it through `buildResultsTreemapData()`:

```vue
<q-card flat class="q-mt-xl q-pa-xl">
  <h2 class="text-h5 text-weight-medium">{{ $t('results_treemap_title') }}</h2>
  <generic-emission-tree-map-chart
    v-if="resultsTreemapData.length"
    :data="resultsTreemapData"
    height="320px"
  />
</q-card>
```

---

## i18n additions

```ts
'results_treemap_title': 'Emissions breakdown overview',
'no-chart-data': 'No chart data available yet',
```

---

## Key Reused Code

| Existing asset                                             | Role                                    |
| ---------------------------------------------------------- | --------------------------------------- |
| `frontend/src/constant/charts.ts → colors`                 | Color scale source of truth             |
| `frontend/src/stores/modules.ts → getEmissionBreakdown()`  | Fetches breakdown; reuse as-is          |
| `frontend/src/stores/modules.ts → state.emissionBreakdown` | Shared reactive state                   |
| `TreeMapModuleChart.vue` (ECharts setup, tooltip, legend)  | Pattern to copy/adapt                   |
| `useModuleChartData.ts`                                    | Extended with bug fix + breakdown fetch |

---

## Verification

1. **Bug fix**: add a travel entry on the Professional Travel module page → treemap updates
   without reloading the page.
2. **Results page**: treemap card appears with all non-empty categories, colors match the
   stacked bar chart directly above.
3. **Module expansion (Results page)**: expand each module section → module-specific treemap
   shows only that module's categories with the same colors.
4. **Module data entry page**: navigate directly to Equipment module page (without visiting
   Results first) → treemap renders correctly.
5. **Professional Travel**: evolution dialog button still appears and functions.
6. **Colorblind mode**: toggle colorblind checkbox → treemap colors update reactively.
7. **Zero-data modules**: module with no data shows "No chart data available" fallback.
