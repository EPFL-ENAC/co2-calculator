---
status: delivered
issue: 2293
last_updated: 2026-08-24
title: "Explorer sandboxes are private per user"
summary: "Two users of the same unit shared one Simulator Explore report, so each saw the other's temp entries. Explore projects are now scoped per (unit, created_by) like Planner plans: the lookup/create path stamps and filters carbon_projects.created_by, and the one-per-unit partial unique index is split per type."
---

# 2293 — Explorer data visible across users of the same unit

## Problem

The Simulator Explore sandbox was keyed on the unit alone: one
`Simulator_Explore` `CarbonProject` per unit (enforced by the partial unique
index `uq_carbon_projects_unit_type_nonplan`), holding one report per
reference year. Two members of the same unit therefore wrote into the same
temp report — user 1's Process Emissions entries showed up for user 2 and
vice versa after re-entering the Explorer.

## Fix

Scope the explore project per user, mirroring the Planner
(`carbon_projects.created_by`, already used for `Simulator_Plan` rows). No
new column and no frontend change — the existing GET-then-POST flow in
`workspace.ts#selectSimulatorExploreCarbonReport` is already authenticated,
so the backend resolves the caller's own sandbox transparently.

- `models/carbon_project.py` — replace the single non-plan unique index with
  two: `uq_carbon_projects_unit_type_calculator` (one Calculator project per
  unit, unchanged behavior) and `uq_carbon_projects_unit_explore_creator`
  (`unit_id, created_by` where type = `Simulator_Explore`).
- `repositories/carbon_report_repo.py` — `get_explore_by_unit_and_reference_year`
  takes `created_by` and joins it into the project filter.
- `services/carbon_report_service.py` — `get_explore` / `create_explore`
  take `created_by`; new `_get_explore_project` / `_create_explore_project`
  helpers stamp `created_by` + `created_at` on the explore project.
  `_get_project` is now Calculator-only (explore, like plans, is no longer
  unique per unit+type).
- `api/v1/carbon_report.py` — both explore endpoints pass
  `current_user.id`; the 24 h-TTL background refresh recreates the report
  under the same user (`_refresh_explore_background` gains `created_by`).

## Migration (`ff4f9bac0339`)

Pure index swap, no data migration: `uq_carbon_projects_unit_type_nonplan`
is dropped and replaced by the two per-type indexes above.

## Tests

`tests/unit/services/test_carbon_report_service.py` gains
`test_get_explore_does_not_cross_users` (fails without the fix: user B's
lookup returned user A's report); existing explore tests updated for the new
`created_by` parameter, as are the route tests in
`tests/unit/v1/test_carbon_report.py`.
