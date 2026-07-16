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
"Percentage of last year" labels are both wrong. The backend JSON key was renamed
`percentage_of_last_year` → `percentage_of_reference_year` (done
2026-07-16); it computes against `report.reference_year` and preserves the
Calculator year-1 fallback in `_get_percentage_override_kg`.

**Decisions (2026-07-16):**

- **Extend the shared table, don't fork it.** Prefilled rows stay fully
  editable (gas/subcategory selects) and gain two columns: reference
  kgCO₂eq + a **0–200%** "% of reference year" slider. Planner and
  Calculator render through the _same_ table.
- **Prerequisite refactor:** `ModuleTable.vue` is 1889 lines — over the
  repo's 500-line component limit. Decompose it via composition FIRST,
  then the planner columns slot in as a small, clean addition.
- Type-2 rows **are the prefill copies of the reference-year data
  entries** (each carries `source_data_entry_id`), so the reference-kg
  column is the source entry's value — no separate reference fetch.
- Slider PATCHes `percentage_of_reference_year` (renamed key) on the
  row's entry; the backend override recomputes `kg_co2eq = source × %`.

**`ModuleTable.vue` decomposition (target < 500 lines each):** extract
cohesive clusters, verifying the Calculator table renders after each step:

- `useModuleTableColumns` — `qCols`, `getColumn*`, numeric rules.
- `useInlineCellEditing` — `commitInline`, `inlineErrors`,
  `setError`/`getError`, `renderCell`, usage-hours/trips validators.
- `useModuleNoteDialog` + `ModuleNoteDialog.vue` — note add/edit/delete.
- `ModuleEditDialog.vue`, `ModuleCsvUploadDialog.vue`,
  `ModulePowerFeedbackDialog.vue` — dialog templates + their state.
- Core `ModuleTable.vue` keeps the `q-table` + slot wiring only.

**Reference-kg backend field:** add `reference_kg_co2eq` to the submodule
item — sum the `source_data_entry_id` entry's emissions
(`_sum_entry_emissions`) for snapshot rows; scope to plan reports (one
extra query per snapshot row on GET). Deriving `kg / (pct/100)`
client-side is rejected (breaks at 0% and after reload).

**Add form:** the extended shared table already carries the module's
add-form — no separate planner form.

**Steps**

- [ ] Refactor `ModuleTable.vue` to < 500 lines (composables +
      sub-components above); Calculator verified unbroken after each step.
- [ ] Backend: `reference_kg_co2eq` on the planner submodule item.
- [ ] Add the reference-kg column + 0–200% slider to the shared table,
      shown only in planner (prefilled) context.
- [ ] Planner renders prefilled modules through the shared table.
- [ ] Verify: prefill → slider 40% → kg = 40% of reference; edit + add row.

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
