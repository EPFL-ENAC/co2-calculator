---
status: in-progress
issue: 1976
last_updated: 2026-08-05
title: "Simulator Plan — Grant proposal mode (first increment)"
summary: "Plans gain a persisted Grant proposal checkbox and, when checked, a Project Grant section (a dedicated grant carbon report) rendered before the year sections; Equipment cannot be excluded from it. Grant tables carry a kgCO₂eq-over-project-years column (#1979 first cut), the section carries a total grant budget plus per-submodule budgets with a distribution check (#1978), and Research Facilities render a custom platform-selection grid (#1980). The custom Equipment module (#1981) and grant results (#1977) are follow-ups."
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
  deactivating Equipment on a grant report (`GRANT_LOCKED_MODULE_TYPES`): a
  grant proposal is first and foremost about the equipment it funds.
  Research Facilities left the locked set once their opt-in platform grid
  shipped (#1980) — an unselected platform list already means "not used".

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

### #1979 first cut: kgCO₂eq over the project's years

- In grant tables only (not year sections, not the grant-locked
  Equipment, not headcount), the kgCO₂eq column is relabeled
  "kgCO₂eq / year" and a "kgCO₂eq over {n} years" column follows it —
  same `kg_co2eq` field multiplied by the plan's year count in
  `ModuleTable` (presentation only, no stored derived value). The
  Purchases grid shows the same pair inline per row (in tCO₂eq).
- `projectYearsCount` (end − start + 1) flows
  page → PlannerYearSection → ModuleTableSection → SubModuleSection →
  ModuleTable.
- Width: grant tables wrap their header cells
  (`co2-table--wrap-headers`) and narrow the % slider to 150px, so every
  module fits without horizontal scroll except Buildings' Rooms table
  (14 columns, ~1509px intrinsic width — it already overflowed narrow
  viewports before this change; revisit with the module redesign).

### #1978: grant budget with distribution check

- `carbon_reports.budget` + `budget_currency` (grant total) and
  `carbon_report_modules.budgets` (JSON, keyed by submodule id) — migration
  `9539986fa17b`.
- `PATCH /carbon-reports/{id}/budget` (`{budget, budget_currency}`) and
  `PATCH /carbon-reports/{id}/modules/{module_type_id}/budget`
  (`{submodule, budget}`; null clears the entry). Both 409 on non-grant
  reports and enforce plan-edit scope. Like purchase entries, the currency
  code is not validated server-side; the select constrains it.
- UI: a Grant budget section right after the reference year — total input
  plus a currency select (the purchase module's currency set, extracted to
  `constant/currencies.ts` and shared) and the check line
  "X of Y distributed, Z remaining", red when the distributed budgets
  exceed the total. Each submodule table carries a "Budget"-titled block:
  a "{submodule} budget" field (chosen currency as suffix) and a one-line
  hint, separated from the table. Single-grid Headcount and Purchases
  carry one field each, keyed by module name. The wording never says
  "submodule" and only shows the currency the user picked.

### #1980: grant-mode Research Facilities module

- In the Project Grant section only (year sections keep the standard
  prefilled table), RF renders `PlannerResearchFacilityRows`: an
  "Add a platform" searchable dropdown offering the **current workspace
  year's** whole platform list — common facilities and animal facilities
  (labeled with their rodent/fish type) — sourced from the new
  `GET /factors/{data_entry_type}/list?year=` endpoint. (Product decision
  overriding the issue's reference-year note. Emission computation still
  resolves the grant's reference-year factors — the plan-wide invariant —
  so a platform missing from the reference year shows no kg; the two years
  coincide in normal use.)
- Picking a platform adds its row: planned use entered in the platform's
  own metric (the factor's `use_unit` — budget/hours/CPU/housing; shown as
  the field suffix), kgCO₂eq per year and over the project's years computed
  by the existing RF share formula against the **reference year's factors**.
  Rows persist as ordinary `research_facilities` / `animal_facilities`
  entries on the grant report through the generic submodule routes; the
  delete button removes the entry.
- A group (research facilities / animal facilities) only renders — title,
  budget field and rows — once it holds at least one platform.
- Grant reports skip the RF snapshot-prefill on reference-year changes
  (entries are still cleared so baselines never mix); year reports keep
  prefilling.
- The metric is fixed by the platform's factor: offering a free metric
  choice would need multi-unit factors (backoffice change) since the
  formula requires an exact `use_unit` match — deferred with #1980's
  remaining design.

## Deferred to follow-up issues

- **#1977 Results**: grant results in the chart/aggregates and the PDF
  export (grant is currently excluded from all three).
- **#1979 remainder**: the over-project-years column for Equipment once its
  custom grant module lands (planner headcount is already manual, so the
  "not prefilled" requirement holds by construction; the RF grid shows the
  over-project values inline).
- **#1981 Equipment**: the custom grant-mode equipment module (manual
  per-row percentages, global percentage toggle, add via dropdown). Until
  then it renders the standard planner table but cannot be excluded.
- Cosmetic: the reference-year dialog wording says "Planned year {year}"
  for the grant section (it shows the start year).
