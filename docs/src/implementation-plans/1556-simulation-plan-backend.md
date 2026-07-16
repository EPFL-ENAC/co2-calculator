---
status: in-progress
issue: 1556
last_updated: 2026-07-16
title: "Simulator Plan — Backend"
summary: "Backend architecture for the Simulator Plan module: plan-year reports as ordinary CarbonReports, reference-year factor resolution, per-module planner schemas, and the API surface for the year-range lifecycle."
---

# Simulator Plan — Backend

Backend slice of [#404 Simulator Module](404-simulation-module-plan.md) (PRD: #1555, task: #1556).

## Context

The Simulator Plan lets a user project a research project's footprint over a
year range, reusing reference-year data and factors, without writing back to
the Calculator. Commit #1804 shipped an esquisse: plan CRUD
(`api/v1/simulator_plan.py`, `services/simulator_plan_service.py`,
`repositories/carbon_project_repo.py`), `CarbonProject.start_year/end_year/
is_viewable_by_unit_members/created_by`, and `CarbonReport.reference_year`.
That esquisse survives; this plan extends it.

## Core principle

**Plan data is ordinary Calculator data under a different project.** A
plan-year is a `CarbonReport` with `carbon_project_id → Simulator_Plan
project`, `year` = simulated year, `reference_year` = chosen baseline.
Entries are ordinary `data_entries`; emissions flow through the existing
compute pipeline (`data_entry_emission_service.py`). Consequences:

- Zero new tables. "No write-back" is structural (separate report rows).
- Calculator-identical forms reuse the existing module/data-entry API.
- Full per-year emissions — including headcount — come from the existing
  recalc + stats machinery (headcount already computes `fte × factor`,
  `modules/headcount/schemas.py` `resolve_computations`).
- The `% of reference year` slider **already exists**:
  `_get_percentage_override_kg` in `data_entry_emission_service.py` honors
  `data.percentage_of_last_year`, matching the reference-year entry by
  stable identifiers.

## Cardinality (per project type)

| Type              | Projects per unit  | Reports under project                                                                                                                                                      |
| ----------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Calculator        | 1                  | 1 per year (open years; in practice users work one year at a time)                                                                                                         |
| Simulator_Explore | 1                  | n per reference year — `create_explore` always creates a new one; resolution is "latest wins" (`get_explore_by_unit_and_reference_year` orders by `last_updated`, limit 1) |
| Simulator_Plan    | n (unique by name) | exactly 1 per year in `start_year..end_year`                                                                                                                               |

Unlike Explore's latest-wins, plan-year reports must be individually
addressable — hence direct `carbon_report_id` addressing below.

Range shrink is destructive by design (confirmed with product 2026-07-15):
out-of-range reports and their entries are deleted.

The plan's report set is **derived from the project's year range**: setting or
changing `start_year`/`end_year` syncs child reports (create missing years
with their modules via `create_all_modules_for_report`; delete out-of-range
years and their entries — the user shrank the range deliberately).

## Design decisions

### 1. Factor year = reference year

Flip precedence to `reference_year if set else year` in
`DataEntryEmissionService._get_year_from_data_entry` and
`modules/professional_travel/schemas.py::_get_report_year_for_module`.
No behavior change for Calculator (`reference_year` is NULL) or Explore
(`year == reference_year`); mandatory for Plan (future years have no
factors). Reference-year dropdown = years open in the Calculator, from
existing `year_configuration`.

### 2. Split `modules/<name>/schemas.py`

Each Calculator module's `schemas.py` splits into:

- `data_entries.py` — entry Create/Update/Response validation schemas
- `factors.py` — factor handler schemas (`BaseFactorHandler` subclasses)
- `handlers.py` — `BaseModuleHandler` subclass (factor resolution +
  emission-compute config)

`__init__.py` re-exports; one mechanical pass over all 8 modules. This is
what lets the planner reuse the factor/emission side while owning its own
data-entry schemas.

### 3. `app/modules_planner/` — only for genuinely new kinds

Planner modules that differ from the Calculator get a subpackage with their
own schemas + handler, registered in the same `MODULE_HANDLERS` registry
under new `DataEntryTypeEnum` values (80+ range). Their `FactorQuery` points
at existing Calculator factors — no new factor rows.

- **Headcount** (new kind, `planner_headcount = 80`): manual aggregate FTE
  per SIUS-code category — no `name`/`user_institutional_id`, FTE unbounded
  (Calculator's `HeadCountCreate` caps FTE ≤ 1 per person). Reuses
  member/student factors via `FactorQuery(data_entry_type=member|student)`.
- **Travel**: no new kind. Same plane/train handlers and factors; the
  traveler dropdown sends a category token (`internal` / `external epfl` /
  `internal epfl`) in `user_institutional_id` instead of a person — frontend
  concern, backend unchanged.
- **Purchases** (delivered): `planner_purchase` / `planner_purchase_budget`
  in `app/modules_planner/purchase/` — CHF per submodule XOR one global
  budget, enforced at creation; average EFs arrive as factor rows.
- Type-2 modules (Process Emissions, Buildings, Equipments, Research
  Facilities, External Clouds & AI): no new kinds — Calculator entries +
  snapshot prefill + `percentage_of_last_year`.

### 4. API surface

Extends the esquisse in `api/v1/simulator_plan.py`:

- `PATCH /simulator-plan/{plan_id}` grows `start_year`, `end_year`,
  `is_viewable_by_unit_members` (today: rename only). The service syncs
  child reports to the range (see Cardinality).
- `PATCH /simulator-plan/{plan_id}/years/{year}` `{reference_year}` — sets
  the baseline for one plan-year report. Changing it re-snapshots type-2
  modules (wipe module entries, re-copy) — slice 2.
- `GET /simulator-plan/{plan_id}/years` — list plan-year reports (id, year,
  reference_year, stats) for the results chart.
- **Identity addressing — lookup once, then identity.**
  `(unit_id, year, carbon_project_type)` is a _query_, not an identity —
  ambiguous once a unit has several plans. The identity-route family
  already exists in `api/v1/carbon_report.py`
  (`GET /carbon-reports/{id}`, `GET /carbon-reports/{id}/modules/`,
  `PATCH /carbon-reports/{id}/modules/{module_type_id}/status`) and the
  frontend already tracks `currentCarbonReportId` (`stores/modules.ts`).
  Extend that family verbatim with the module/data-entry operations
  currently under `/{unit_id}/{year}/{module_id}/...`
  (~15 routes in `carbon_report_module.py`):

  `/carbon-reports/{carbon_report_id}/modules/{module_type_id}/{submodule_id}/{item_id}`

  `carbon_report_id` alone pins unit (authz), year, and project — no
  redundant parent segments (a `/project/{id}/report/{id}/...` chain would
  need per-request consistency checks or silently ignore segments).
  `module_type_id` over `carbon_report_module_id`: unique within a report,
  and the frontend already thinks in module-type constants.
  The unit/year natural key survives as exactly one lookup (get/create
  report for unit/year/type → report + modules) used when the Calculator
  workspace selects unit+year; all subsequent operations use report-id
  routes. Legacy unit/year module routes are then deleted (no dual path).
  Genuinely unit/year-scoped aggregates (`modules-stats/.../totals`,
  results-summary) are workspace queries, not resource addressing — they
  keep their shape.

- **Frontend**: `utils/modulePath.ts::buildModulePath` is the single
  source of truth for legacy module paths (plus ~4 stragglers in
  `stores/modules.ts` / `api/modules.ts`) — its signature switches from
  `(moduleType, unit, year)` to `(moduleType, carbonReportId)`;
  `carbon_project_type` query juggling disappears. Planner stores
  (`stores/simulatorPlans.ts`) key state by `carbon_project_id` (plan) and
  `carbon_report_id` per year (from `GET .../years`). Browser URLs are
  unchanged: `.../project-planner/:name` (plan name is the URL identifier;
  all year sections on one page).
- **Rollout, all under #1556** (decided 2026-07-15; delivered 2026-07-16
  as a single-branch rewrite rather than three sequenced PRs): the ~11
  module routes were rewritten in place to the identity paths (no
  transitional delegation), the frontend swapped in the same branch, and
  the `carbon_project_type` param removed — no dual-path window ever
  existed. The modules router now mounts under `/carbon-reports`.
- **Module Active checkbox**: new nullable `is_active` bool on
  `carbon_report_modules` (migration via `make db-revision`), default true.
  Inactive modules are excluded from report `stats` aggregation.
- **Snapshot prefill** (slice 2):
  `POST /simulator-plan/{plan_id}/years/{year}/modules/{module_type}/prefill`
  copies reference-year Calculator entries into the plan module with
  `percentage_of_last_year = 100`. Note: the slider override computes
  against the _live_ reference entry when it still exists (existing
  `_get_percentage_override_kg` matching); if the source disappears, the
  snapshot data at its stored quantities is the fallback.

### 5. Permissions

Decided with product (2026-07-15): plans stay unit-scoped (esquisse's
`require_unit_access`; unit-less users out of scope). A plan is visible to
non-creator unit members only when `is_viewable_by_unit_members` is true,
and shared plans are **read-only** for non-creators — only the creator (or
backoffice) mutates. Enforced in `_require_plan_unit_access`.

## Slices

### Slice 1 — Travel + Headcount end-to-end (delivered 2026-07-16)

- [ ] Split `modules/<name>/schemas.py` → `data_entries.py` / `factors.py` /
      `handlers.py` (all 8 modules, mechanical).
- [x] Factor-year flip (`reference_year or year`) in the two resolution
      helpers.
- [x] Plan year-range lifecycle: PATCH plan (start/end year, visibility) +
      report sync in `simulator_plan_service.py`; reference-year PATCH per
      plan-year report; GET years.
- [x] Identity routes: extend `/carbon-reports/{id}/modules/{module_type}`
      with the entry CRUD/stats operations (legacy unit/year routes
      delegate to the shared impl).
- [x] Frontend: planner stores keyed by project/report ids (incl.
      `constant/planner-module-config` defining each module's planner
      behavior in Calculator order);
      `buildModulePath` swapped to `(moduleType, carbonReportId)` for
      Calculator/Explore; then delete legacy unit/year module routes +
      `carbon_project_type` param (rollout steps 2–3).
- [x] `carbon_report_modules.is_active` migration + PATCH + stats exclusion.
- [x] Permissions: hide unshared plans from non-creators in list/get; reject
      writes (plan, plan-year reports, their entries) from non-creators —
      including data-entry writes arriving via the module routes when the
      target report belongs to a `Simulator_Plan` project.
- [x] `modules_planner/headcount/`: schemas + handler
      (`planner_headcount = 80`), reusing member/student factors.
- [x] Travel: verify plane/train entry CRUD + emissions work against a
      plan-year report (category token in `user_institutional_id`); no code
      expected beyond the disambiguation param.
- [x] Tests: plan lifecycle sync, disambiguation, reference-year factor
      lookup, planner-headcount emissions, is_active exclusion.

### Slice 2 — Snapshot prefill (delivered 2026-07-16, generic for all type-2 modules)

- [x] Snapshot-prefill endpoint + service: `POST /carbon-reports/{id}/modules/{module}/prefill` copies the
      reference-year Calculator entries at `percentage_of_last_year =
100` with `source = PLANNER_SNAPSHOT` and `source_data_entry_id`
      (the slider matches its exact source row; deleted sources fall
      back to the snapshot data). Generic — works for every type-2
      module, no per-module code.
- [x] Re-snapshot on reference-year change (wipe snapshot rows +
      re-copy from the new baseline; user-added rows survive).
- [x] Slider override verified: `source_data_entry_id` matching unit
      tests + SQLite prefill/re-snapshot lifecycle tests.

### Slice 3 — Remaining modules + results

- [ ] Buildings, Equipments, Research Facilities, External Clouds & AI
      (type-2): backend prefill is already generic — remaining work is
      frontend wiring only (planner-module-config marks them 'prefilled').
- [x] Purchases planner kinds (delivered 2026-07-16):
      `planner_purchase = 81` (CHF total per submodule, emission type
      resolved per category) and `planner_purchase_budget = 82` (one
      global budget → `purchases__goods_and_services`). XOR + duplicate
      rules enforced at entry creation (422 codes). Emissions compute
      `amount_chf × ef_kg_co2eq_per_chf` from factors keyed on the
      planner kinds — the average-EF methodology ships as factor data
      (CSV upload), not code; entries carry no kg_co2eq until those
      factors exist.
- [ ] Results aggregation across active modules/years for the chart;
      exports (PDF/CSV) per #404 scope decision.

## Verification

- `uv run pytest backend/tests/unit/services/test_simulator_plan_service.py`
  plus new tests above (user runs the suite).
- `/verify` skill: create a plan, set years 2027–2029 with reference year
  2024, add planner-headcount FTE rows and a travel entry, confirm non-zero
  per-year emissions in the plan-year report stats and zero writes to the
  Calculator reports.- [x]status: in-progress
  issue: 1556
  last_updated: 2026-07-16
  title: "Simulator Plan — Backend"
  summary: "Backend architecture for the Simulator Plan module: plan-year reports as ordinary CarbonReports, reference-year factor resolution, per-module planner schemas, and the API surface for the year-range lifecycle."

---

# Simulator Plan — Backend

Backend slice of [#404 Simulator Module](404-simulation-module-plan.md) (PRD: #1555, task: #1556).

## Context

The Simulator Plan lets a user project a research project's footprint over a
year range, reusing reference-year data and factors, without writing back to
the Calculator. Commit #1804 shipped an esquisse: plan CRUD
(`api/v1/simulator_plan.py`, `services/simulator_plan_service.py`,
`repositories/carbon_project_repo.py`), `CarbonProject.start_year/end_year/
is_viewable_by_unit_members/created_by`, and `CarbonReport.reference_year`.
That esquisse survives; this plan extends it.

## Core principle

**Plan data is ordinary Calculator data under a different project.** A
plan-year is a `CarbonReport` with `carbon_project_id → Simulator_Plan
project`, `year` = simulated year, `reference_year` = chosen baseline.
Entries are ordinary `data_entries`; emissions flow through the existing
compute pipeline (`data_entry_emission_service.py`). Consequences:

- Zero new tables. "No write-back" is structural (separate report rows).
- Calculator-identical forms reuse the existing module/data-entry API.
- Full per-year emissions — including headcount — come from the existing
  recalc + stats machinery (headcount already computes `fte × factor`,
  `modules/headcount/schemas.py` `resolve_computations`).
- The `% of reference year` slider **already exists**:
  `_get_percentage_override_kg` in `data_entry_emission_service.py` honors
  `data.percentage_of_last_year`, matching the reference-year entry by
  stable identifiers.

## Cardinality (per project type)

| Type              | Projects per unit  | Reports under project                                                                                                                                                      |
| ----------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Calculator        | 1                  | 1 per year (open years; in practice users work one year at a time)                                                                                                         |
| Simulator_Explore | 1                  | n per reference year — `create_explore` always creates a new one; resolution is "latest wins" (`get_explore_by_unit_and_reference_year` orders by `last_updated`, limit 1) |
| Simulator_Plan    | n (unique by name) | exactly 1 per year in `start_year..end_year`                                                                                                                               |

Unlike Explore's latest-wins, plan-year reports must be individually
addressable — hence direct `carbon_report_id` addressing below.

Range shrink is destructive by design (confirmed with product 2026-07-15):
out-of-range reports and their entries are deleted.

The plan's report set is **derived from the project's year range**: setting or
changing `start_year`/`end_year` syncs child reports (create missing years
with their modules via `create_all_modules_for_report`; delete out-of-range
years and their entries — the user shrank the range deliberately).

## Design decisions

### 1. Factor year = reference year

Flip precedence to `reference_year if set else year` in
`DataEntryEmissionService._get_year_from_data_entry` and
`modules/professional_travel/schemas.py::_get_report_year_for_module`.
No behavior change for Calculator (`reference_year` is NULL) or Explore
(`year == reference_year`); mandatory for Plan (future years have no
factors). Reference-year dropdown = years open in the Calculator, from
existing `year_configuration`.

### 2. Split `modules/<name>/schemas.py`

Each Calculator module's `schemas.py` splits into:

- `data_entries.py` — entry Create/Update/Response validation schemas
- `factors.py` — factor handler schemas (`BaseFactorHandler` subclasses)
- `handlers.py` — `BaseModuleHandler` subclass (factor resolution +
  emission-compute config)

`__init__.py` re-exports; one mechanical pass over all 8 modules. This is
what lets the planner reuse the factor/emission side while owning its own
data-entry schemas.

### 3. `app/modules_planner/` — only for genuinely new kinds

Planner modules that differ from the Calculator get a subpackage with their
own schemas + handler, registered in the same `MODULE_HANDLERS` registry
under new `DataEntryTypeEnum` values (80+ range). Their `FactorQuery` points
at existing Calculator factors — no new factor rows.

- **Headcount** (new kind, `planner_headcount = 80`): manual aggregate FTE
  per SIUS-code category — no `name`/`user_institutional_id`, FTE unbounded
  (Calculator's `HeadCountCreate` caps FTE ≤ 1 per person). Reuses
  member/student factors via `FactorQuery(data_entry_type=member|student)`.
- **Travel**: no new kind. Same plane/train handlers and factors; the
  traveler dropdown sends a category token (`internal` / `external epfl` /
  `internal epfl`) in `user_institutional_id` instead of a person — frontend
  concern, backend unchanged.
- **Purchases** (delivered): `planner_purchase` / `planner_purchase_budget`
  in `app/modules_planner/purchase/` — CHF per submodule XOR one global
  budget, enforced at creation; average EFs arrive as factor rows.
- Type-2 modules (Process Emissions, Buildings, Equipments, Research
  Facilities, External Clouds & AI): no new kinds — Calculator entries +
  snapshot prefill + `percentage_of_last_year`.

### 4. API surface

Extends the esquisse in `api/v1/simulator_plan.py`:

- `PATCH /simulator-plan/{plan_id}` grows `start_year`, `end_year`,
  `is_viewable_by_unit_members` (today: rename only). The service syncs
  child reports to the range (see Cardinality).
- `PATCH /simulator-plan/{plan_id}/years/{year}` `{reference_year}` — sets
  the baseline for one plan-year report. Changing it re-snapshots type-2
  modules (wipe module entries, re-copy) — slice 2.
- `GET /simulator-plan/{plan_id}/years` — list plan-year reports (id, year,
  reference_year, stats) for the results chart.
- **Identity addressing — lookup once, then identity.**
  `(unit_id, year, carbon_project_type)` is a _query_, not an identity —
  ambiguous once a unit has several plans. The identity-route family
  already exists in `api/v1/carbon_report.py`
  (`GET /carbon-reports/{id}`, `GET /carbon-reports/{id}/modules/`,
  `PATCH /carbon-reports/{id}/modules/{module_type_id}/status`) and the
  frontend already tracks `currentCarbonReportId` (`stores/modules.ts`).
  Extend that family verbatim with the module/data-entry operations
  currently under `/{unit_id}/{year}/{module_id}/...`
  (~15 routes in `carbon_report_module.py`):

  `/carbon-reports/{carbon_report_id}/modules/{module_type_id}/{submodule_id}/{item_id}`

  `carbon_report_id` alone pins unit (authz), year, and project — no
  redundant parent segments (a `/project/{id}/report/{id}/...` chain would
  need per-request consistency checks or silently ignore segments).
  `module_type_id` over `carbon_report_module_id`: unique within a report,
  and the frontend already thinks in module-type constants.
  The unit/year natural key survives as exactly one lookup (get/create
  report for unit/year/type → report + modules) used when the Calculator
  workspace selects unit+year; all subsequent operations use report-id
  routes. Legacy unit/year module routes are then deleted (no dual path).
  Genuinely unit/year-scoped aggregates (`modules-stats/.../totals`,
  results-summary) are workspace queries, not resource addressing — they
  keep their shape.

- **Frontend**: `utils/modulePath.ts::buildModulePath` is the single
  source of truth for legacy module paths (plus ~4 stragglers in
  `stores/modules.ts` / `api/modules.ts`) — its signature switches from
  `(moduleType, unit, year)` to `(moduleType, carbonReportId)`;
  `carbon_project_type` query juggling disappears. Planner stores
  (`stores/simulatorPlans.ts`) key state by `carbon_project_id` (plan) and
  `carbon_report_id` per year (from `GET .../years`). Browser URLs are
  unchanged: `.../project-planner/:name` (plan name is the URL identifier;
  all year sections on one page).
- **Rollout, all under #1556** (decided 2026-07-15; delivered 2026-07-16
  as a single-branch rewrite rather than three sequenced PRs): the ~11
  module routes were rewritten in place to the identity paths (no
  transitional delegation), the frontend swapped in the same branch, and
  the `carbon_project_type` param removed — no dual-path window ever
  existed. The modules router now mounts under `/carbon-reports`.
- **Module Active checkbox**: new nullable `is_active` bool on
  `carbon_report_modules` (migration via `make db-revision`), default true.
  Inactive modules are excluded from report `stats` aggregation.
- **Snapshot prefill** (slice 2):
  `POST /simulator-plan/{plan_id}/years/{year}/modules/{module_type}/prefill`
  copies reference-year Calculator entries into the plan module with
  `percentage_of_last_year = 100`. Note: the slider override computes
  against the _live_ reference entry when it still exists (existing
  `_get_percentage_override_kg` matching); if the source disappears, the
  snapshot data at its stored quantities is the fallback.

### 5. Permissions

Decided with product (2026-07-15): plans stay unit-scoped (esquisse's
`require_unit_access`; unit-less users out of scope). A plan is visible to
non-creator unit members only when `is_viewable_by_unit_members` is true,
and shared plans are **read-only** for non-creators — only the creator (or
backoffice) mutates. Enforced in `_require_plan_unit_access`.

## Slices

### Slice 1 — Travel + Headcount end-to-end (delivered 2026-07-16)

- [ ] Split `modules/<name>/schemas.py` → `data_entries.py` / `factors.py` /
      `handlers.py` (all 8 modules, mechanical).
- [ ] Factor-year flip (`reference_year or year`) in the two resolution
      helpers.
- [ ] Plan year-range lifecycle: PATCH plan (start/end year, visibility) +
      report sync in `simulator_plan_service.py`; reference-year PATCH per
      plan-year report; GET years.
- [ ] Identity routes: extend `/carbon-reports/{id}/modules/{module_type}`
      with the entry CRUD/stats operations (legacy unit/year routes
      delegate to the shared impl).
- [ ] Frontend: planner stores keyed by project/report ids;
      `buildModulePath` swapped to `(moduleType, carbonReportId)` for
      Calculator/Explore; then delete legacy unit/year module routes +
      `carbon_project_type` param (rollout steps 2–3).
- [ ] `carbon_report_modules.is_active` migration + PATCH + stats exclusion.
- [ ] Permissions: hide unshared plans from non-creators in list/get; reject
      writes (plan, plan-year reports, their entries) from non-creators —
      including data-entry writes arriving via the module routes when the
      target report belongs to a `Simulator_Plan` project.
- [ ] `modules_planner/headcount/`: schemas + handler
      (`planner_headcount = 80`), reusing member/student factors.
- [ ] Travel: verify plane/train entry CRUD + emissions work against a
      plan-year report (category token in `user_institutional_id`); no code
      expected beyond the disambiguation param.
- [ ] Tests: plan lifecycle sync, disambiguation, reference-year factor
      lookup, planner-headcount emissions, is_active exclusion.

### Slice 2 — Snapshot prefill (delivered 2026-07-16, generic for all type-2 modules)

- [x] Snapshot-prefill endpoint + service: `POST /carbon-reports/{id}/modules/{module}/prefill` copies the
      reference-year Calculator entries at `percentage_of_last_year =
100` with `source = PLANNER_SNAPSHOT` and `source_data_entry_id`
      (the slider matches its exact source row; deleted sources fall
      back to the snapshot data). Generic — works for every type-2
      module, no per-module code.
- [x] Re-snapshot on reference-year change (wipe snapshot rows +
      re-copy from the new baseline; user-added rows survive).
- [x] Slider override verified: `source_data_entry_id` matching unit
      tests + SQLite prefill/re-snapshot lifecycle tests.

### Slice 3 — Remaining modules + results

- [ ] Buildings, Equipments, Research Facilities, External Clouds & AI
      (type-2): backend prefill is already generic — remaining work is
      frontend wiring only (planner-module-config marks them 'prefilled').
- [x] Purchases planner kinds (delivered 2026-07-16):
      `planner_purchase = 81` (CHF total per submodule, emission type
      resolved per category) and `planner_purchase_budget = 82` (one
      global budget → `purchases__goods_and_services`). XOR + duplicate
      rules enforced at entry creation (422 codes). Emissions compute
      `amount_chf × ef_kg_co2eq_per_chf` from factors keyed on the
      planner kinds — the average-EF methodology ships as factor data
      (CSV upload), not code; entries carry no kg_co2eq until those
      factors exist.
- [ ] Results aggregation across active modules/years for the chart;
      exports (PDF/CSV) per #404 scope decision.

## Verification

- `uv run pytest backend/tests/unit/services/test_simulator_plan_service.py`
  plus new tests above (user runs the suite).
- `/verify` skill: create a plan, set years 2027–2029 with reference year
  2024, add planner-headcount FTE rows and a travel entry, confirm non-zero
  per-year emissions in the plan-year report stats and zero writes to the
  Calculator reports.
