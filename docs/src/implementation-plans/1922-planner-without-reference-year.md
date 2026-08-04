---
status: delivered
issue: 1922
last_updated: 2026-08-04
title: "Project Planner: default reference year + no locked modules"
summary: "New plan-year sections default their reference year to the workspace year the planner was opened from (sent with the range PATCH, normal prefill runs); the reference year is removable; module drawers are never locked, so a year whose reference is unset is fully usable for manual input with factors falling back to the unit's latest Calculator report year. No schema change."
---

# Project Planner: default reference year + no locked modules

Part of the planner feedback batch
([#1556](1556-simulation-plan-backend.md),
[#1557](1557-planner-frontend-followups.md)). Previously a plan year was
locked until a reference year was set: every module drawer was disabled, and
factor lookups fell back to the plan year itself (usually a future year with
no factors, so entries computed no emissions).

## Decision (with the lead, 2026-08-04)

- **Default the reference year itself.** When the year range is set and new
  plan-year reports are created, each gets `reference_year` = the workspace
  year the planner page is under (the Assessment Year selector), and the
  normal prefill runs from it — exactly as if the user had picked it in the
  dialog. Changing it later keeps today's destructive rebuild.
- **No migration.** Three designs were discarded: persisting a
  `factor_year` column on `carbon_projects` (workspace year frozen at plan
  creation), deriving the default from the latest opened year
  configuration, and an `assessment_year` column scoping the plan list per
  workspace year (implemented then rolled back at the lead's request).
- **The reference year is removable.** The dialog offers a "No reference
  year (manual data entry)" option; removal empties the prefilled modules
  exactly like a change does (`SimulatorPlanReferenceYearUpdate.reference_year`
  is nullable, `_prefill_reference_modules` wipes before the None
  early-return), and any change now requires the acknowledgment checkbox,
  since manual rows can exist before a first set.
- **Modules are never locked.** All planner modules (not just the four the
  spec names) accept manual input even when a year's reference is unset
  (legacy plans, duplicated plans — `duplicate_plan` copies the range but
  not the reference years). For those, factor lookups fall back to the year
  of the unit's most recent Calculator report, derived by joining
  `carbon_projects` (type Calculator) with `carbon_reports`; stored
  emissions of such entries keep their old factors until an entry is edited
  (same staleness rule as factor re-uploads).

## Backend

- `SimulatorPlanUpdate.default_reference_year` — sent by the frontend with
  the range PATCH; `_sync_year_reports` applies it (create report with
  `reference_year`, run `_prefill_reference_modules`, refresh the report
  rollup) **only to reports the sync creates** — existing reports keep
  their reference year.
- `app/utils/factor_year.py` — `resolve_factor_year(session, report)`, the
  single factor-year chain: `reference_year` → (Simulator Plan reports only)
  unit's latest Calculator report year → `report.year`. Backed by
  `CarbonProjectRepository.get_latest_calculator_year(unit_id)`.
- Routed through the helper (was three hand-rolled copies of
  "reference_year wins"):
  - `DataEntryEmissionService._get_year_from_data_entry`
  - the inline fallback in `DataEntryEmissionService.prepare_create`
  - `_get_report_year_for_module` in `app/modules/professional_travel/handlers.py`
- `SimulatorPlanRead.default_factor_year` (derived, read-only) exposes the
  unset-reference fallback so the frontend's dropdowns use the same year
  the backend computes with.

## Frontend

- `PlannerProjectInfo.vue` sends `default_reference_year:
Number(route.params.year)` with the range PATCH; the store gives that
  PATCH the same 5-minute timeout as `setReferenceYear` (it now prefills).
- `PlannerYearSection.vue`: the `!hasReferenceYear` drawer gate is removed;
  `factorYear` mirrors the backend chain (`reference_year ??
plan.default_factor_year ?? yearData.year`) and feeds
  `ModuleTableSection`'s `:factor-year` and the `factorMountKey` remount
  keys; the "% of reference year" columns only render when a reference year
  exists.
- `planner_reference_year_hint` (en/fr) presents the reference year as
  optional and names the fallback factor year. The print composable's
  taxonomy year follows the same chain.

## Tests

- `backend/tests/unit/utils/test_factor_year.py` — the resolution chain
  (reference year wins; plan without reference → latest Calculator year;
  no Calculator report → own year; Calculator report → own year).
- `test_simulator_plan_service.py` — range sync defaults the reference year
  on newly created reports only; without `default_reference_year` the
  reference stays unset; removal wipes the prefilled modules.
