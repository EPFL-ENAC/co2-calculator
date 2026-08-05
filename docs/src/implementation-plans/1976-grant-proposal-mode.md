---
status: in-progress
issue: 1976
last_updated: 2026-08-05
title: "Simulator Plan — Grant proposal mode (first increment)"
summary: "Plans gain a persisted Grant proposal checkbox and, when checked, a Project Grant section (a dedicated grant carbon report) rendered before the year sections with the same module list; Equipment and Research Facilities cannot be excluded from it. Custom Equipment/RF grant modules (#1980/#1981), the over-all-years column and budget tracking (#1978/#1979) and grant results (#1977) are follow-ups."
---

# Simulator Plan — Grant proposal mode (first increment)

Umbrella issue [#1976](https://github.com/EPFL-ENAC/co2-calculator/issues/1976).
This plan delivers the structural first cut and settles the open design
question from the issue: the Grant proposal checkbox lives in the Project
information panel **in addition to** the year selection, and the Project
Grant section renders **before** (not instead of) the year sections.

## Shipped in this increment

### Data model

- `carbon_projects.is_grant_proposal` (bool, default false): the plan-level
  checkbox state.
- `carbon_reports.is_grant` (bool, default false): marks the plan's single
  Project Grant report. It is anchored to the plan's **start year** (grant
  entries resolve factors from the reference year, not the report year, so
  the anchor is only an ordering/identity anchor).
- `uq_carbon_reports_project_year` widened to
  `(carbon_project_id, year, is_grant)` — the grant report shares its year
  with the start-year report. Migration `3d74009feee4`.

### Backend behavior

- `SimulatorPlanService._sync_year_reports` also syncs the grant report:
  created when `is_grant_proposal` and the year range are set, its year
  follows `start_year` (keeping its entries), and it is **deleted with its
  entries** when the checkbox is unchecked (destructive by design, like
  shrinking the year range).
- `PATCH /project-plans/{id}/years/{year}` takes `is_grant` in the body to
  disambiguate the grant report from the start-year report.
- `GET /project-plans/{id}/years` returns the grant report first
  (`is_grant` on the DTO); the frontend renders sections in list order.
- Grant stats are **excluded** from `/aggregate-stats`, the home-table plan
  totals (`list_report_stats_by_project`) and the print report until #1977
  settles how grant results combine with per-year results — summing both
  would count the project twice.
- `PATCH /carbon-reports/{id}/modules/{module_type_id}/active` rejects (409)
  deactivating Equipment or Research Facilities on a grant report
  (`GRANT_LOCKED_MODULE_TYPES`): a grant proposal is first and foremost
  about the equipment and research facilities it funds.

### Frontend

- `PlannerProjectInfo`: Grant proposal section (checkbox + hint) between the
  Project name and the Year selection; the generate button moved to the
  bottom of the panel, full-width and one size up, relabeled "Create project
  sections" since it now syncs the grant section too. Dirty tracking covers
  the checkbox; the PATCH carries `is_grant_proposal`.
- `PlannerYearSection` handles both section kinds: grant sections title
  "Project Grant" instead of the year, use a `grant-` expansion-key prefix
  (the year prefix would collide with the start-year section), pass
  `is_grant` on reference-year updates, and disable the Active checkbox for
  Equipment and Research Facilities with a dedicated tooltip.
- For now the grant section reuses the standard planner module list
  unchanged (same reference-year gate, same prefilled behavior).

## Deferred to follow-up issues

- **#1977 Results**: grant results in the chart/aggregates and the PDF
  export (grant is currently excluded from all three).
- **#1978 Budget**: per-module budget entry + non-distributed budget
  counter.
- **#1979 Modules**: the "over all project years" multiplied column in every
  grant module table; headcount not prefilled in grant mode.
- **#1980 RF / #1981 Equipment**: the custom grant-mode modules (manual
  per-row percentages, global percentage toggle, platform selection). Until
  then both render the standard planner tables but cannot be excluded.
- Cosmetic: the reference-year dialog wording says "Planned year {year}"
  for the grant section (it shows the start year).
