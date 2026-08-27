---
status: delivered
issue: 1976
last_updated: 2026-08-26
title: "Simulator Plan — Grant proposal mode (first increment)"
summary: "Plans gain a persisted Grant proposal checkbox and, when checked, a Project Grant section (a dedicated grant carbon report) rendered before the year sections. Grant tables carry a kgCO₂eq-over-project-years column (#1979), the section carries a total grant budget with currency plus per-submodule budgets and a distribution check (#1978), Research Facilities render a platform-selection grid (#1980), Equipment gets a per-line vs global-percentage planning toggle (#1981), and results show a grant vs year-by-year comparison chart plus a grant page in the PDF (#1977)."
---

# Simulator Plan — Grant proposal mode (first increment)

Umbrella issue [#1976](https://github.com/EPFL-ENAC/co2-calculator/issues/1976).
This plan delivers the structural first cut and settles the open design
question from the issue: the Grant proposal checkbox lives in the Project
information panel **in addition to** the year selection, and the Project
Grant section renders **before** (not instead of) the year sections.

## Shipped in this increment

### Data model

- A plan is a grant proposal iff it owns an `is_grant` report. The API still
  exposes `is_grant_proposal` (read and PATCH), but it is derived from that
  report (`EXISTS` in `CarbonProjectRepository._plan_with_creator_stmt`),
  not stored: the former `carbon_projects.is_grant_proposal` column was a
  cache that nothing kept in sync with the report and was dropped
  (migration `277bf6757926`, 2026-08-21).
- `carbon_reports.is_grant` (bool, default false): marks the plan's single
  Project Grant report, enforced by the partial unique index
  `uq_carbon_reports_project_grant` on `(carbon_project_id) WHERE is_grant`. It is anchored to the plan's **start year** (grant
  entries resolve factors from the reference year, not the report year, so
  the anchor is only an ordering/identity anchor).
- `uq_carbon_reports_project_year` widened to
  `(carbon_project_id, year, is_grant)` — the grant report shares its year
  with the start-year report. Migration `3d74009feee4`.

### Backend behavior

- `SimulatorPlanService._sync_year_reports` also syncs the grant report
  from the PATCH's `is_grant_proposal` (`None` keeps the current state):
  created as soon as the checkbox is set (year range or not), its year
  follows `start_year` (keeping its entries), and it is **deleted with its
  entries** when the checkbox is unchecked. The "year sections or grant"
  invariant is checked on every sync, including before a year range is set (destructive by design, like
  shrinking the year range).
- `PATCH /project-plans/{id}/years/{year}` takes `is_grant` in the body to
  disambiguate the grant report from the start-year report.
- `GET /project-plans/{id}/years` returns the grant report first
  (`is_grant` on the DTO); the frontend renders sections in list order.
- `/aggregate-stats` returns `{years, grant}`: the year aggregate and the
  Project Grant report's own stats, charted side by side and never summed
  together — summing both would count the project twice (#1977). The
  home-table plan totals (`list_report_stats_by_project`) stay years-only
  for the same reason.
- Every grant module's Active checkbox is toggleable. An earlier iteration
  locked Equipment/RF on (`GRANT_LOCKED_MODULE_TYPES`); the lock was removed
  once both modules got their own grant-mode UIs (#1980/#1981) — the
  machinery was deleted, not kept dormant.

### Frontend

- `PlannerProjectInfo`: Grant proposal section (checkbox + hint) between the
  Project name and the Year selection; the generate button moved to the
  bottom of the panel, full-width and one size up, relabeled "Create project
  sections" since it now syncs the grant section too. Dirty tracking covers
  the checkbox; the PATCH carries `is_grant_proposal`.
- `PlannerYearSection` handles both section kinds: grant sections title
  "Project Grant" instead of the year, use a `grant-` expansion-key prefix
  (the year prefix would collide with the start-year section), and pass
  `is_grant` on reference-year updates.
- The grant section reuses the standard planner module list (same
  reference-year gate) except where #1980/#1981 swap in custom UIs below.

### #1979 first cut: kgCO₂eq over the project's years

- In grant tables only (not year sections, not headcount), the kgCO₂eq
  column is relabeled
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

### #1977: grant results (first cut)

- On grant proposals the planner results card shows one grouped chart
  (`PlannerGrantComparisonChart`): two bars per category — Project Grant
  vs year by year, legend-labeled, colorblind-aware palette. Its CSV
  button downloads one file per view; the headline row shows both totals
  side by side, split by a vertical separator. Non-grant plans keep the
  single chart and total.
- The PDF gains a "Project Grant" summary page right after the cover
  (reference year, grant total, breakdown chart) — `PlannerPrintYearPage`
  reused with a name title instead of the anchor year. Grant module
  detail pages in the PDF remain open.

### #1981: grant-mode Equipment module

- In the Project Grant section only, Equipment carries a "Planning mode"
  toggle: **Manual entry per line** (each prefilled line has its own
  reference-year percentage, prefilled at the planner's usual 100%) vs
  **Global percentage** (one value applied to all prefilled lines at
  once, shown beside the aggregated reference-year total it scales).
  Adding an equipment through the usual form stays available in both
  modes; hand-added lines are untouched by the global value but a
  confirmed mode switch deletes them.
- Global mode: `PATCH
/carbon-reports/{id}/modules/{module_type_id}/reference-percentage`
  (`{percentage: 0..100}`, grant reports only) updates every snapshot
  entry (`source_data_entry_id` set), recomputes their emissions and the
  stats; the table remounts to refetch its rows. Per-row % controls are
  read-only in global mode (`percentageLocked` prop chain).
- Global mode lists the same prefilled snapshot rows as per-line mode.
  An earlier cut (2026-08-19) filtered them out of the lists and counts
  via an `exclude_snapshots` query param so global mode showed only
  hand-added lines; since every prefilled row is a `PLANNER_SNAPSHOT`
  entry, the tables rendered empty for principal users. That param and
  its frontend prop chain are removed (2026-08-26); visibility is
  governed solely by the standard-user read-time hide
  (`_hide_planner_snapshots_for_viewer`, #2120), so standard users still
  see no snapshot rows in grant modules while principal/global users see
  them in both modes.
- Budgets follow the mode: per-submodule budget fields in per-line mode,
  one module-level budget (key `equipment`) in global mode. Values saved
  in one mode keep counting in the distribution check when the other mode
  is shown.

## Deferred to follow-up issues

- Grant module detail pages in the PDF (#1977 remainder): the grant is
  still a summary page only.
- Cosmetic: the reference-year dialog wording says "Planned year {year}"
  for the grant section (it shows the start year).
