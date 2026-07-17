---
status: proposed
issue: 1557
last_updated: 2026-07-17
title: "Simulator Plan — Frontend"
summary: "Frontend completion plan for the Simulator Plan module: first-priority per-module data-shape & fields audit, then the sub-issue cut for results chart & totals, PDF export, shared-plan read-only mode, purchases XOR UX, and the final design-alignment refactor of the vibecoded first cut."
---

# Simulator Plan — Frontend

Frontend slice of [#404 Simulator Module](404-simulation-module-plan.md)
(PRD: #1555, task: #1557). Companion to
[Simulator Plan — Backend](1556-simulation-plan-backend.md).

Related docs:

- [1557-planner-frontend-followups.md](1557-planner-frontend-followups.md) —
  **superseded by this document**: item A (prefilled slider table) was
  delivered on `task/404/dev`; item B (wrong-plan report resolution) is fixed

Design reference: [Figma proto (approximate)](https://www.figma.com/proto/DXeFrKiXUpqCHUEgXVROng/200_Calculateur-CO2?node-id=4109-47273&starting-point-node-id=4109%3A47273&show-proto-sidebar=1&t=zTVvjLO31Fs0WlI9-1)
plus the annotated screenshots in PRD #1555.

## Context

The backend is essentially delivered (slices 1–2 complete, slice 3 partially:
purchases kinds done, results aggregation open). A first frontend cut was
merged into `task/404/dev` (PR #1816 and follow-up commits through
`7a8f38781`). It is functionally further along than expected — but it was
built fast ("vibecoded"), has no results section, no export, no shared-plan
read-only handling, no tests, and diverges visually from the Simulator
Explore page it should resemble.

## The three module types (PRD) and their planner wiring

| PRD type                                    | Behavior key | Modules                                                                           | Rendering path                                                                                                                                                                                            | Remaining gaps                                                                           |
| ------------------------------------------- | ------------ | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| 1 — Manual entry                            | `manual`     | Headcount, Purchases                                                              | `PlannerHeadcountRows` (headcount); bespoke `plannerPurchase` config with two submodules — per-category CHF (`planner_purchase`) and global budget (`planner_purchase_budget`) — via `ModuleTableSection` | Purchases XOR not expressed in the UI (F4); headcount grid non-standard (F6)             |
| 2 — Prefilled from reference year, % slider | `prefilled`  | Process Emissions, Buildings, Equipment, Research Facilities, External Cloud & AI | `ModuleTableSection` → `SubModuleSection show-reference-columns` → shared `ModuleTable` (reference-kg column + slider) + Calculator add-form                                                              | Reference-year _change_ UX (re-snapshot is destructive for snapshot rows) surfaced in F6 |
| 3 — Empty, Calculator-identical forms       | `empty`      | Travel                                                                            | `withPlannerAdaptations` clones the Calculator config, drops the CSV bar, swaps the traveler dropdown for category tokens (`internal` / `external epfl` / `internal epfl`)                                |                                                                                          |

## Per-module data shape & fields audit (first priority)

**This audit precedes F1** — before building the results chart, every one of
the 8 planner modules must be checked: the backend data schema / API
response shape against what the frontend form sends and the table renders,
the form adapted where the shapes diverge, and a per-module decision
recorded on **which fields appear in the table and which in the form**.

### How shapes flow (the contract surfaces)

- **Backend**: only Headcount (`planner_headcount` = 80) and Purchases
  (`planner_purchase` = 81 / `planner_purchase_budget` = 82) have
  planner-specific DTOs, in `backend/app/modules_planner/{headcount,purchase}/`.
  The five prefilled modules and Travel reuse the **unchanged Calculator
  handlers** in `backend/app/modules/<module>/`; their planner-ness is extra
  keys in `data` (`percentage_of_reference_year` default 100,
  `source_data_entry_id`, source `PLANNER_SNAPSHOT`) injected by
  `prefill_module_from_reference`
  (`backend/app/services/simulator_plan_service.py`).
- Every entry read (`DataEntryResponseGen`,
  `backend/app/schemas/data_entry.py`) carries top-level
  `reference_kg_co2eq` and `percentage_of_reference_year` (null for
  Calculator rows); `reference_kg_co2eq` is enriched in
  `backend/app/repositories/data_entry_repo.py`.
- **Frontend**: form fields and table columns both come from the same
  `moduleFields[]` per submodule, split by `hideIn: { form, table }` flags
  (`frontend/src/constant/moduleConfig.ts`; `ModuleTable.qCols` filters
  `!hideIn.table`, `SubModuleSection.hasModuleForm` filters `!hideIn.form`).
  **These flags are the knob** for every table-vs-form field decision —
  applied via `withPlannerAdaptations` / config overrides in
  `frontend/src/constant/planner-module-config/module-configs.ts`.
- The reference columns (`reference_kg_co2eq`, `percentage_of_reference_year`
  slider) are **injected** by `ModuleTable.qCols` when
  `show-reference-columns` is set, spliced around `kg_co2eq` — no config
  declares them; they are a pure backend-response contract.
- Factors for planner emissions resolve at the plan's **reference year**,
  not the plan year (`data_entry_emission_service.py`) — a form field whose
  factor doesn't exist for the reference year yields no kg.

### Per-module audit

| Module                                                                            | Backend shape                                                                                                                                                                                             | Frontend today                                                                                                                                                         | Mismatch / decision to record                                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Headcount                                                                         | `{sius_code ∈ SIUS_CODE_VALUES, fte ≥ 0 (> 1 allowed — aggregate), note}` + computed `kg_co2eq`                                                                                                           | `PlannerHeadcountRows.vue` hardcoded SIUS 51–59 grid, single `fte` input, raw `api` calls bypassing the module store                                                   | Surface `kg_co2eq` per row? Expose `note`? Grid vs shared table (F6 overlap). `fte` semantics differ from Calculator (aggregate FTE vs per-person 0–1)                                                                                                                                                                  |
| Purchases                                                                         | `planner_purchase {purchase_category (7 categories), amount_chf ≥ 0, note}`; `planner_purchase_budget {amount_chf, note}` — no category; XOR + one-per-category 422s (`carbon_report_module.py` workflow) | Bespoke `plannerPurchase` config matches the fields                                                                                                                    | `ModuleTable.isComplete` applies **Calculator**-Purchase required fields (`name/quantity/…`) → every planner row renders orange "incomplete" — fix here. Decide columns: category / CHF / kg / note                                                                                                                     |
| Prefilled five (Process Emissions, Buildings, Equipment, Research Fac., Cloud&AI) | Full Calculator DTOs; snapshot rows carry `percentage_of_reference_year` + `source_data_entry_id`; responses add `reference_kg_co2eq`                                                                     | Wholesale Calculator-config clones via `withPlannerAdaptations` — the add-form exposes **every** Calculator field                                                      | Decide per module which fields a _plan_ form/table needs (equipment power/usage, building kWh, cloud currency, …). Reference-column placement falls to the end if `kg_co2eq` isn't a declared field. Buildings: is `building_embodied_energy` (32) snapshotted, and should the planner show it (Calculator FE doesn't)? |
| Travel                                                                            | Unchanged Calculator plane/train DTOs; **no traveler category modeled server-side**                                                                                                                       | Form writes category tokens (`internal` / `external_epfl` / `internal_epfl`) into `user_institutional_id`; `renderCell` resolves `traveler_name` via headcount members | Traveler column **always renders `-`** in the planner. Decide: model categories backend-side (sentinel/enum) vs client-side display mapping. Decide which Calculator fields stay (IATA pair, dates, cabin class, round-trip double-POST)                                                                                |

### Cross-cutting

- [ ] Per-module field matrix (form fields, table columns) decided and
      applied via `hideIn` flags / config overrides
- [ ] `ModuleTable.isComplete` hardcoded per-module required-field lists
      taught the planner types (it throws `Unknown module type` otherwise)
- [ ] Prefill lifecycle audited against the forms: prefill is idempotent per
      data_entry_type (wipes `PLANNER_SNAPSHOT` rows, keeps user-added rows)
      — user rows added through the form must survive a re-prefill
- [ ] Reference-column contract verified per prefilled module
      (`reference_kg_co2eq` present on snapshot rows, slider hidden on
      user-added rows)

## Sub-issue cut

| #   | Sub-issue                                        | Depends on                                                                     |
| --- | ------------------------------------------------ | ------------------------------------------------------------------------------ |
| F1  | Plan Results: per-year footprint chart + totals  | Data-shape audit (above); backend results contract (slice 3, the hard blocker) |
| F2  | PDF export of the plan report                    | F1                                                                             |
| F3  | Shared plans: read-only mode for non-creators    | —                                                                              |
| F4  | Purchases: submodule totals XOR global budget UX | —                                                                              |
| F6  | **Design-alignment refactor** (final)            |                                                                                |

---

## F1 — [FEAT] (Simulation PLAN) Results: per-year footprint chart + totals

### 🎯 Feature Overview (Why?)

A plan currently computes per-year emissions server-side but shows the user
nothing aggregated: no results chart, no totals, and the home planner table's
tCO₂eq column is empty. Per PRD #1555 the planner page must end with a
"**{Project Name} Carbon Footprint**" chart summing all _active_ modules for all
years, so a researcher can read their project's projected footprint at a
glance.

### 🧩 Solution

- Add a results card at the bottom of `ProjectPlannerPage.vue`, mirroring the
  Simulator Explore results card (`SimulationExplorePage.vue`): headline
  `BigNumber` (grand total, tonnes CO₂eq) + chart.
- Chart component: **open — see Clarifications**. Candidates:
  `CompareYearsChart.vue` (#834 per-year stacked bars: `years` = the plan's
  year range, `series` = emission categories with the existing scope colors,
  `dataByYear` = per-year category sums) or `ModuleCarbonFootprintChart.vue`
  (single aggregate category breakdown, as Explore renders). Follows from
  the view-mode decision.
- Data source: `GET /project-plans/{plan_id}/years` already returns each
  plan-year report's persisted `stats` (scope sums + `by_emission_type`
  emission-type-id → kg, aggregated over `is_active` modules only). The raw
  `by_emission_type` map must be reduced to chart categories — **the FE/BE
  contract to pin** (see Clarifications): either the backend adds a
  per-year breakdown in the `emission_breakdown` category shape (preferred,
  keeps the category mapping in `emission_category.py` as the single source
  of truth), or the frontend maps emission-type ids via a documented util.
- Home table totals: extend the plans **list** response with a per-plan
  total server-side, then bind `CO2ProjectPlanner.vue`'s `tco2eq` column.
  Fetching `GET .../years` per listed plan (N+1) is rejected.
- Refetch plan years after an `is_active` toggle so totals/chart track the
  checkbox live (stats already exclude inactive modules server-side).
- **Constraint — validated-only trap:** plan reports are never "validated";
  any reuse of Calculator results endpoints that filter
  `validated_only=True` silently returns zeros (#856 gotcha). The chart must
  read plan stats only through the plan endpoints.

### 📋 Implementation Plan

- [ ] Pin the FE/BE results contract (backend slice 3): per-year category
      breakdown shape on `GET /project-plans/{plan_id}/years` (or documented
      client-side mapping)
- [ ] Results card on `ProjectPlannerPage.vue`: `BigNumber` total + chart
      wired per the decided view mode / chart component
- [ ] Hide the card while no year sections exist; empty-state annotation for
      years whose reference year is unset (zero bar must be distinguishable
      from a genuine 0)
- [ ] Refetch years after `setModuleActive` so chart/totals update live
- [ ] Backend: per-plan total on the plans list response; bind the home
      table `tco2eq` column (`CO2ProjectPlanner.vue`)
- [ ] Locale-aware number formatting (existing `formatNumber` utils)
- [ ] i18n keys (en+fr) for the card title, total label, empty states

### ⚙️ Clarifications Needed

- View mode: expose an option to switch between a **per-year** breakdown and
  a single **global** (whole-plan aggregate) view, or ship only one? If
  per-year is the default, how should a single-year plan render (one lonely
  stacked bar vs a category-breakdown chart)?
- Chart component, following from the view mode: reuse
  `CompareYearsChart.vue` (#834, per-year stacked bars) or
  `ModuleCarbonFootprintChart.vue` (aggregate category bars, the Explore
  pattern)?
- Series granularity: emission **category** (scope colors, like Results) or
  **module**?
- Backend vs frontend aggregation of `by_emission_type` → categories (the
  only hard blocker; backend slice 3 is open).

---

## F2 — [FEAT] (Simulation PLAN) Export PDF report

### 🎯 Feature Overview (Why?)

PRD #1555 requires an exportable report: a researcher attaches the plan's
projected footprint to a grant application. The app already has a print-page
pattern (Explore, Results, Backoffice reporting); the planner needs its own.

### 🧩 Solution

- New print route + page `ProjectPlannerPrintPage.vue` and composable
  `usePlannerPrintData.ts`, following the existing pattern:
  `SimulationExplorePrintPage.vue`, shared `ReportPage.vue` wrapper,
  `src/composables/print/` (`usePrintMode` waits for charts before
  `window.print()`).
- "Download report" button in the F1 results card opens the print route in a
  new tab (`router.resolve(...).href` + `window.open`), like Explore's
  `downloadReport()`.
- Report composition: cover/summary page (project info, year range,
  reference years, grand total, footprint chart) + one `ReportPage` per year
  with that year's module totals.

### 📋 Implementation Plan

- [ ] Print route (own layout, `breadcrumb: false`) resolving the plan by
      the `:name` param (URL-encoded; `getPlanByName` already
      `encodeURIComponent`s)
- [ ] `usePlannerPrintData.ts` — fetch plan + years + breakdown once, no
      interactive state
- [ ] `ProjectPlannerPrintPage.vue` — summary page + per-year pages via
      `ReportPage`
- [ ] Charts render fully before print (`usePrintMode` pattern)
- [ ] Download button in the results card
- [ ] Zero-data plan still exports a valid skeleton report
- [ ] Print page reachable for shared-plan viewers (read-only is fine —
      export is a read)

### ⚙️ Clarifications Needed

- Per-year detail depth: module totals only, or full entry tables?

---

## F3 — [FEAT] (Simulation PLAN) Shared plans: read-only mode for non-creators

### 🎯 Feature Overview (Why?)

A plan with `is_viewable_by_unit_members = true` is visible to unit members
but **read-only for non-creators** — only the creator (or backoffice)
mutates (backend-enforced, decided with product 2026-07-15). The UI currently
renders full edit controls for everyone; a non-creator's first write returns
403, and the global `http.ts` 403 → `/unauthorized` redirect (#1596) fires
before any local catch — **killing the whole page**. UI gating is therefore
correctness, not polish.

### 🧩 Solution

- `isReadOnly = plan.created_by !== authStore.user.id` (backoffice exception
  per clarification), computed once on `ProjectPlannerPage` and passed down
  as a single `readonly` prop: `PlannerProjectInfo` (name, year selects,
  Generate years, visibility checkbox), `PlannerYearSection` (reference-year
  select, Active checkboxes), and into `ModuleTableSection` /
  `PlannerHeadcountRows` — reusing the `:disable` plumbing that already
  exists for inactive modules (tables, forms, sliders, row actions).
- Auto-save-on-blur handlers in `PlannerProjectInfo` must be **inert** when
  readonly, not just visually disabled — a blur on a styled-but-live field
  would still fire the PATCH and trigger the 403 redirect.
- Banner on the plan page: "Shared by {creator_name} — read-only"
  (`creator_name` is already on the DTO).
- Home table (`CO2ProjectPlanner.vue`): hide rename/delete actions on rows
  the user does not own; duplicate per clarification below.
- Direct URL to an **unshared** plan by a non-creator: backend returns 403 —
  catch it (`skipErrorCodes: [403]` on `getPlanByName`, alongside the
  existing 404 skip) and render the existing `notFound` card instead of the
  global redirect. Same handling covers "creator un-shares while a viewer
  has the page open" (next refetch 403s) and rename-while-viewing (404 →
  `notFound`, already handled).

### 📋 Implementation Plan

- [ ] `isReadOnly` computed on `ProjectPlannerPage`, threaded as one prop
- [ ] `PlannerProjectInfo`: inputs readonly **and** save handlers inert
- [ ] `PlannerYearSection`: reference-year select + Active checkboxes
      disabled; tables/forms/sliders/row actions disabled via existing
      `:disable` path
- [ ] Read-only banner with creator name
- [ ] Home table: gate rename/delete (and duplicate, per clarification) by
      ownership
- [ ] 403 on `getPlanByName` → `notFound` card, not the global redirect
- [ ] `created_by: null` legacy plans: fallback rule per clarification
- [ ] Verify zero write requests are fired in read-only mode (network log)

### ⚙️ Clarifications Needed

- May a non-creator **duplicate** a shared plan (becoming owner of the
  copy)? Does the backend allow it today?
- Backoffice/global roles: full edit rights in this UI, or read-only too?
- `created_by: null` (pre-migration plans): editable by whole unit, or
  locked?
- Should shared (non-owned) plans be visually distinguished in the home
  table (icon/section)?

---

## F4 — [FEAT] (Simulation PLAN) Purchases: submodule totals XOR global budget UX

### 🎯 Feature Overview (Why?)

PRD #1555: "Either the submodule totals OR the Global budget must be
filled." The backend enforces the XOR and the one-entry-per-category rule at
creation (422 codes, `planner_purchase` = 81 / `planner_purchase_budget` =
82), but the UI shows both submodules side by side with no exclusivity
affordance — the user discovers the rule only via a raw error.

**Design ↔ implementation divergence.** The PRD/design screenshot shows the
submodule totals table and the Global budget field _side by side_, as if
both can be filled together — but the backend is XOR, so that layout
actively misleads. Mechanically disabling one half whenever the other holds
data makes the screen read as broken, not as a designed either/or. Properly
expressing the XOR needs a **reworked design / new UI frame** for the
Purchases section, decided with product/design — not bolted onto the
existing side-by-side layout. That design rework is the gating decision for
this feature; the items below are the interaction requirements it must
satisfy plus a candidate approach, not a settled UI.

### 🧩 Solution

> **Blocked on a design rework** (see Overview): the side-by-side layout and
> the XOR backend diverge, so the section needs a new design frame before
> this UX is built. Park the design decision for product/design per the
> guardrails. The items below are the
> requirements that frame must satisfy plus a candidate mechanical approach,
> not a settled UI.

- In the planner Purchases module (bespoke `plannerPurchase` config,
  `planner-module-config/module-configs.ts`): the two modes (per-category
  submodule totals vs global budget) must be a **visible, explicit
  either/or** — the reworked design decides the affordance (e.g. a segmented
  control / mode toggle) rather than leaving the user to infer the rule from
  greyed-out fields.
- Candidate mechanical fallback if the design keeps the current layout: when
  a global-budget entry exists, disable the per-submodule table/form with an
  explanatory hint — and vice-versa. Deleting the blocking entry re-enables
  the other mode without reload (both submodules' data live in the same
  module fetch).
- Map the backend 422 error codes to i18n messages (en+fr) surfaced inline
  on the form, not as a raw-JSON toast — covers the race where two tabs
  create a budget and a submodule row concurrently (the second gets the
  server 422 despite UI gating).
- One-entry-per-category duplicate rule surfaced inline on the category
  select (disable already-used categories or map the 422).
- Missing-factor display: entries carry no kg CO₂eq until the average-EF
  factor rows are uploaded (data concern, not code) — show an em-dash or
  explanatory tooltip instead of a misleading hard `0`.
- Guard: reference-kg column and % slider must never appear for Purchases
  (manual type — no snapshot rows).

### 📋 Implementation Plan

- [ ] **Design rework decided with product/design first** — a Purchases UI
      that expresses the XOR as an explicit either/or (mode affordance);
      gates the items below
- [ ] Mutual-exclusion state derived from the module's entries; disable the
      opposite mode's form/table with hint
- [ ] Re-enable on deletion of the blocking entry (no reload)
- [ ] Enumerate the backend 422 codes from `modules_planner/purchase` and
      map each to an i18n message (en+fr), rendered inline
- [ ] Duplicate-category rule surfaced on the category select
- [ ] Missing-factor kg display convention (— / tooltip) per clarification
- [ ] Amount edited to 0 still counts as "filled" (blocks the other mode) —
      deleting is the way to switch modes; hint says so
- [ ] Verify no reference columns/slider render for Purchases

### ⚙️ Clarifications Needed

- **Design rework (hard blocker)**: the side-by-side design and the XOR
  backend diverge — a new/reworked Purchases design that expresses the
  either/or (mode affordance) is needed before the UX is built. Owned by
  product/design; gates the items below.
- Exact 422 error-code list (enumerate from
  `backend/app/modules_planner/purchase/` in review).
- Missing-factor kg: `—` vs `0` + tooltip?
- Switching modes: require explicit deletion (recommended, matches backend),
  or offer a "switch to global budget" action that deletes for you (needs
  confirm)?

---

## F6 — [REFACTOR] (Simulation PLAN) Design-alignment refactor of the planner UI (final)

### 🎯 Feature Overview (Why?)

The first planner cut was built fast and diverges from the app's visual and
architectural conventions — most visibly from the Simulator **Explore** page
(`SimulationExplorePage.vue`), which the planner should feel like a sibling
of. This issue de-vibecodes the planner: same look, same shared components,
same store plumbing as the rest of the app. **Explicitly
behavior-preserving** — F5's suite must pass unchanged.

### 🧩 Solution

Known divergences to fix:

- **Accent color**: planner cards use ad-hoc `color="negative"` (red) on the
  title icon, reference-year icon, and Active checkbox; Explore and the home
  planner section use `info`. Pick one planner accent (`info`) and apply it
  consistently.
- **Page grammar**: adopt Explore's structure — title box (`q-card flat
class="container"`, 32px icon, `text-h2`/`text-body1`), module list as one
  bordered card with `q-expansion-item`s separated by `q-separator`, module
  headers with `ModuleIconBox`, results card last. Use `.container` /
  `page-grid` / `src/css/02-tokens` spacing instead of ad-hoc padding.
- **`PlannerHeadcountRows.vue`**: replace the hand-rolled `v-for` div-grid
  (inline `style="max-width: 180px"`) and its direct `api.get/post/patch`
  calls with the shared table/form path, routing data through the module
  store like every other module.
- **Year-section behavior**: decide all-open year sections + page-wide
  single-open module accordion (current) vs single-open year accordion
  (original #1557 decision). Either way, document the constraint the
  accordion protects: `state.dataSubmodule` is keyed by submodule id only
  (`stores/modules.ts` ~L368) — two simultaneously open instances of the
  same submodule in different years would collide. Re-keying
  `${year}:${id}` stays deferred to the ModuleTable decomposition track
  (#1827).
- **Destructive range shrink**: confirm dialog before "Generate years" when
  the new range drops existing years (backend deletes their reports +
  entries by design) — reuse the `common_delete_dialog_*` i18n pattern.
  Currently silent data loss.
- **Unit switch mid-page**: workspace unit change leaves the page showing
  another unit's plan — redirect home (same handling as Explore).
- **States & polish**: skeletons while `planYearsLoading`
  (`ChartSkeleton`/`ChartEmptyState` for the results card), empty states,
  i18n audit (currently clean — keep zero raw user-facing strings),
  responsiveness pass per #21 (year sections, sliders, purchase forms, home
  table on small screens).

### 🎨 Design

[Figma proto](https://www.figma.com/proto/DXeFrKiXUpqCHUEgXVROng/200_Calculateur-CO2?node-id=4109-47273&starting-point-node-id=4109%3A47273&show-proto-sidebar=1&t=zTVvjLO31Fs0WlI9-1)
(approximate) + `SimulationExplorePage.vue` as the living reference.

### 📋 Implementation Plan

- [ ] Single planner accent (`info`) across title, reference-year, Active
      checkbox, home section
- [ ] Planner page restructured to Explore's grammar (title box, module list
      card + `ModuleIconBox` headers, results card, `.container`/tokens)
- [ ] `PlannerHeadcountRows` → shared table/form + module store
- [ ] Year-section accordion decision implemented + `dataSubmodule` keying
      constraint documented in code
- [ ] Loading skeletons + empty states
- [ ] Responsiveness pass (#21) on planner page, year sections, home table
- [ ] i18n audit

### ⚙️ Clarifications Needed

- Extract a shared `PageTitleBox` component (Explore, Planner, Home repeat
  the same inline title-box pattern today), or keep the pattern inline?
- Is a final Figma design coming, or is the approximate proto the reference
  to match?
- Year sections: all-open (current) or single-open accordion (original
  decision)? Product call on the reading experience for long ranges.

---
