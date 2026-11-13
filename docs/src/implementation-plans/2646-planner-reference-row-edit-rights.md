---
status: in-progress
issue: 2646
last_updated: 2026-11-13
title: "Planner: a row with a slider keeps only its percentage and its note editable"
summary: "A Simulator Plan row copied from the reference year is priced as reference kgCO2eq times its percentage. An edit to its own fields changed the cell and never the result. Such a row now resolves to a third data-entry branch, reference. Only percentage_of_reference_year and the note are writable there. The row stays deletable. The prefill matrix in the product owner's sheet already matches the code and does not change."
---

# Planner: edit rights on rows with a slider (#2646)

Follow-up to [#951](951-edit-rights-per-dataset-permissions.md), for the
Simulator Plan tables.

## Problem

A reference row is a plan row that the prefill copied from the reference year.
It shows the "% of reference year" slider. Its emissions are the reference
row's kgCO2eq multiplied by that percentage
(`DataEntryEmissionService._get_percentage_override_kg`). The row's own fields
never reach the result.

#951 put every planner snapshot row in the `user` branch. A reference row
therefore inherited the `user` whitelist of its module. On Process Emissions
that whitelist is the gas, the sub-category and the quantity. The user typed a
new quantity, the cell kept the new value, and the kgCO2eq column did not
move. The table showed a quantity that the total did not count.

## What the product owner's sheet says

The product owner answered the issue with a sheet, "Import of data from the
CO2 calculator section based on modules, workspaces, and user roles". The
sheet states which modules receive calculator rows, per workspace and per
role.

| Module                 | Grant proposal | Detailed per year | Explorer |
| ---------------------- | -------------- | ----------------- | -------- |
| Headcount              | no             | yes               | no       |
| Process emissions      | yes            | yes               | no       |
| Buildings              | yes            | yes               | no       |
| Equipment              | yes            | yes               | no       |
| External clouds and AI | yes            | yes               | no       |
| Professional travel    | no             | yes               | no       |
| Purchases              | no             | no                | no       |
| Research facilities    | no             | yes               | no       |

The columns above are for a principal user. A standard user receives no
calculator rows in any workspace.

The code already does this. No prefill change is part of this plan.

- `PLANNER_PREFILLED_MODULE_TYPES` and `PLANNER_PLAIN_COPY_MODULE_TYPES`
  (`backend/app/models/module_type.py`) give the "Detailed per year" column.
  Purchases are in neither set.
- `SimulatorPlanService._prefill_reference_modules` leaves headcount,
  professional travel and research facilities out of a grant report.
- For a standard user, `_plan_creator_has_baseline_access` skips the copy on
  year reports, and `_hide_planner_snapshots_for_viewer` hides the copied rows
  of a grant report at read time.
- `CarbonReportService.create_explore` makes an empty sandbox with no
  reference year.

The sheet says where calculator rows arrive. It does not say what a user can
edit on them. That part is the decision below.

## Decision

On a reference row, only the percentage and the note are writable. The rule
is the same in every module.

This follows the issue title ("probably disable edit lines"). The other
option in the issue was to let an edit replace the reference calculation. That
option needs a new product rule. The rule must say at which point a row stops
to follow its reference year. Nobody wrote it.

The product owner did not confirm this decision in writing. The plan stays
`in-progress` until they do.

## Changes

### Backend

`backend/app/core/data_entry_permissions.py`:

- `Provenance` gains `REFERENCE`. `provenance_of(source, data)` returns it
  for a `PLANNER_SNAPSHOT` row whose persisted `data` carries a
  `percentage_of_reference_year`. This is the same condition that makes the
  emission compute price the row from the reference year.
- `REFERENCE_WRITABLE_FIELDS` holds the percentage. It replaces
  `PLANNER_SNAPSHOT_WRITABLE_FIELDS`, which granted the percentage on top of
  the `user` whitelist. The rule is module-independent, so it is not a row of
  the `PERMISSIONS` matrix.
- `can_delete` is true for `REFERENCE`. `can_create` is false, because only
  the prefill writes these rows.
- `clears_reference_percentage` refuses a `null` percentage on a reference
  row. Without the percentage the row reads as a plain copy, which is
  `user`. Without this refusal, two API calls undo the lock.
- `submodule_policies` ships the third branch as
  `data_entry_policies.reference`.

`CarbonReportModuleWorkflow.update` and `.delete` pass the persisted `data`
to `provenance_of`. The refusal is the existing 403 `FIELD_NOT_EDITABLE`.

### Frontend

- `utils/dataEntryPolicy.ts`: `branchOf` takes the row and returns
  `reference` for `source === 6` with a percentage. `isFieldEditable` and
  `isRowDeletable` take the row too.
- `ModuleTable.vue` passes `source` and `percentage_of_reference_year` of the
  row. The inline cells of a reference row render as the read-only cells that
  #951 already uses. The slider and the note button do not change.
- `types/api/openapi.d.ts` is regenerated for the new branch.

## What is deliberately not changed

- A reference row stays deletable. A deleted row counts the same as a row at
  0%, and the plan is the user's own scenario.
- A row that the user adds in a plan table is a `user` row. It keeps the #951
  whitelist, because its emissions come from its own fields.
- Professional travel rows are plain copies with no percentage (#2018). They
  stay `user` and editable. The percentage is no longer writable on them,
  because they have no reference row to scale.
- Headcount and purchases use planner-kind types. They are exempt from this
  layer and render in their own grids.
- The equipment aggregate lines of the global mode (#2749) are written by
  `CarbonReportModuleService`, not through the update workflow.

## Known limit

If someone deletes the source row in the calculator, the reference row keeps
its percentage. The emission compute then prices the row from its stored
fields, and the table shows no slider for it. With this change the row is
read-only. The user can delete it, or set the reference year again to rebuild
the module.

## Tests

- `backend/tests/unit/core/test_data_entry_permissions.py`: `provenance_of`
  for a per-line copy, an aggregate line, a plain copy and a manual row with
  a stray percentage. The writable set of the branch for six submodules. The
  `reference` branch in the submodule payload.
- `backend/tests/unit/workflows/test_carbon_report_module_permissions.py`:
  a PATCH of `sub_class` on a reference row is 403 (the regression, red before
  this change). The percentage and the note save. A `null` percentage is 403.
  A plain copy keeps its own fields editable and refuses the percentage. A
  reference row deletes.
- `frontend/tests/unit/dataEntryPolicy.spec.ts`: `branchOf` for the same
  cases, with 0% as a percentage. A reference row locks `sub_class` and keeps
  the percentage and the note.
