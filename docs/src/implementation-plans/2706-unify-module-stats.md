---
status: delivered
issue: 2706
last_updated: 2026-09-11
summary: "Module stats had two implementations: a JSON persisted by the
  pipeline and a live aggregate recomputed on every module-detail GET. The
  GET now reads the persisted column; the per-viewer planner-snapshot filter
  and the headcount FTE chart maps are persisted alongside so nothing is
  re-aggregated at read time."
---

# 2706 — One path for a module's stats

## Problem

`GET /carbon-reports/{id}/modules/{module}` ran two aggregates per request:
`DataEntryEmissionRepository.get_stats` (flat `{emission_type_id: kg}`) and,
for headcount, `get_headcount_fte_breakdown`. The pipeline meanwhile
persisted a richer, bucketed stats JSON on `carbon_report_modules.stats`
through `compute_module_stats`. Two formulas for one published number, two
shapes, and a per-GET aggregate on the hottest page.

What the frontend actually rendered from the live path: only
`totals.total_kg_co2eq` / `total_tonnes_co2eq` (module sidebar) and, for
headcount, the FTE-by-SIUS map feeding the bar chart. The flat emissions map
was dead payload for every other module.

## Decision (maintainer, 2026-09-11)

Option A of the issue: the GET reads the persisted column. KISS — one path,
one location. The persisted JSON gains what the read path needed:

| key                                      | module    | what                                                                                                                                              |
| ---------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `total_excluding_additional`             | all       | headline: every bucket except the additional ones (commuting, food, waste, embodied energy) — what the sidebar shows                              |
| `planner_snapshot_kg`                    | all       | share of that headline carried by Simulator prefill rows (`source = PLANNER_SNAPSHOT`); subtracted for viewers who may not see those rows (#1983) |
| `student_fte`, `member_fte_by_sius_code` | headcount | the bar-chart maps, from the existing `get_headcount_fte_breakdown` query, now run at recompute time                                              |

`get_stats_pair_many` (the batched query behind `recompute_stats_many`)
gains one `SUM(CASE WHEN source = 6 …)` column. It keeps its
`data_entries` join because `source` lives there — the #2527 Phase 2 join
drop for this query is therefore off the table unless `source` is
denormalized onto emissions too.

## Shipped

- `carbon_report_module.py` — `_module_totals` reads the keys above;
  `stats` in `ModuleResponse` is the persisted JSON verbatim. A row written
  before this change lacks the keys and answers **503** pointing at the
  admin recompute-stats trigger. No silent zero.
- Deleted: `DataEntryEmissionRepository.get_stats`, `get_stats_pair`,
  `DataEntryEmissionService.get_stats`,
  `DataEntryService.get_headcount_fte_breakdown` (the repo query stays, the
  module service calls it).
- Frontend: `ModuleResponse.stats` is `Record<string, unknown> | null`;
  `headcountChartStats` builds the chart map from the persisted keys.
- Tests: repo (`get_stats_pair_many` snapshot split, rollup no-double-count,
  banner total), pure `compute_module_stats` keys, route (headline, hidden
  viewer, no stats, 503), Playwright unit spec for the chart adapter, and the
  `_pg` shape contract updated.

## Deploy step

Every environment must run `POST /sync/admin/recompute-stats` right after
this deploys (backoffice pipeline operations). Until then non-headcount
module pages answer 503 by design.

## Found on the way, not fixed here

- **Stage drift**: 4039 of 18096 modules on stage differ between the
  persisted `by_emission_type` and a live sum — the first query also counted
  computed parent rollups, so the leaf-only figure is still to be read.
- **Emptied modules keep stale stats**: `bulk_delete_by_source_year` (CSV /
  Tableau re-import) deletes a module's rows, then the recalc finds no
  entries, reports no affected modules, and the aggregation job never
  rewrites that module's JSON. The simulator already compensates
  (`cleared + emptied` at `simulator_plan_service.py:634`); the bulk path
  does not. With the GET now reading the column, this staleness reaches the
  sidebar too. Separate decision — pipeline scoping.
- `breakdownTotal.ts` still re-sums non-additional buckets client-side for
  the results page; `total_excluding_additional` can retire it.
