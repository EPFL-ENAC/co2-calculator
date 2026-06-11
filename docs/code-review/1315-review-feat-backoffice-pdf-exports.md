# PR #1315 — Code Review (max effort)

**PR**: `feat: add backoffice PDF exports and print pages` by @BenBotros
**Branch**: `feat/462-backoffice-reporting-pdf-exports-of-reports` (rebased onto `origin/dev` `a572434c` + force-pushed)
**Scope**: 15 files, +783/-48 — closes #462 (PDF export for Combiné and Résultats backoffice reports)
**CI**: not re-checked after the new push; the previous run on this branch was clean except for the `Install uv` infrastructure flake — rerun to confirm.

## Verdict: REQUEST CHANGES — three verified P0 bugs

The PDF-export feature has the right SHAPE (print-only Vue pages, route-based PDF preview, filter-state-in-URL, dedicated print composables). But three verified bugs in the wiring make the feature **non-functional on first click** and **regress an existing CSV export**. Plus several P1 correctness issues around URL parsing, store-state leaks, and dead reactive bindings.

## P0 — Verified bugs (must fix before merge)

### F1. `downloadPDF` opens a malformed URL — PDF button is broken on first click

**Evidence (verified)**:

- Route path: `routes.ts:72` — `/:language(${LANGUAGE_PATTERN})/back-office/reporting/print` — `language` is a **required path parameter**.
- New `ReportExport.vue:65-74`: `router.resolve({ name, query })` — no `params: { language }`.
- Sibling `ResultsPage.vue:349-356` (the proven existing pattern): correctly passes `params: { language: String(route.params.language ?? 'en'), ... }`.

**Consequence**: Vue Router 4 logs "Missing required param 'language'" and resolves to a malformed `href` (strips the param or falls through). `window.open` lands on a non-matching path → **404 / blank tab**. Every click of the PDF button fails.

**Fix**: Mirror `ResultsPage.vue:349-356`'s pattern — pass `params: { language: String(route.params.language ?? 'en') }` to both `router.resolve` calls in `downloadPDF()`.

---

### F2. `UnitDialogue.vue` — CSV button regression in unit-detail dialog

**Evidence (verified)**: `UnitDialogue.vue:348` uses `<ReportExport />` with NO props. The PR adds an optional `hasData?: boolean` prop to `ReportExport` and gates both PDF AND CSV buttons on `:disable="!props.hasData"`. With `hasData` undefined, `!undefined === true` → **both buttons permanently disabled** in the dialog.

**Consequence**: Pre-PR behavior: the CSV button worked in `UnitDialogue`. Post-PR behavior: CSV button is grayed out. Strict regression for a working feature.

**Fix options**: (a) update `UnitDialogue.vue:348` to pass `:has-data="someAppropriateBoolean"`, OR (b) `withDefaults({ hasData: true })` in `ReportExport.vue` so the new guard is opt-in, OR (c) gate only the PDF button on `hasData`, leaving the CSV button independent (it didn't have the guard pre-PR — symmetric scope change would have been documented).

Option (b) is the most conservative — adding a guard that defaults to "previous behavior" is the safer migration path.

---

### F3. New print routes lack the project's standard backoffice permission guard

**Evidence (verified)**:

- New routes at `routes.ts:77` and `routes.ts:94` have only `meta: { requiresAuth: true, isBackOffice: true, breadcrumb: false, ... }`.
- All other backoffice routes (e.g. `routes.ts:247`) wrap in `beforeEnter: requirePermission('backoffice.users', VIEW)`.

**Consequence**: Server-side `gate_backoffice` returns 403 so aggregated emission_breakdown / module_status_counts data does NOT leak. But the client-side defense-in-depth gate is missing — any authenticated workspace-only user who hits `/en/back-office/reporting/print?filters=...` mounts the `ReportingPrintPage` component, which calls `backofficeStore.getUnits()` in `onMounted`, fires a 403, and shows a blank `PrintLayout` instead of being redirected to `unauthorized`.

**Fix**: Add `beforeEnter: requirePermission('backoffice.users', VIEW)` to both new route entries. Matches the project's existing pattern at `routes.ts:247-364`.

## P1 — Real correctness issues (should fix before merge)

### F4. `JSON.parse` silent fallback on invalid `?filters=` payload — violates project rule

**Evidence**: `useBackofficePrintBase.ts:25` — `try { return JSON.parse(...) as UnitFilters; } catch {}` returns `{}` on parse failure. No log, no Notify, no visible state.

**Consequence**: A malformed `?filters=...` URL (truncated copy, autofill error) silently renders an **unfiltered global report**. User believes they are seeing their scope. Violates project memory `feedback_no_silent_fallbacks.md`.

**Fix**: Surface the parse failure — either redirect to `unauthorized` / `not-found`, or render an explicit "filter parse failed" message. Optionally use zod (already a dep) to validate the parsed shape against `UnitFilters`.

### F5. `JSON.parse` accepts non-object payloads → TypeError downstream

**Evidence**: `useBackofficePrintBase.ts:25` — `JSON.parse('null')` returns `null`, `JSON.parse('42')` returns `42`, `JSON.parse('[1]')` returns `[1]`. The bare `as UnitFilters` cast passes them through. Downstream `filters.value.years ?? []` throws on `null`.

**Consequence**: Crafted `?filters=null` URL crashes the print page with `TypeError: Cannot read properties of null`.

**Fix**: After parsing, validate: `if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return {} as UnitFilters;`. Or use zod.

### F6. `LocationQueryValue` is `string | null | (string|null)[]` — array case mishandled

**Evidence**: `useBackofficePrintBase.ts:23` — `String(route.query.filters ?? '{}')`. If `route.query.filters` is an array (e.g. `?filters=a&filters=b`), `String([a,b])` produces `"a,b"` which `JSON.parse` rejects → falls into the silent catch → empty filters.

**Consequence**: Duplicate query keys (accidental link sharing, autofill quirk) silently print the global dataset.

**Fix**: Narrow before stringifying: `const raw = Array.isArray(route.query.filters) ? route.query.filters[0] : route.query.filters; ...`. Same zod fix from F5 covers this.

### F7. Pinia store mutation with no cleanup — `pageSize = 5000` leaks

**Evidence**: `useBackofficePrintBase.ts:63` — `fetchData()` mutates `backofficeStore.unitsPagination.pageSize = 5000`. No `onScopeDispose` / restore.

**Consequence**: Today the print page is opened in a new tab via `window.open`, so this is contained per-tab. But if the route is ever opened via in-app navigation (history back, direct URL load), the main `ReportingPage` in the same tab now paginates at 5000 — performance regression.

**Fix**: Either pass `pageSize` to `getUnits()` as a local arg (cleanest), or capture-and-restore the original value with `onScopeDispose`.

### F8. Print button clickable while data is loading

**Evidence**: `ReportingPrintPage.vue` and `BackofficeResultsPrintPage.vue` — the print toolbar renders outside the `v-if="loading"` branch. The button has no `:disable="loading"`.

**Consequence**: User clicks Print before the spinner clears → `window.print()` captures spinner state → blank/partial PDF.

**Fix**: `:disable="loading || !hasData"` on the q-btn, or move the toolbar into the `v-else-if="hasData"` branch.

### F9. ECharts canvases may not be ready when print fires

**Evidence**: Multiple charts (`ModuleCarbonFootprintChart`, `CarbonFootPrintPerPersonChart`, `EmissionBreakdownChart` × 7 modules) mount in parallel. None of them signal a "render complete" event the print page waits on.

**Consequence**: Rapid Print-click after page load → mid-animation capture → blank or partial canvases in the PDF.

**Fix**: Either set `animation: false` for charts in print mode (some charts in the codebase already do this), OR gate the Print button on an "all charts finished" counter that the ECharts `finished` event increments.

### F10. Missing `years` filter guard

**Evidence**: `ReportingPage.fetchUnits()` has `if (selectedYears.length === 0) return;`. `useBackofficePrintBase.fetchData()` does not.

**Consequence**: `?filters={}` (or `?filters` missing `years`) reaches the backend which raises 400 `ERROR_AT_LEAST_ONE_YEAR`. The catch block sets `units.value = null`, `loading` flips back to false, but `hasData` stays false → **silent blank print page** with no error, no spinner, no retry.

**Fix**: Mirror the existing guard. Surface a visible "no data" message rather than blank-state degradation.

### F11. `+` in URL-encoded JSON decoded as space

**Evidence**: `ReportExport.vue:63` — `JSON.stringify(props.unitFilters ?? {})` is passed straight as the `filters` query string. Browsers/URLs decode `+` as space.

**Consequence**: If any filter value contains `+` (likely for affiliation codes like `R&D+` or search terms), the print page parses a corrupted JSON, falls into the silent catch (F4), and prints the global dataset.

**Fix**: `encodeURIComponent(JSON.stringify(...))`. Symmetric `decodeURIComponent` on read.

### F12. `_print-page.scss` extraction dropped `!important`

**Evidence**: The CSS rule for `@media print { .print-hide, .q-header, .q-footer, .q-drawer { display: none; } }` was moved from `ResultsPrintPage.vue` (scoped CSS, with `!important`) into the new global `_print-page.scss` (no `!important`).

**Consequence**: Quasar's runtime styles for `.q-header` use specific selectors that may beat the new rule. The existing `/results/print` flow may now show header/sidebar in printed PDFs — a regression in a previously-working flow.

**Fix**: Restore `!important` on the print-hide rule. Or verify the cascade still wins via the `@layer` declaration order in `app.scss`.

### F13. `tonnesPerFte` semantic divergence — print computes differently than live page

**Evidence**: `useBackofficeResultsPrintData.ts:44-49` synthesizes `tonnesPerFte = total_tonnes_co2eq / total_fte`. `ReportingPage.vue`'s per-FTE display derives from `per_person_breakdown` (rounding per-module before summing).

**Consequence**: The printed PDF's per-FTE number may not match the live page's per-FTE number. Undermines the PR's stated invariant that the print "mirrors the data ReportingPage uses".

**Fix**: Either consume `per_person_breakdown.sum` directly, or extract the per-FTE computation into a shared helper that both pages call.

## P2 — Architecture / quality

### F14. `?filters=<json>` is the first ad-hoc route-state-as-JSON convention

No existing `useRouteQuery` / `useUrlState` composable. This PR establishes a convention by accident. Next PR that needs filter persistence will re-invent encoding/validation/error-handling.

**Recommendation**: Extract `useRouteJsonParam<T>(key, default, schema)` (zod-validated) into `composables/`. Apply to F4/F5/F6 in one move.

### F15. Three composables for two print pages — over-split

`useBackofficePrintBase` (77 lines) + `useBackofficeReportingPrintData` (39 lines) + `useBackofficeResultsPrintData` (43 lines). The two leaves are thin re-exports + a few derived computeds. Could be one `useBackofficePrintData()` returning a richer object (Vue's `computed` only evaluates accessed refs).

### F16. `ReportingPrintPage.vue` and `BackofficeResultsPrintPage.vue` are ~80% identical

Same toolbar, spinner, container shell, `<ReportPage v-for="availableModules">`. Differ only on Page 1 mid-section (stat-cards vs big-numbers). Could be a single `BackofficeReportPrintPage.vue` parameterized by `reportType`.

### F17. Dead `:print-mode="true"` props on chart components

`ReportingPrintPage.vue` and `BackofficeResultsPrintPage.vue` pass `:print-mode="true"` to `ModuleCarbonFootprintChart` and `CarbonFootPrintPerPersonChart`. **Neither component declares a `printMode` prop** — they use `usePrintMode()` inject from `PrintLayout`. The bindings are silently inert.

**Recommendation**: Drop the prop bindings. Document that print mode is provided via inject. Or genuinely add the prop and remove the inject-only pattern.

### F18. `printMode` prop on `CompletionRateBar` — should be CSS

26 lines (prop + withDefaults + redundant `const printMode = computed(() => props.printMode)`) to hide a tooltip icon in print. Pure CSS `@media print { .completion-bar-info-icon { display: none; } }` does the same in 3 lines, no prop.

### F19. `EmissionBreakdownChart` print-mode template branch is duplicate

The new `<template v-if="isPrintMode">` branch (~30 lines) renders TreeMap + EmissionTypeBreakdown in two q-cards — same charts the `v-else` branch already renders. Hardcoded English strings (`'Treemap — '`, `'Emission breakdown — '`) bypass i18n.

**Fix**: Single template, `<div class="print-chart-box" v-if="isPrintMode">` wrapper, proper i18n keys for the box labels.

### F20. `forcedModule` vs `selectedTab` — parallel mechanisms

The new `forcedModule` prop short-circuits the existing `selectedTab` ref/`activeTab` computed. Could be a `v-model:activeModule` instead — single mechanism, no new prop.

### F21. `availableModules` duplicated between `useBackofficePrintBase` and `EmissionBreakdownChart`

Same data, same filter logic — with the new copy already adding a `category_key` fallback the original lacks. Two implementations, drift on day one.

**Fix**: Extract to a shared util (`composables/useEmissionTreemap.ts` or `constants/charts.ts`), consume in both.

### F22. `downloadPDF` is the second inline copy of the open-print-route pattern

`ResultsPage.vue:348-362` already has the same shape. PR adds a parallel copy in `ReportExport.vue`. Extract to `composables/print/useDownloadAsPDF.ts`.

## Karpathy checklist

| Question                                              | Answer                                                                                                                                                                                 |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code satisfies the original requirements?             | **No.** Feature opens a 404 URL on first click (F1).                                                                                                                                   |
| Edge cases / error handling / invalid inputs covered? | **No.** JSON.parse silent + non-object + array (F4, F5, F6).                                                                                                                           |
| APIs / imports / framework calls real and valid?      | Mostly yes; dead `:print-mode` props are no-ops (F17).                                                                                                                                 |
| Auth / authorization / validation / security correct? | **Defense-in-depth gap.** Backend protects data; client guards missing (F3).                                                                                                           |
| Code simpler than necessary, or overengineered?       | **Overengineered.** Three composables for two pages (F15); two sibling pages 80% identical (F16).                                                                                      |
| Duplicated or dead code introduced?                   | **Yes.** F17, F19, F21, F22 all duplications; bundled scope creep flagged by author description (auth-flow + ADR-019) does NOT actually appear in the diff — good catch by the author. |
| Naming / typing / comments accurate?                  | Mostly. `hasData` prop semantics inconsistent across callers.                                                                                                                          |
| Performance / concurrency / scalability?              | **Yes.** No render-ready gate (F9), pageSize leak (F7), unnecessary 5000-row fetch when only aggregates are read.                                                                      |
| Tests for happy path / edge cases / failure?          | **No tests added.** Author's checkbox unchecked.                                                                                                                                       |
| Would I approve this if a junior wrote it?            | **No.** Request F1, F2, F3 minimum. F4-F11 should also land before merge.                                                                                                              |

## Recommended action

**Block merge.** Three verified P0 bugs and the feature doesn't work on first click.

Required before merge:

1. **F1** — fix `downloadPDF` to pass `params.language`.
2. **F2** — restore `UnitDialogue` CSV button (default `hasData` to `true` is the safest fix).
3. **F3** — add `beforeEnter: requirePermission('backoffice.users', VIEW)` to both new print routes.
4. **F4 + F5 + F6 + F11** — handle `?filters=...` parsing edge cases (one zod schema + `encodeURIComponent` covers all four).
5. **F8** — disable Print button while loading.
6. **F10** — guard against missing `years`.

Strongly recommended:

- **F7** — restore `pageSize` on unmount.
- **F9** — gate print on chart-ready.
- **F12** — restore `!important` on print-hide rule (regression risk for existing flow).
- **F13** — align `tonnesPerFte` with the live page's computation.

F14-F22 are architectural; can be addressed in this PR or split into follow-ups based on PR-size preference.

Author's CSV button bundling is fine and self-flagged. Author should be told the auth-flow / ADR-019 description bullets don't match the actual diff — likely stale PR description.
