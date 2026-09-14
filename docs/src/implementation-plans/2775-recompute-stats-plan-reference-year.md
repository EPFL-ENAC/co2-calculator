---
status: delivered
issue: 2775
last_updated: 2026-09-14
summary: "Scope the recompute-stats and stale-stats queries on the effective factor year (COALESCE(reference_year, year)) instead of carbon_reports.year, so Simulator Plan reports fold into their baseline year's aggregation scope instead of raising a scope for their planning year — which has no factors, is never selectable in the operator UI, and left every plan's stats permanently un-recomputed. The aggregation handler's module slice is widened for the admin trigger only, so the recalc-chained path cannot bump validated plans to IN_PROGRESS."
---

# recompute-stats never reached Simulator Plan reports (#2775)

## Context

`POST /v1/sync/admin/recompute-stats` is the admin backfill trigger: it fans
out one root `aggregation` job per `(module_type_id, year)` scope so every
`carbon_report_module.stats` row gets re-derived under current code after a
stats-shape change. Running it for 2025 on dev dispatched 8 jobs (one per
module type, jobs 242-249) and none of them touched a Simulator Plan module.

A Plan report's `carbon_reports.year` is its **planning target**; its entries
price against `reference_year`. That is exactly what `resolve_factor_year`
reads first (`app/utils/factor_year.py`), and the plan year is deliberately a
year no factor set exists for — on dev all 84 `Simulator_Plan` reports carry
`reference_year = 2025` with `year` spanning 2020-2043.

Every scoping query in the recompute path keyed on `carbon_reports.year`, so a
plan was stranded three times over:

1. `list_module_type_year_scopes` filtered `CarbonReport.year == year` and
   emitted `CarbonReport.year` as the scope key, so picking 2025 in the
   operator UI never produced a scope containing a 2043 plan report.
2. `filter_scopes_with_current_factors` then asked "does 2043 have a current
   FACTORS job?" → no → counted in `skipped_no_factors`.
3. `list_by_module_type_and_year` — the aggregation handler's own module
   selection — filtered the same way, so even a dispatched job would not have
   collected the plan's modules.

Only the seven plan reports that coincidentally sit at `year = 2025` were ever
recomputed, which is why the symptom read as "it only recomputes Calculator".

The same seed query backs `find_stale_aggregations`, so the stale-stats
endpoint had the mirror-image bug: a plan at 2043 raised a scope no
aggregation can ever target, reported as `no_aggregation_ever` forever.

## What shipped

A single SQL expression, `effective_factor_year_col()` in
`app/utils/factor_year.py`, next to the Python `resolve_factor_year` it is the
twin of — so the two answers to "which year does this report price against"
cannot drift:

```python
func.coalesce(col(CarbonReport.reference_year), col(CarbonReport.year))
```

Applied at the three scoping sites:

| Site                                                     | Was                                   | Now                                                                            |
| -------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------ |
| `data_ingestion.list_module_type_year_scopes`            | `CarbonReport.year` (select + filter) | `effective_factor_year_col()`                                                  |
| `data_ingestion.find_stale_aggregations` (seed subquery) | `CarbonReport.year`                   | `effective_factor_year_col()`                                                  |
| `carbon_report_module_repo.list_by_module_type_and_year` | `CarbonReport.year == year`           | `effective_factor_year_col() == year`, **opt-in** via `include_reference_year` |

`CarbonReport.reference_year` is written in exactly one place —
`SimulatorPlanService.set_reference_year`, a Simulator Plan route — so the
COALESCE is a no-op for Calculator and Explore reports.

### The module slice is widened for the admin trigger only

`list_by_module_type_and_year` backs **both** aggregation paths: the admin
trigger and the recalc-chained aggregation that runs after every ingest or
factor upload. Widening it unconditionally would have changed the hot path:

```python
emptied = await svc.emptied_module_ids(candidates)
affected = [m for m in candidates if m.id in affected_scope or m.id in emptied]
```

`emptied_module_ids` runs over the full candidate list and is _not_ filtered by
`affected_scope`, and the recalc path recomputes with `bump_status=True`. So a
routine 2025 factor upload could have flipped validated plan modules back to
IN_PROGRESS — a change to validated data on the pipeline's hot path, which is
not what this issue is for.

The widening is therefore opt-in: `create_root_aggregation_job` sets
`meta.config.include_reference_year_reports`, and `aggregation_handler` passes
it through to the slice query. Recalc-chained aggregations don't set it and
keep exactly their current candidate set.

**Open question for review:** a 2025 factor change _does_ invalidate plans
baselined on 2025, so arguably the recalc path should reach them too. That is a
deliberate follow-up, not an oversight — it touches validated emission data and
needs its own plan.

### Why this shape

Plans fold into the **existing** `(module_type_id, 2025)` scope rather than
raising one of their own. That means no new scopes, no new jobs, and no extra
pooled DB connections — the 8 jobs an operator dispatches today stay 8 jobs.
It also dissolves the factor filter's objection without touching it: the scope
year is now 2025, which has factors.

The operator UI needs no change either. Its year dropdown is restricted to
years with a year-configuration row (`RecomputeStatsCard.vue`), so a plan year
like 2043 could never have been selected; picking the baseline year now sweeps
in every plan baselined on it.

## Deliberately out of scope

- **Simulator Explore.** It has no `reference_year` by design (#2656) and
  resolves via `_resolve_latest_started_year`, which needs per-project state
  and has no SQL twin. Explore modules are still not reached by the trigger;
  tracked separately.
- **Re-pricing.** `recompute_stats_many` re-aggregates existing
  `data_entry_emissions` rows into the stats JSON; it does not recompute
  emissions. This change makes the stats backfill _reach_ plans, which is what
  the endpoint is for. Whether a factor change re-prices plan entries is
  `emission_recalc`'s concern and was not investigated.

## Tests

`backend/tests/integration/services/data_ingestion/test_recompute_stats_endpoint_pg.py`:

- `test_recompute_stats_scopes_plan_by_reference_year` — a plan at
  `year=2043 / reference_year=2025` alongside a Calculator 2025 report with
  factors dispatches **one** job, at year 2025, with `skipped_no_factors == 0`.
  Before the fix the plan raised a second, factorless 2043 scope.
- `test_reference_year_slice_collects_plan_modules` — the handler's own module
  query returns the plan's module for the widened 2025 slice, and _not_ for the
  narrow (recalc-chained) 2025 slice nor the 2043 planning slice. This proves a
  dispatched job reaches the modules and that the recalc path is unchanged.

`backend/tests/unit/tasks/test_aggregation_handler.py` pins the default: a plain
aggregation job calls `list_modules_for(..., include_reference_year=False)`.
