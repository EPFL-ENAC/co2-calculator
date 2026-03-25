# Implementation Plan: Reporting Aggregated Treemap Chart (#460)

## Objective

Add an **Emission Breakdown** treemap chart to the backoffice reporting page, visualising
aggregated emission data across the currently filtered unit set, with module-level tabs for
drill-down (e.g. Professional Travel, Equipment, …).

The chart must react to the same filter state as the units table, using the
`emission_breakdown` already returned by `GET /backoffice/units`.

## Final Architecture

- Data source: existing `GET /backoffice/units` endpoint (unchanged)
- Treemap hierarchy: built entirely on the frontend from
  `emission_breakdown.module_breakdown` using `useEmissionTreemap.ts` composable
- Chart component: reuse existing `GenericEmissionTreeMapChart.vue`
- No new endpoint introduced

## API Contract

- Endpoint: `GET /backoffice/units` (unchanged)
- Request filters (unchanged): `years`, `path_lvl2`, `path_lvl3`, `path_lvl4`,
  `completion_status`, `search`, `modules`, `page`, `page_size`
- Response fields consumed by the treemap:
  - `emission_breakdown.module_breakdown` — flat per-category rows used as treemap input
  - `emission_breakdown.validated_categories` — used to filter out unvalidated categories

## Composable Contract

`useEmissionTreemap.ts` exposes:

```typescript
export interface EmissionTreemapChild {
  name: string;
  value: number;
  percentage: number;
}

export interface EmissionTreemapCategory {
  name: string;
  value: number;
  percentage: number;
  children: EmissionTreemapChild[];
}

// Builds treemap hierarchy from flat module_breakdown rows.
// Uses categoryChartKeys to determine which keys are children of each category.
export function buildModuleTreemapData(
  rows: Array<{ category: string; [key: string]: number | string }>,
  categoryChartKeys: Record<string, string[]>,
): EmissionTreemapCategory[];

// Builds treemap for the results summary from module_breakdown totals.
export function buildResultsTreemapData(
  moduleBreakdown: Array<{ category: string; [key: string]: number | string }>,
): EmissionTreemapCategory[];
```

`categoryChartKeys` mirrors the backend constant:

```typescript
const CATEGORY_CHART_KEYS: Record<string, string[]> = {
  Processes: [],
  "Buildings energy consumption": ["energy"],
  "Buildings room": ["grey_energy"],
  Equipment: ["scientific", "it", "other"],
  "External cloud & AI": [
    "stockage",
    "virtualisation",
    "calcul",
    "ai_provider",
  ],
  Purchases: [],
  "Research facilities": [],
  "Professional travel": ["plane", "train"],
};
```

## Implementation Status

### Backend

- [x] `emission_breakdown.module_breakdown` already exposed by `/backoffice/units`
- [ ] No additional backend changes required

### Frontend

- [x] Create `frontend/src/composables/useEmissionTreemap.ts`
  - Export `EmissionTreemapChild` and `EmissionTreemapCategory` interfaces
  - Implement `buildModuleTreemapData()` — builds hierarchy from flat `module_breakdown` rows
  - Implement `buildResultsTreemapData()` — top-level category totals for summary treemap
- [x] Update `GenericEmissionTreeMapChart.vue`
  - Import `EmissionTreemapChild` / `EmissionTreemapCategory` from composable instead of
    defining them inline
  - Remove `TREEMAP_LABEL_KEY_MAP`, `resolveLabel`, `getCategoryScale`, `levelColor`,
    `getFixedSubcategoryColor` — replace with simple colour assignment from category color map
- [x] Add treemap to `ReportingPage.vue`
  - Derive `treemapData` from `reportingEmissionBreakdown.module_breakdown` via
    `buildResultsTreemapData()`
  - Render `<GenericEmissionTreeMapChart :data="treemapData" />` below the existing
    `ModuleCarbonFootprintChart` / `CarbonFootPrintPerPersonChart` pair
  - Gate rendering on `treemapData.length > 0`
- [x] Update `ModuleCharts.vue`
  - Replace inline `buildTreemapFromRows()` and `buildModuleTreemapData()` with
    `buildModuleTreemapData()` imported from `useEmissionTreemap.ts`
  - Remove local `BackendTreemapCategory` type; align to composable types

## Validation Checklist

- [ ] Treemap categories match `module_breakdown` category totals exactly
- [ ] Children (subcategories) sum to their parent category value
- [ ] Year and hierarchy filters update table + treemap together
- [ ] Completion filter updates table + treemap together
- [ ] Treemap hides / shows correctly when filtered result set is empty
- [ ] Module-level tab selection renders correct subcategory breakdown
- [ ] Colour assignment is consistent with `ModuleCarbonFootprintChart`

## Non-Goals

- No backend treemap hierarchy construction (`module_treemap`, `module_breakdown_parents`)
- No new aggregation endpoint
- No multi-level colour scales (`CHART_CATEGORY_COLOR_SCALES`, `CHART_SUBCATEGORY_COLOR_SCHEMES`)
- No YY subcategory keys (`co2`, `ch4`, `n2o`, `refrigerants`, …)

## Risks / Follow-ups

- `module_breakdown` is currently page-scoped (current page units only); full filtered
  aggregation across all pages requires a dedicated aggregate query in a follow-up
- `GenericEmissionTreeMapChart.vue` inline type definitions must be removed before the
  composable types can be shared with `ModuleCharts.vue` without duplication
