---
status: delivered
issue: 2096
last_updated: 2026-08-19
summary: Validated modules with no data were dropped from validated_buckets and the results summary, so the Results chart greyed them out with a "Validate X to see results" tooltip; fixed at recompute time, pending the admin stats-recompute backfill for reports persisted before the fix.
---

# 2096 — Empty validated modules shown as "not validated" in Results

## Problem

Validating a module that has no data entries did not register anywhere the
Results page reads validation from. In the overall results chart the module's
bar stayed greyed out with the "Validate {module} to see results" tooltip,
and its per-module section on the Results page kept the validation
placeholder card — even though the sidebar timeline correctly showed the
module as validated (it reads `module_states`, a different source).

Two independent read paths had the same bug:

1. **`validated_buckets` (drives the chart).**
   `_build_report_stats` (`app/services/carbon_report_service.py`) filtered
   the validated bucket list with `and bucket_nodes.bucket.key in buckets`.
   An empty module contributes no bucket to the merged stats, so its key was
   dropped from `validated_buckets` no matter its status. The frontend turns
   `validated_buckets` into `validated_categories`
   (`frontend/src/utils/emissionStatsAdapter.ts` for the report-stats path),
   and `ModuleCarbonFootprintChart.vue` greys out any category not in that
   list and swaps its tooltip for the validate prompt.

2. **Results summary (drives the per-module section placeholders).**
   `UnitTotalsService._validated_module_totals` skipped rows where `stats`
   was not a dict (`None` for a never-computed module), so a validated empty
   module produced no key in `current_emissions`. `compute_results_summary`
   emits one `module_results` row per key, and `ResultsPage.vue` shows the
   validation placeholder for any module without a row
   (`getModuleResult(module)` undefined).

## Fix (commit ba51637e3)

- `_build_report_stats`: removed the `in buckets` condition —
  `validated_buckets` now lists every bucket key whose module type is
  validated, whether or not the bucket has data. Downstream consumers are
  safe with a validated-but-dataless key: `derive_report_sections` only
  reads keys via `buckets.get(...)`, `build_year_comparison` already skips
  `total_kg <= 0` buckets, and the chart renders a normal (non-grey) zero
  bar via its `MAIN_RESULT_CATEGORIES` placeholder rows.
- `UnitTotalsService._validated_module_totals`: a validated module with
  non-dict stats now contributes `0.0` instead of being skipped, so the
  results summary emits a real row (0 t, 0 km equivalent) and the Results
  page shows zeros instead of the placeholder card.

No schema or endpoint shape changed; both fixes only change which keys the
recompute writes / the summary read returns.

## Rollout — stale persisted stats

`validated_buckets` lives in the persisted `carbon_report.stats`, rewritten
only by `recompute_report_stats_many`. Reports validated before this deploy
keep the old list until something re-triggers their aggregation, so the
chart symptom survives the deploy for existing data.

Backfill: `POST /modules-sync/admin/recompute-stats` (backoffice pipeline
permission) after deploy. It dispatches root aggregation jobs per
`(module_type, year)` scope with `skip_module_status_update`, so validation
statuses are preserved while `carbon_report.stats` is rebuilt under the new
code. The results-summary side needs no backfill — it derives from module
status + stats at read time.

Edge left open: a report whose modules are all empty refreshes no module in
any scope, so its report rollup may not fire from the backfill. Re-validating
any module of such a report rebuilds it.

## Verification

- Validate a module with zero entries → overall results chart shows the
  category with a normal label, zero bar, standard tooltip (no "Validate X
  to see results"); the per-module Results section shows 0 t / 0 km instead
  of the placeholder card.
- Existing report from before the fix shows the old behavior until the
  admin recompute (or any data mutation on the report) runs, then matches.
