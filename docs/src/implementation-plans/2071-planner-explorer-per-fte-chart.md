---
status: delivered
issue: 2071
last_updated: 2026-09-16
title: "Planner and Explorer results: carbon footprint per FTE chart"
summary: "The Results page shows the unit's stacked per-FTE bar beside the main category chart. The Explorer and Planner results cards now show the same pair in the same 2:1 layout, fed by the per-FTE values the backend already derives for simulator reports."
---

# Planner and Explorer results: carbon footprint per FTE chart (#2071)

## Ask

The Results page pairs the "Unit carbon footprint" category chart with a
narrower "My unit carbon footprint per FTE" stacked bar on its right third.
The Explorer and the Project Planner results cards only had the category
chart. Add the per-FTE chart to both, in the same layout.

## What the backend already provides

Nothing changed server-side. `derive_report_sections`
(`backend/app/utils/report_stats.py`) writes `per_fte` for every bucket
into each report's persisted stats, and `merge_report_stats` re-derives it
for the planner's summed years (summed kg over summed FTE). Simulator
reports have no validation step, so `_build_report_stats` counts every
active module as validated there and `toEmissionBreakdown`
(`frontend/src/utils/emissionStatsAdapter.ts`) keeps every active
bucket in `per_person_breakdown`. FTE comes from each report's own
Headcount module, which both the Explorer and the Planner carry.

## Change (frontend only)

- **Shared layout.** The Results page's scoped `.results-charts-grid`
  rules move to `frontend/src/css/03-layout/_grid.scss` as `.charts-grid`
  (`__main` 2 : `__side` 1 from 1024px, stacked below). The Results page
  now uses the shared classes; the Explorer and Planner results cards wrap
  their main chart and the new `CarbonFootPrintPerPersonChart` in it.
- **Shared toggle.** The per-FTE chart must show the same categories as
  the main chart, so the results title row of both pages carries the
  Calculator's "Additional data" `q-toggle` (`results_additional_data`),
  right-aligned and vertically centred, and passes it to every chart as
  `viewAdditionalData`.
  A chart given that prop hides its own checkbox
  (`ModuleCarbonFootprintChart` already did; `PlannerGrantComparisonChart`
  gained the prop). The Results page keeps its page-level filter.
- **Total follows the toggle.** `sumBreakdownTonnes` takes an
  `includeAdditional` flag: module categories only by default (what the
  chart draws), plus the additional rows when the toggle is on. Its old
  fallback to the backend's all-buckets total is gone: it showed a non-zero
  headline above an empty chart for a headcount-only sandbox. The print
  composables keep the default.
- **Planner bars.** `CarbonFootPrintPerPersonChart` takes an optional
  `rows` prop (label + per-FTE values + `hatched`) in place of the single
  "My unit" bar, and now builds its bars from explicit per-bar data
  instead of an ECharts dataset so a bar can carry its own decal. The
  disabled EPFL-reference and objective rows went with the dataset.
  `plannerPerFteRows` (`utils/plannerPerFte.ts`) gives the Planner one bar
  per results view that has headcount, labelled and hatched exactly like
  the comparison chart's series (`YEARS_DECAL`, now in `constant/charts`):
  "Grant proposal (range)" plain and "Detailed per year (range)" hatched
  for a grant plan with year sections, one plain bar otherwise. All bars
  share the one "Total" tick as side-by-side stacks; with several bars a
  legend names them and the tooltip shows one section per bar (its label
  and total, then its categories), like the comparison chart's tooltip
  (`TooltipRow.heading`).
- **Comparison chart card.** `PlannerGrantComparisonChart` now renders the
  same card, header and download footer as `ModuleCarbonFootprintChart`,
  so the planner's results chart reads like the explorer's; the print page
  dropped its extra wrapper card.
- **PDFs.** Both print reports draw the per-FTE chart under the results
  chart (horizontal bars, print mode), only when there is headcount. The
  download link carries the page's toggle as `?additional=1|0`; the print
  composables read it and both the charts and the totals follow it.
- **Missing headcount.** Simulator reports are never "validated", so the
  chart gets `show-validation-placeholder` with `placeholder-variant="add"`:
  when no FTE was entered (`total_fte` is 0, or no Planner view has one)
  the placeholder card replaces the whole side panel, title included and
  edge to edge like the Results page's own card, reading "Add Headcount to
  see results / Please fill in this module…" (`results_add_module_title` /
  `_message`) instead of the "Validate…" wording. The chart card is
  `flex: 1` so it fills the side column.

## Verified locally

Test unit 1 (`ENAC-IT4R-TEST`), principal test login. Explorer without
headcount: placeholder fills the right third. Plan `per-fte-check`
(2027): placeholder before any FTE, one "Detailed per year (2027)" bar
after adding staff and student rows, additional categories appearing when
the main chart's checkbox is ticked.

While verifying: a staff row (SIUS 51) added FTE but no commuting /
food / waste, a student row added both, in the Calculator as well.
`seed_generic_factors.py` reads `INPUT_DATA/headcount_member_factors.csv`
but the local `INPUT_DATA` folder held `headcount_members_factors.csv`
(plural), so `seed_all_factors` printed its "Skipping factor seed" line
and the member factors were never loaded. Seeding that file for the
member type (2025 and 2026) fixed it: a staff-only row now prices in
both simulators. Rows saved before the seed keep their zero until
re-saved. A local seed-data gap, not a frontend issue; the silent skip in
the seeder is worth its own issue.

- **Titles.** The Explorer reuses the Results title ("My unit carbon
  footprint per FTE"). The Planner gets
  `planner_results_per_fte_chart_title` ("{name} carbon footprint per
  FTE"), matching its neighbouring "{name} carbon footprint, year by year".

## Out of scope

Nothing: the print totals now follow the same toggle as their charts.

## Test

`frontend/tests/unit/charts-additional-data.spec.ts` mounts both main
charts with `viewAdditionalData` and checks they render no checkbox of
their own, and mounts the per-FTE chart without headcount to pin the
"add" placeholder wording. `breakdown-total.spec.ts` pins the helper:
module-only by default, additional rows on request, zero for a
headcount-only report with the toggle off.
