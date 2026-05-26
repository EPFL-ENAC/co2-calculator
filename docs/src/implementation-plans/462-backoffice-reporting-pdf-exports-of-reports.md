# PDF Export for Backoffice Reporting — Implementation Plan

Issue: #462 — `feat/462-backoffice-reporting-pdf-exports-of-reports`

## Context

The backoffice reporting page has an export section (`ReportExport.vue`) with four report types. The PDF button currently renders but has **no `@click` handler** (line 287–295 of `ReportExport.vue`).

Per the official spec (`CalcCo2_Spec_exportation_PDF`):

| Report type                   | PDF                                                            |
| ----------------------------- | -------------------------------------------------------------- |
| Utilisation                   | ❌ No PDF                                                      |
| Détails de données par module | ❌ No PDF                                                      |
| **Résultats**                 | ✅ Same as Results page PDF, but aggregated for selected units |
| **Combiné**                   | ✅ Print the full backoffice reporting page                    |

The same spec also covers the **regular Results page** (issue #462): export same as current page with all BigNumbers and charts, **except** the "Objectif de réduction" chart (interactive, loses meaning in static PDF).

---

## Approach

Both PDF exports follow the identical pattern already used by `pages/app/ResultsPrintPage.vue`:

1. Resolve a named print route via `router.resolve()`
2. `window.open(url, '_blank')` — opens a new tab
3. The print page uses `PrintLayout.vue` (no header/sidebar chrome), calls `window.print()` on a toolbar button
4. `@media print` CSS hides the toolbar; `ReportPage.vue` wraps content in A4-sized blocks with automatic page breaks

Current filters (`unitFilters` computed in `ReportingPage.vue`) are serialized as a JSON query param (`?filters=<json>`) and read back inside the print pages to re-fetch their own data.

---

## Files to Create

### 1. `frontend/src/composables/print/useBackofficeReportingPrintData.ts`

Reads `?filters=<json>` from the route query, calls `backofficeStore.getUnits(filters)` on mount, and exposes the same computed refs already used in `ReportingPage.vue`:

- `units`, `reportingEmissionBreakdown`, `validatedCount`, `tableTotal`, `usageStats`, `moduleStats`, `totalModules`, `loading`

### 2. `frontend/src/pages/back-office/ReportingPrintPage.vue`

**Combiné PDF print page.** Mirrors the structure of `ResultsPrintPage.vue`:

- Uses `useBackofficeReportingPrintData()` composable
- Toolbar (`.print-hide`) with "Print" button → `window.print()`
- `ReportPage` wrappers for A4 pagination (reuses `src/components/organisms/ReportPage.vue`)
- **Page 1**: Title + `CompletionRateBar` + `ReportingStatCards` / `ReportingStatCardUnit` (big numbers = validated / in-progress / not-started unit counts)
- **Page 2**: `ModuleCarbonFootprintChart` + `CarbonFootPrintPerPersonChart` (2-col grid)
- **Page 3**: `EmissionBreakdownChart`
- `@media print` CSS hides toolbar, preserves multi-col grid layouts

### 3. `frontend/src/composables/print/useBackofficeResultsPrintData.ts`

Same filter reading / fetching pattern. Exposes `reportingEmissionBreakdown`, `validatedCount`, `tableTotal`, `loading`.

### 4. `frontend/src/pages/back-office/BackofficeResultsPrintPage.vue`

**Résultats PDF print page.** Visually mirrors `ResultsPrintPage.vue` but powered by aggregated backoffice data instead of single-workspace `ResultsSummary`:

- Toolbar with print button
- **Page 1**: Title ("Aggregated Results – [year(s)]"), `CompletionRateBar` (shows units-in-scope), total CO₂ and per-FTE BigNumbers derived from `emission_breakdown` totals
- **Page 2**: `ModuleCarbonFootprintChart` + `CarbonFootPrintPerPersonChart`
- **Page 3**: `EmissionBreakdownChart`

> Year-over-year % change BigNumbers are omitted — they require `ResultsSummary` which is not available from the backoffice aggregation API.

> "Objectif de réduction" chart is excluded per spec (interactive chart loses meaning in static PDF). Verify `ResultsPrintPage.vue` also excludes it; if not, fix that too.

---

## Files to Modify

### `frontend/src/router/routes.ts`

Add two new top-level route blocks **before** the main `MainLayout` wrapper, alongside the existing `results/print` block (line 41):

```typescript
{
  path: `/:language(${LANGUAGE_PATTERN})/back-office/reporting/print`,
  component: () => import('layouts/PrintLayout.vue'),
  children: [{
    path: '',
    name: 'backoffice-reporting-print',
    component: () => import('pages/back-office/ReportingPrintPage.vue'),
    meta: { requiresAuth: true, breadcrumb: false, isBackOffice: true },
  }],
},
{
  path: `/:language(${LANGUAGE_PATTERN})/back-office/reporting/results-print`,
  component: () => import('layouts/PrintLayout.vue'),
  children: [{
    path: '',
    name: 'backoffice-results-print',
    component: () => import('pages/back-office/BackofficeResultsPrintPage.vue'),
    meta: { requiresAuth: true, breadcrumb: false, isBackOffice: true },
  }],
},
```

### `frontend/src/components/organisms/backoffice/reporting/ReportExport.vue`

1. Import `useRouter` from `vue-router`.
2. Add `downloadPDF()` function:

```typescript
function downloadPDF() {
  const filtersJson = JSON.stringify(props.unitFilters ?? {});
  if (selectedReport.value === "combined") {
    const url = router.resolve({
      name: "backoffice-reporting-print",
      query: { filters: filtersJson },
    }).href;
    window.open(url, "_blank");
  } else if (selectedReport.value === "results") {
    const url = router.resolve({
      name: "backoffice-results-print",
      query: { filters: filtersJson },
    }).href;
    window.open(url, "_blank");
  }
  // usage / detailed: button is disabled — no-op
}
```

3. Add `@click="downloadPDF"` to the PDF `q-btn`.
4. Add `:disable="selectedReport === 'usage' || selectedReport === 'detailed'"` — grays out the button for the two no-PDF report types.

### `frontend/src/i18n/backoffice_reporting.ts`

Add any missing i18n keys for print page headings, e.g.:

- `backoffice_reporting_print_combined_title`
- `backoffice_reporting_print_results_title`

---

## Filter Serialization

`unitFilters` is JSON-stringified into `?filters=<json>` when opening print pages. Print pages parse `route.query.filters` and pass the result to `backofficeStore.getUnits()`. This cleanly handles the `modules` array (array of objects) without complex nested query-string encoding.

---

## Reused Utilities / Components

| What                                                  | Path                                                                                    |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------- |
| A4 page wrapper                                       | `src/components/organisms/ReportPage.vue`                                               |
| Print layout (no chrome, provides print mode context) | `src/layouts/PrintLayout.vue`                                                           |
| Print mode composable                                 | `src/composables/print/usePrintMode.ts` (auto-provided by PrintLayout)                  |
| Aggregated emission charts                            | `ModuleCarbonFootprintChart`, `CarbonFootPrintPerPersonChart`, `EmissionBreakdownChart` |
| Completion progress bar                               | `CompletionRateBar`                                                                     |
| Usage stat cards                                      | `ReportingStatCards`, `ReportingStatCardUnit`                                           |
| BigNumber display                                     | `src/components/molecules/BigNumber.vue` (has `print-mode` prop)                        |
| Backoffice store                                      | `src/stores/backoffice.ts` → `getUnits()`                                               |

---

## Verification

1. Start the dev server.
2. Open backoffice reporting, apply some filters (year + affiliation).
3. **Combiné** → click **Export as PDF** → new tab opens with unit counts, charts; print button triggers browser dialog; A4 pages break correctly.
4. **Résultats** → click **Export as PDF** → new tab opens with aggregated CO₂ data and charts; print dialog works.
5. **Utilisation / Détails** → PDF button is grayed out (disabled); CSV still works.
6. Confirm "Objectif de réduction" chart does not appear in any print page.
7. Check print preview: each `ReportPage` section breaks to a new A4 page; colors preserved via `print-color-adjust: exact`.
