---
status: proposed
issue: 1557
last_updated: 2026-07-16
title: "Simulator Plan — frontend follow-ups"
summary: "Two remaining planner-frontend pieces that need the running app to verify: the type-2 prefilled slider table, and fixing the wrong-plan report resolution for units with overlapping-year plans."
---

# Simulator Plan — frontend follow-ups

Follow-ups to the planner UI (PR #1816 / [#1556](1556-simulation-plan-backend.md)).
Both need a browser + a seeded test-user unit to verify, so they are
specified here for review before implementation rather than landed blind.

## A. Type-2 prefilled slider table

**Goal (design):** for prefilled modules (Process Emissions, Buildings,
Equipments, Research Facilities, External Clouds & AI) each snapshot row
shows its Calculator key fields plus three planner columns — **Reference
year kgCO₂eq**, current **kgCO₂eq**, and a **"% of reference year" slider**
— with an "Add …" form below.

Terminology (confirmed with PO/PM 2026-07-16): it is the **reference year**,
not "last year", and the unit is **kgCO₂eq** — the mockup's "tco2eq" and
"Percentage of last year" labels are both wrong. The backend JSON key is
still `percentage_of_last_year` (legacy Calculator name; already computes
against `report.reference_year`); rename it to
`percentage_of_reference_year` as a small standalone follow-up (planner-only
key, no production data, but `_get_percentage_override_kg` keeps a Calculator
year-1 fallback to preserve — do it deliberately, not as a blind sed).

**Component:** `PlannerPrefilledTable.vue`, rendered by `PlannerYearSection`
for `behavior === 'prefilled'` modules (replacing the generic
`ModuleTableSection` for those). Props: `carbonReportId` (the plan-year
report id), `moduleType`, `disable`, and the submodule list from
`getPlannerModuleConfig`.

**Rows:** fetch each submodule via
`carbon-reports/{reportId}/modules/{module}/{submodule}`. Each item's `data`
already carries `percentage_of_last_year`, `kg_co2eq`, and
`source_data_entry_id` (spread by the handler `to_response`). Display the
module's key fields read-only-ish (from the module's `moduleFields`).

**"Reference year kgCO₂eq":** NOT in the submodule response today. Two options —

- **(recommended) backend:** add `reference_kg_co2eq` to the planner
  submodule item — sum the `source_data_entry_id` entry's emissions
  (`_sum_entry_emissions`) when the row has one. One extra query per snapshot
  row on GET; scope it to plan reports only. Correct and reload-stable.
- (rejected) derive client-side `last = kg / (pct/100)` — breaks at
  `pct = 0` and after a reload where only `kg` is known.

**Slider:** q-slider 0–100 (confirm max with product; PRD says "% of each
data entry"), bound to the row's `percentage_of_last_year`, debounced PATCH
to `carbon-reports/{reportId}/modules/{module}/{submodule}/{itemId}` with
`{percentage_of_last_year}`; on success refetch the row so `kg_co2eq`
reflects the recompute (backend already honours the override —
`_get_percentage_override_kg`).

**Add form:** reuse the Calculator `SubModuleSection` add-form for the
module (it already builds the correct fields and POSTs through the identity
route with CSV upload disabled via `configOverride`), OR a compact
planner-only add form. **Decision needed** — leaning on reusing
`SubModuleSection`'s form only (not its table) to avoid a second field
definition.

**Steps**

- [ ] Backend: `reference_kg_co2eq` on the planner submodule item.
- [ ] `PlannerPrefilledTable.vue` (rows + 3 columns + slider + add form).
- [ ] Wire into `PlannerYearSection` for prefilled modules.
- [ ] Verify end-to-end (prefill → slider 40% → kg halves-to-40%; add row).

## B. Wrong-plan report resolution (overlapping-year plans)

**Defect:** `stores/modules.ts::resolveCarbonReportId` resolves the planner
case (`carbonProjectType === 2`) through a **year-keyed global map**
(`plannerReportIdsByYear`) that the last `fetchPlanYears` populated. A unit
can hold several plans with overlapping years, so switching plans (or a
module call racing a `fetchPlanYears` refetch) resolves a **year to the
wrong plan's report id** — the operation lands on another plan — or throws
`No plan-year report registered for year X` before the map is populated.

**Fix — pass the report id, never re-derive it.** The planner already holds
`yearData.id` (the plan-year report id) per section. Give planner module
calls the report id directly instead of routing unit/year through the store
map:

- Add `getModuleTotalsByReport(moduleType, carbonReportId)` (and any sibling
  fetchers the planner uses) that call `buildModulePath(moduleType,
carbonReportId)` with no resolution step.
- `PlannerYearSection` / `PlannerPrefilledTable` call the by-report variants
  with `yearData.id`.
- Delete `plannerReportIdsByYear`, `setPlannerReportIds`, and the
  `carbonProjectType === 2` branch in `resolveCarbonReportId` (they exist
  only to work around not having the id at the call site) — also a ponytail
  win.

**Steps**

- [ ] `getModuleTotalsByReport` (+ submodule/data-entry variants as needed).
- [ ] Planner components pass `yearData.id`; drop the year→id map + branch.
- [ ] Regression: two same-unit plans with overlapping years, edit each,
      confirm entries land on the addressed report only.
