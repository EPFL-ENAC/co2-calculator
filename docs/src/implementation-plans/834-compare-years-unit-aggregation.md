---
status: delivered
issue: 834
last_updated: 2026-08-04
title: "Compare Years: aggregate across combined units + reword target box"
summary: "Replace the single-unit multi-year-report-stats endpoint with GET /merged/multi-year-report-stats (unit_ids query, allow-list auth factored out of the year-scoped helper), wire combined units from ResultsPage through CompareYearsDialog, and reword the target-gap KPI to the approved 'Reduction needed to reach {year} target' phrasing with a template-side minus sign."
---

# Compare Years: aggregate across combined units + reword target box

## Problem (follow-up feedback on #834)

Two collaborator asks before closing the issue:

1. On the Results page, "Add a Unit" combines units and every `/merged/*`
   stats endpoint respects the combined perimeter — but the Compare Years
   pop-up ignored it. `CompareYearsDialog` received a single `unit-id` and
   called `GET /modules-stats/unit/{unit_id}/multi-year-report-stats`, so
   with N units combined the dialog silently showed only the selected
   unit's numbers.
2. The target KPI box wording "Missing to reach 2040 target / 11% /
   target 1.3 t CO₂-eq" was unclear. Approved rewording:
   - EN: "Reduction needed to reach 2040 target" / "-11%" /
     "2040 target: 1.3 t CO₂-eq"
   - FR: "Réduction nécessaire pour atteindre l'objectif 2040" / "-11 %" /
     "Objectif pour 2040 : 1.3 t CO₂-eq"

## Decisions

- **Aggregation is server-side** (backend is the source of truth). The
  frontend sends the unit list; the backend groups every unit's report
  stats by year and folds each year with the existing
  `merge_report_stats`, then `build_year_comparison` — the same primitives
  the single-unit endpoint already used for multi-project years.
- **The single-unit endpoint is deleted** (no backward-compatibility
  paths). The single-unit case is a list of one on the merged endpoint.
  Its access semantics therefore shift from `require_unit_access` to the
  `/merged/*` family's allow-list check, which 404s (never 403s, to avoid
  the frontend's hard `/unauthorized` redirect on 403).
- The allow-list check is factored out of the year-scoped
  `_authorize_and_resolve_reports` into `_authorize_unit_ids`, because the
  multi-year endpoint needs all years (`list_by_unit`), not one
  (`get_by_unit_and_year`).
- **No 404 when no unit has any report** — the endpoint returns
  `{"years": []}` like its predecessor; the dialog has a proper no-data
  state.
- The minus sign on the gap percentage is presentation, hardcoded in the
  template for the "missing" case only; `pctMagnitude` stays a positive
  magnitude and the "below target" case stays unsigned.
- `results_compare_years_gap_beaten_label` is untouched — the approved
  proposition only covers the "missing" case.
- The `%` stays glued to the number in both locales (uniform rendering);
  the FR-typography `-11 %` spacing was not adopted.

## Changes

### Backend — `backend/app/api/v1/carbon_report_module_stats.py`

- New `_authorize_unit_ids(db, current_user, unit_ids) -> list[int]`:
  empty → 400, allow-list from `UnitService.get_user_units` → 404 for
  unknown units, deduped ids returned.
- `_authorize_and_resolve_reports` now delegates to it and keeps only the
  per-unit `get_by_unit_and_year` loop; `/merged/report-stats` and
  `/merged/results-summary` behavior unchanged.
- New `GET /merged/multi-year-report-stats?unit_ids=…` returning the same
  `{"years": [...]}` shape as the deleted
  `GET /unit/{unit_id}/multi-year-report-stats`.

### Frontend

- `frontend/src/stores/modules.ts` — `getMultiYearReportStats(unitIds:
number[])` calls the merged endpoint with repeated `unit_ids` params
  (mirrors `getMergedResultsSummary`).
- `frontend/src/components/charts/results/CompareYearsDialog.vue` — prop
  `unitId` → `unitIds: number[]`; KPI template adds the conditional minus
  and passes `year` to `results_compare_years_gap_target`. The dialog
  re-fetches on every open, so changing combined units between opens is
  covered. Objectives need no change: year config is global and
  `computeCompareYearsObjectives` baselines on the aggregated years.
- `frontend/src/pages/app/ResultsPage.vue` — `compareYearsUnitIds` =
  `mergedContext.unitIds` when combining, else the selected report's unit.
- `frontend/src/i18n/results.ts` — reworded
  `results_compare_years_gap_label`, `results_compare_years_gap_target`
  (now takes `{year}`).
- `frontend/scripts/openapi.snapshot.json` + generated
  `frontend/src/types/api/openapi.d.ts` regenerated; the snapshot was
  stale since #1564, so the diff also catches up on routes shipped since.
