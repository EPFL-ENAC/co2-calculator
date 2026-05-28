# PR #1309 — Code Review (max effort)

**PR**: `feat 973: download as png in all charts` by @BenBotros
**Branch**: `feat/973-feat-results-charts-download-as-png` (rebased + force-pushed)
**Scope**: 11 files, +275/-48 — closes #973
**Effort calibration**: 7 finder angles (skipped removed-behavior + efficiency as low-risk for a feature-add)

## Verdict: REQUEST CHANGES — no hard blockers, but multiple usability bugs

The feature works on the happy path. The shared utility `utils/chartDownload.ts` does correctly extract the previously-duplicated download logic. However, the PR ships several latent bugs that will surface in real use: animation-mid-capture, silent no-ops with no user feedback, a missing chart, identical filenames for distinct charts, and a Safari/iOS download cancellation pattern.

None of these are P0 in the sense of "breaks existing functionality" — they're failure modes of the NEW feature when triggered by realistic inputs.

## P0 — Real defects that affect the happy path

### F1. 200ms animation-settle race — captures may be mid-animation

**Evidence**: `chartDownload.ts:28` uses `setTimeout(200)` before `getDataURL`. ECharts default `animationDuration` is ~1000ms and `animationDurationUpdate` is ~300ms. 200ms is shorter than the default.

**Consequence**: User opens a results page, chart animates in over ~1s, immediately clicks Download PNG. After 200ms wait, `getDataURL` captures bars/lines partway through their entrance animation → exported PNG shows half-drawn chart.

**Fix**: Use `chart.on('finished', ...)` event, OR set `animation: false` on the chart when capturing, OR poll `chart.isAnimating()`. Magic-number sleeps for animation state are inherently flaky.

---

### F2. Silent no-op when chart ref is null, data is empty, or context is missing

**Evidence**: Multiple paths in `chartDownload.ts` and consumer components:

- `chartDownload.ts:22`: `if (!chart) return;` — returns silently
- `chartDownload.ts:80`: `if (!ctx) return;` — same
- `chartDownload.ts:62`: `c.charts.some(Boolean)` filter — keeps columns where any chart is _truthy_ (mounted) but not necessarily _rendered_
- `ItFocusSection.vue:480`: Download button visibility gated only by `!loading && data && !printMode`, NOT by `hasData` — when `data` is truthy but the chart didn't mount because rows are empty, the button still renders and clicking does nothing.
- `ReductionObjectiveChart.vue:149`: Download button unconditional; doesn't consult active child's data-ready state.

**Consequence**: User clicks the download button in various legitimate states (chart not yet rendered, empty-state, hidden tab) → nothing happens → user assumes the button is broken. No console error, no notification, no retry hint.

**Fix**:

- Gate every download button on `hasData` (or chart-ready state) — disabling rather than silently rendering.
- In the utility, when an early-return triggers, surface via `Notify.create({ color: 'warning', message: t('chart_download_unavailable') })` rather than `return`.

---

### F3. `EmissionBreakdownChart` (the backoffice wrapper) has NO download button despite "all charts" claim

**Evidence**: `frontend/src/pages/back-office/ReportingPage.vue:292` mounts `EmissionBreakdownChart`. Its children `GenericEmissionTreeMapChart` and `EmissionTypeBreakdownChart` both expose `downloadPNG`. But `EmissionBreakdownChart` itself never instantiates refs to them and never renders a button. Not documented as excluded (PR description only mentions headcount).

**Consequence**: Backoffice user on `/back-office/reporting` sees emission-breakdown alongside two other charts with download buttons; this one silently has no button. "Download as PNG in all charts" promise breaks on the most-trafficked backoffice page.

**Fix**: Add the same ref + delegation + button pattern that `ModuleCharts.vue` uses, in `EmissionBreakdownChart.vue`.

---

### F4. No re-entrancy guard on download buttons → duplicate downloads on double-click

**Evidence**: All 4 buttons (`ModuleCharts.vue:123`, `ReductionObjectiveChart.vue:149`, `AdditionalCategoriesSection.vue:858`, `ItFocusSection.vue:480`) call the async `downloadPNG()` with no `disabled` state during the in-flight period and no debounce.

**Consequence**: User double-clicks → two independent canvases built sequentially (~200ms+ each) → two near-identical PNGs hit the download tray, sometimes with conflicting filenames (timestamp collision possible on fast networks).

**Fix**: Track `downloading.value` ref per button, disable while in-flight. Or debounce 500ms in the utility.

## P1 — Real quality issues

### F5. Filename collision — `emission-breakdown` for two different views

**Evidence**: `GenericEmissionTreeMapChart.vue:244` and `EmissionTypeBreakdownChart.vue:491` both use the filename base `'emission-breakdown'`. `ModuleCharts` proxies between them based on `moduleChartView` (`'breakdown'` vs `'type'`), but the produced file does not encode which view was active.

**Consequence**: User downloads treemap view, toggles to type-breakdown, downloads again. Both files named `emission-breakdown-<timestamp>.png`. In a folder of exports, cannot distinguish; OS may de-duplicate as `emission-breakdown (1).png`.

**Fix**: Pass a more specific name (`emission-breakdown-treemap` vs `emission-breakdown-type`) at each call site.

### F6. No sanitization of `filenameBase` — special chars survive unfiltered

**Evidence**: `chartDownload.ts:18` — `filenameBase` is concatenated as-is. No filtering of `/`, `\`, `:`, `?`, `*`, `<`, `>`, `|`.

**Consequence**: Today's 8 callers use literal strings, so latent. But the utility is exported and reusable; any future caller passing a user-controlled string (project name, scenario label) produces a broken or surprising filename. Chrome silently strips, Windows rejects, macOS may behave unexpectedly.

**Fix**: Sanitize via a `slugify`/`kebabCase` step inside the utility.

### F7. Composite stitching at fixed 400×300 ignores source aspect ratio

**Evidence**: `chartDownload.ts:98` — `drawImage` forces every source chart into a fixed destination rectangle.

**Consequence**: A chart whose source canvas is 800×300 (wide bar) gets squeezed into 400×300 → bars compressed, labels overlap in the exported PNG.

**Fix**: Compute destination dimensions from source aspect ratio. Or use `getConnectedDataURL` (ECharts native composite API) instead of hand-rolling.

### F8. Composite canvas downsamples 2× rasters to DPR=1

**Evidence**: Per-chart `pixelRatio: 2` in `getDataURL`, but composite canvas at logical pixels with no DPR scaling. `drawImage` then downsamples the high-DPR sources into low-DPR slots.

**Consequence**: Single-chart download produces crisp 2× DPR PNG; composite download of the same charts is soft/aliased — confusingly inconsistent.

**Fix**: Scale the composite canvas by `devicePixelRatio` and `ctx.scale(dpr, dpr)` at the start.

### F9. Silent `console.error` failure — no user notification

**Evidence**: `chartDownload.ts` catches errors and only logs to console. Project pattern (verified in `ReportExport.vue`, `useAuditLogs.ts`, `useRecalculation.ts`, etc.) is `Notify.create({ color: 'negative', ... })` for download flows.

**Consequence**: User clicks download, something fails (tainted canvas, WebGL context loss, blob too large), gets ZERO feedback. Inconsistent with every other download flow in the app.

**Fix**: Add `Notify.create` calls on success AND failure. Match the convention of existing download flows.

### F10. iOS Safari download cancellation pattern

**Evidence**: `chartDownload.ts:13` — `triggerPngDownload` calls `document.body.removeChild(link)` synchronously after `link.click()`. In older Safari/iOS, the click navigation is async and removing the link before navigation completes can cancel the download.

**Consequence**: On iOS Safari, the user taps the PNG download button → `removeChild` runs before the browser dispatches navigation from `click()` → no save dialog → silent failure on mobile.

**Fix**: Schedule `removeChild` via `setTimeout(0)` or `requestAnimationFrame` to defer it past the click event.

### F11. `getDataURL` on hidden chart returns blank PNG with no warning

**Evidence**: ECharts inside `v-if=false` / `v-show=false` / hidden Quasar tab has zero rendered dimensions. `getDataURL` returns blank, no error thrown.

**Consequence**: `AdditionalCategoriesSection`'s composite — if a chart in a column was never scrolled into view (IntersectionObserver hasn't fired for it specifically), its canvas is 0×0 → blank rect in the composite.

**Fix**: Check `chart.getWidth() > 0 && chart.getHeight() > 0` before `getDataURL`. If not, either skip the chart with a notice, or render a placeholder, or refuse the composite download.

### F12. Composite `toDataURL` may silently exceed browser 2MB data URL cap

**Evidence**: `chartDownload.ts:119` uses `canvas.toDataURL('image/png')` (sync) → materializes a large base64 string in memory → sets as `<a href>`. Chromium/WebKit silently fail downloads when the data URL exceeds ~2MB.

**Consequence**: A 4-column composite at 1600×640 with dense chart content can exceed 2MB. Chrome clicks the `<a>` but no download dialog appears (silent failure, no catch trigger).

**Fix**: Use `canvas.toBlob()` + `URL.createObjectURL` + `URL.revokeObjectURL` for the composite path. Slightly more code but no size cap.

### F13. ItFocusSection: download button rendered before `hasData` check

**Evidence**: `ItFocusSection.vue:480` — button visibility uses `!loading && data && !printMode`, ignoring `hasData`. The chart only mounts when `hasData` is true.

**Consequence**: Empty IT focus response (data truthy, hasData false) renders button without chart. Click → silent no-op (covered by F2 but specifically gated wrong).

**Fix**: Gate on `hasData`, not on truthiness of `data`.

## P2 — Architecture / consistency

### F14. `defineExpose({ downloadPNG })` ref-chasing — should be a composable

**Evidence**: 4 components expose `downloadPNG`, 3 parents reach via refs typed as structural `ref<{ downloadPNG: () => Promise<void> } | null>`. This bypasses Vue's `InstanceType<typeof Child>` typing — type changes on child won't surface as compile errors at parent.

**Right altitude**: `const { register, downloadActive } = useChartDownload()`. Each chart calls `register(chartRef, filename)` in setup; parents call `downloadActive(viewKey)`. No `defineExpose`, no ref-chasing, no per-parent proxy code.

### F15. Two near-identical download patterns — could unify

**Evidence**: `downloadEchartAsPng` and `downloadCompositeChartAsPng` share the 200ms wait + filename + try/catch shape. The composite is the general case (length-1 array is the common case).

**Right altitude**: One `downloadCharts(columns: CompositeColumn[], base: string)`. Single-chart sugar: `downloadEchart(chart, base) = downloadCharts([{title: '', charts: [chart]}], base)`. Bug-fixes land in one place.

### F16. Download button template duplicated 6 times — should be molecule

**Evidence**: Identical `<q-btn icon=download outline dense size=xs q-px-sm ...>` block across `ReductionObjectiveChart`, `AdditionalCategoriesSection`, `ItFocusSection`, `ModuleCharts`, and the two inline download impls.

**Right altitude**: `<ChartDownloadButton :handle="download" />` molecule. Visual tweaks land once.

### F17. `triggerPngDownload` is the 4th copy of the anchor-click pattern

**Evidence**: Existing `downloadBlob` helper at `ReportExport.vue:59`. Plus inline anchor-click in `useAuditLogs.ts`, `useModuleConfig.ts`, `useSubmoduleConfig.ts`, `useUploadCard.ts`, `ModuleCarbonFootprintChart.vue` (CSV adjacent to PNG), `CarbonFootPrintPerPersonChart.vue` (CSV), `ModuleTable.vue`, `ReductionObjectivesSection.vue`, `PipelineOperationsConsolePage.vue`, `UploadCardReferences.vue`.

**Right altitude**: Promote `downloadBlob` (or new `downloadUrl`) to `src/utils/download.ts`. Use for both PNG and CSV. Every browser quirk fix (Safari, revoke timing) lives once.

### F18. ECharts `toolbox.feature.saveAsImage` is already bundled

**Evidence**: `ToolboxComponent` is imported and registered in `ReductionObjectiveUnitView` and `ReductionObjectiveEpflView`. ECharts native `saveAsImage` could replace the custom path for single charts. Pro/con tradeoff (toolbox UI vs `<q-btn>` styling consistency).

**Recommendation**: Document the tradeoff in the PR — explicit "we chose custom because of styling/UX consistency" vs implicit duplication.

### F19. Hardcoded `'Arial, sans-serif'` font + `fillText` with no overflow handling

**Evidence**: `chartDownload.ts:79` — composite title rendered via raw `fillText` at fixed 14px Arial centered at `x + colWidth/2`.

**Consequence**: Long column titles (e.g. French scenario names) overflow the column with no clipping or ellipsis. Non-Latin scripts may render incorrectly without a font fallback.

**Fix**: Either use a font that matches the app's design system (read from CSS custom property), measure text and ellipsize if too wide, OR use `getConnectedDataURL` and let ECharts handle the layout.

### F20. Headcount exclusion is a hardcoded string check

**Evidence**: `ModuleCharts.vue` gates the button on `type !== 'headcount'`. Special case bolted on shared code.

**Right altitude**: Each chart declares whether it's downloadable via the composable's registration (`useChartDownload({ downloadable: false })`). Button renders only when a downloadable chart is registered.

### F21. Inconsistent filename timestamp format with adjacent CSV exporters

**Evidence**: `chartDownload.ts:18` uses `new Date().toISOString().replace(/[:.]/g, '-')`. The unrefactored CSV exporters adjacent to the refactored PNG impls (`ModuleCarbonFootprintChart.vue:1384`, `CarbonFootPrintPerPersonChart.vue:469`) use the same expression. ISO timestamp is also UTC, which surprises non-UTC users.

**Fix**: Extract a shared `formatTimestampForFilename()` util. Consider including UTC offset or local-time conversion to reduce confusion.

## Karpathy checklist

| Question                                  | Answer                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Satisfies original requirements?          | **Partial.** "Download as PNG in all charts" — `EmissionBreakdownChart` missing (F3).                      |
| Edge cases / error handling?              | **No.** Silent no-ops (F2, F4), animation race (F1), iOS quirks (F10), hidden charts (F11), 2MB cap (F12). |
| APIs / framework calls real?              | Yes.                                                                                                       |
| Auth / security?                          | N/A.                                                                                                       |
| Simpler than necessary or overengineered? | Two patterns where one would do (F15); 6 button copies (F16); `defineExpose` antipattern (F14).            |
| Duplicated or dead code?                  | Yes — `triggerPngDownload` is the 4th anchor-click copy (F17).                                             |
| Naming / typing accurate?                 | Filename collision (F5); structural ref type bypasses Vue check (F14).                                     |
| Performance / scalability?                | Composite issues (F7, F8, F12).                                                                            |
| Tests added?                              | **No.**                                                                                                    |
| Approve from a junior?                    | **No.** F1, F2, F3, F4 before merge. F5-F13 strongly recommended. F14-F21 follow-up.                       |

## Recommended action

**Request changes.** Required before merge:

1. **F1** — replace `setTimeout(200)` with `chart.on('finished')` or `animation: false` during capture.
2. **F2** — every download path must either succeed or notify; no silent returns.
3. **F3** — add the download button to `EmissionBreakdownChart` (backoffice wrapper) or document the omission.
4. **F4** — disable buttons during in-flight downloads.

Strongly recommended:

- **F5** — fix filename collision (treemap vs type-breakdown).
- **F6** — sanitize `filenameBase`.
- **F7 + F8 + F11 + F12** — composite path is the riskiest; address aspect ratio, DPR, hidden charts, blob alternative.
- **F9** — Notify on failure to match project convention.
- **F10** — defer `removeChild` for Safari/iOS.

Architecture (this PR or follow-up):

- **F14** — composable-based registration replaces `defineExpose`.
- **F15** — unify the two download functions.
- **F16** — extract `<ChartDownloadButton>` molecule.
- **F17** — promote `downloadBlob` to a shared util used by both CSV and PNG.

**This is a NET-positive PR** — it does extract real duplication (the CSV exporters next door should follow the same shape). The verdict is "request changes for usability bugs", not "block for design problems."
