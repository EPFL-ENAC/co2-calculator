---
status: delivered
issue: 1557
last_updated: 2026-07-23
title: "Simulator Plan — frontend follow-ups"
summary: "Four planner-frontend pieces: the type-2 prefilled slider table (delivered; ModuleTable decomposition deferred to its own plan), the wrong-plan report resolution fix (delivered; overlapping-plans regression test outstanding), dropdowns resolving factors from the plan year instead of the reference year (delivered), and the Comment button disabled by the Calculator's validated state (delivered)."
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
  kgCO₂eq + a "% of reference year" slider. Planner and Calculator render
  through the _same_ table.
- **Range narrowed 0–200% → 0–100%, and the value is typeable**
  (2026-07-22, superseding the original 0–200 decision): the slider caps at
  100%, and the value beside it is an editable field that drives the slider,
  capped to the same range on commit (`utils/reference-percentage.ts`) since
  `<input type="number" max>` does not stop a pasted value. **A plan can no
  longer model growth above the reference year** — see the open question
  below.
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
- [x] Cap the slider at 100% and make the value typeable (0–100 on commit),
      pinned in `tests/unit/reference-percentage.spec.ts`.
- [x] Slider and field share one uncommitted draft per row, so the number
      follows the handle mid-drag and typing moves the handle. QSlider emits
      `update:modelValue` throughout the drag and `change` only on release
      (`use-slider.js::updateValue`), so the PATCH still fires once. The
      field commits on blur/Enter; QInput emits the **value**, not a native
      `Event` — reading `event.target.value` threw
      `Cannot read properties of undefined`.
- [ ] **Open (needs a decision):** the cap is UI-only. The backend still
      takes `percentage_of_reference_year: Optional[float]` unbounded, and
      **rows already stored above 100%** from the 0–200 era keep their value
      — the slider renders them pinned at its max while the stored figure
      (and the kg it produces) stays higher, which reads as a wrong total.
      Either bound the DTO and migrate those rows down, or keep the backend
      open and treat the cap as guidance. Not decided unilaterally: it
      migrates plan data.

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

## C. Dropdowns resolved factors from the plan year

**Defect:** the backend resolves a plan entry's factors from the plan-year
report's `reference_year`
(`DataEntryEmissionService._get_year_from_data_entry`, and the same rule in
`modules/professional_travel/handlers.py`). The frontend did not:
`PlannerYearSection` passed `yearData.year` down the
`ModuleTableSection → SubModuleSection → ModuleTable` chain into
`useEquipmentClassOptions` / `useBuildingRoomDynamicOptions`, which is what
reaches `factors/{sub}/class-subclass-map?year=` and `.../values?year=`.
`FactorRepo.get_class_subclass_map` filters `Factor.year == year` exactly,
so a 2030 section asked for 2030 factors: **empty class/subclass dropdowns**
where that year has none (silently — the composable catches into `[]`), and
where it does have some, **options and seeded factor values from a year the
emission is never computed with** (`active_power_w`, the buildings kWh/m²
defaults). Prefilled snapshot rows are unaffected: they scale
`source_data_entry_id` by `percentage_of_reference_year` and never resolve a
factor.

**Fix — carry the factor year explicitly** (delivered 2026-07-22): a
`factorYear` prop threads the plan year's `reference_year` down the same
chain, alongside `year` (which stays the entry's own year — it addresses the
row for PATCH and bounds the date pickers). The two components share
`utils/factor-year.ts::resolveFactorYear`:

- `undefined` — Calculator, no reference year exists, the entry's `year` is
  the factor year;
- `null` — a plan year with **no reference year picked yet**: nothing is
  fetched. No fallback to the plan year, since the backend would not use it
  either.

**Steps**

- [x] `resolveFactorYear` + `tests/unit/factor-year.spec.ts` pinning all
      three cases.
- [x] `factorYear` threaded through the shared table chain; `ModuleForm` and
      `ModuleInlineSelect` feed it to both factor composables.
- [x] `PlannerYearSection` passes `yearData.reference_year`.
- [x] Verified in a browser: a plan year offers its reference year's classes.

**Two defects found in that verification** (fixed 2026-07-22):

- **Changing the reference year needed a page reload.**
  `useEquipmentClassOptions` loads its options once per mount — it watches the
  submodule and the selected class, never the year — so a changed
  `factorYear` prop never refetched. `PlannerYearSection` now keys the table
  on `factorMountKey(module, reference_year)`, remounting it when the
  reference year changes. No cache invalidation is needed alongside it: the
  factors store is keyed `(submodule, year)`, so the new reference year is a
  new key rather than a stale hit.
- **Modules were enterable with no reference year set.** The drawers resolved
  against nothing — empty dropdowns explained only by the hint at the top of
  the year card. The per-module `q-expansion-item` is now disabled until a
  reference year exists, and `planner_reference_year_hint` says so (both
  locales).

**Steps**

- [x] Remount the planner table on reference-year change (`factorMountKey`,
      pinned in `tests/unit/factor-year.spec.ts`).
- [x] Disable the module drawers until a reference year is set; extend the
      hint copy.

## D. The Comment button was disabled in the Planner

**Defect:** the per-row Comment button was greyed out on Planner tables while
every other control in the same table (inline edits, delete, the % slider)
stayed live. `ModuleTable.vue` held two twin computeds: `isDisabled` already
carved the Planner out of the Calculator's validated lock
(`props.carbonReportId != null` — see A), `isNoteDisabled` did not and still
read `timelineStore.itemStates[moduleType] === Validated`. The workspace guard
(`router/guards/workspaceGuard.ts`) fills that store with the **Calculator**
module statuses of the selected workspace year on every workspace route, so a
module validated in the Calculator disabled comments on every plan year of every
plan — plan reports are never validated and have no lock of their own.

**Fix (2026-07-23):** both rules moved to `utils/module-table-access.ts`
(`isModuleTableDisabled` / `isModuleNoteDisabled`), which names the three
contexts a table renders in — Calculator, Explorer, Planner. Notes are blocked
by the validated lock in the Calculator only; in the Explorer and the Planner
they need `canEdit` alone. `canEdit` stays a condition everywhere: the backend
gates the underlying PATCH with `check_module_permission_for_unit("edit")`, and
`api/http.ts` turns that 403 into a whole-page `/unauthorized` redirect.

The ambiguous `isSimulator` prop (set only by `SimulationExplorePage`) is
renamed `isExplorer` through `SubModuleSection → ModuleTable`; the Planner is
identified by `carbonReportId`, which the Calculator never passes.

**Steps**

- [x] Extract `isModuleTableDisabled` / `isModuleNoteDisabled` into
      `utils/module-table-access.ts`; both `ModuleTable` computeds delegate.
- [x] Regression: `tests/unit/module-table-access.spec.ts` pins the Planner +
      validated-Calculator-module case, plus the Calculator and permission cases.
- [x] Rename `isSimulator` → `isExplorer`.
