---
status: in-progress
issue: 1557
last_updated: 2026-07-16
title: "Simulator Plan — frontend follow-ups"
summary: "Two planner-frontend pieces: the type-2 prefilled slider table (delivered; ModuleTable decomposition deferred to its own plan) and the wrong-plan report resolution fix (delivered; overlapping-plans regression test outstanding)."
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
- **Decomposition reordered** (2026-07-16): the planner columns landed
  first in the existing file; the `ModuleTable.vue` decomposition (~2020
  lines vs the 500-line limit) is deferred to its own plan,
  [1557-moduletable-decomposition.md](1557-moduletable-decomposition.md).
- Type-2 rows **are the prefill copies of the reference-year data
  entries** (each carries `source_data_entry_id`), so the reference-kg
  column is the source entry's value — no separate reference fetch.
- Slider PATCHes `percentage_of_reference_year` (renamed key) on the
  row's entry; the backend override recomputes `kg_co2eq = source × %`.

**`ModuleTable.vue` decomposition:** fleshed out into its own ordered plan —
see [1557-moduletable-decomposition.md](1557-moduletable-decomposition.md).

**Reference-kg backend field:** add `reference_kg_co2eq` to the submodule
item — sum the `source_data_entry_id` entry's emissions
(`_sum_entry_emissions`) for snapshot rows; scope to plan reports (one
extra query per snapshot row on GET). Deriving `kg / (pct/100)`
client-side is rejected (breaks at 0% and after reload).

**Add form:** the extended shared table already carries the module's
add-form — no separate planner form.

**Steps**

- [ ] Refactor `ModuleTable.vue` to < 500 lines — deferred to
      [1557-moduletable-decomposition.md](1557-moduletable-decomposition.md)
      (reordered: the columns shipped first).
- [x] Backend: `reference_kg_co2eq` on the planner submodule item.
- [x] Add the reference-kg column + 0–200% slider to the shared table,
      shown only in planner (prefilled) context.
- [x] Planner renders prefilled modules through the shared table; setting a
      section's reference year auto-prefills every prefilled module, and
      prefilled tables no longer lock on the Calculator's validated state.
- [x] Verify: prefill → slider 40% → kg = 40% of reference; edit + add row.

## B. Wrong-plan report resolution (overlapping-year plans)

**Defect:** `stores/modules.ts::resolveCarbonReportId` resolves the planner
case (`carbonProjectType === 2`) through a **year-keyed global map**
(`plannerReportIdsByYear`) that the last `fetchPlanYears` populated. A unit
can hold several plans with overlapping years, so switching plans (or a
module call racing a `fetchPlanYears` refetch) resolves a **year to the
wrong plan's report id** — the operation lands on another plan — or throws
`No plan-year report registered for year X` before the map is populated.

**Fix — pass the report id, never re-derive it** (delivered 2026-07-16,
shape differs slightly from the original spec): instead of by-report sibling
fetchers, `stores/modules.ts::modulePath` grew an optional trailing
`carbonReportId` param that short-circuits straight to
`buildModulePath(moduleType, carbonReportId)`. Planner components pass
`yearData.id` through it; a planner call (`carbonProjectType === 2`) that
omits the id **throws** — no silent fallback to the Calculator report.
`plannerReportIdsByYear`, `setPlannerReportIds`, and the type-2 branch in
`resolveCarbonReportId` are deleted.

**Steps**

- [x] Planner module calls address reports by id (`modulePath` optional
      `carbonReportId` + fail-loud guard).
- [x] Planner components pass `yearData.id`; drop the year→id map + branch.
- [ ] Regression: two same-unit plans with overlapping years, edit each,
      confirm entries land on the addressed report only.
