---
status: delivered
issue: 2176
last_updated: 2026-08-19
summary: Planner "% of reference year" slider PATCHes 403'd under the #951 field whitelist; planner snapshot rows now additionally own percentage_of_reference_year, and http.ts no longer redirects to /unauthorized on object-shaped (row-level) 403 details.
---

# 2176 — (planner) Error 403 on usage update

## Problem

Since #951 (PR #2106, provenance-keyed data-entry field permissions), moving
the "% of reference year" slider in any prefilled Project Planner module
(Equipment, Local/rooms, …) returned `403 FIELD_NOT_EDITABLE` on every
change, and the global 403 hook then hard-redirected the user to
`/unauthorized`.

## Root cause

Two independent defects stacked:

1. **Backend.** The slider sends the generic data-entry
   `PATCH …/modules/{module}/{submodule}/{item_id}` with
   `{percentage_of_reference_year}`. Planner-prefilled rows reuse
   _calculator_ data-entry types (< 80), so `is_policy_exempt()` does not
   exempt them; the #951 review fix only mapped their `PLANNER_SNAPSHOT`
   source to the USER provenance branch. The USER whitelists come verbatim
   from the #951 issue matrix, which never mentions
   `percentage_of_reference_year` — the field is planner-only and not a DTO
   field on any module (it rides through `DataEntryUpdate.unflatten_payload`
   into `data`). Every actual slider change therefore diffed as a locked
   field. Planner headcount kept working because `planner_headcount` (≥ 80)
   is type-exempt.
2. **Frontend.** `http.ts`'s 403 hook assumed `detail` is a string;
   `FIELD_NOT_EDITABLE` sends `{code, fields}`, so `.match` threw, was
   swallowed, and the hook redirected to `/unauthorized` — evicting the user
   from the planner for a row-level denial.

## Fix

- `backend/app/core/data_entry_permissions.py`: new
  `PLANNER_SNAPSHOT_WRITABLE_FIELDS = {"percentage_of_reference_year"}` and
  `writable_fields_for_row(module_type, data_entry_type, source)`, which
  unions the provenance whitelist, `ALWAYS_WRITABLE_FIELDS`, and — for
  `PLANNER_SNAPSHOT`-sourced rows only — the planner scaling field. The
  field stays out of the `PERMISSIONS` matrix on purpose:
  `_validate_registry()` checks matrix fields against each module's update
  DTO, where it does not exist. Snapshot rows otherwise keep exactly the
  USER-branch field caps (narrow fix, confirmed over full row exemption).
- `backend/app/workflows/carbon_report_module.py`: the update guard resolves
  `allowed` via `writable_fields_for_row(...)` instead of the inline
  `editable_fields(...) | ALWAYS_WRITABLE_FIELDS`.
- `frontend/src/api/http.ts`: when the parsed 403 `detail` is an object
  (row-level business denial: `FIELD_NOT_EDITABLE`, `ROW_NOT_DELETABLE`),
  the hook returns without notifying/redirecting so ky throws `HTTPError`
  and the caller's catch surfaces its own save-error toast. String details
  keep the existing `/unauthorized` redirect.

The slider only renders when `row.reference_kg_co2eq != null`
(`ModuleTable.vue`), i.e. only on `PLANNER_SNAPSHOT` rows — keying the grant
on that source covers every slider row, including rows a user adds manually
in the planner (no reference entry → no slider).

## Regression test

`backend/tests/unit/workflows/test_carbon_report_module_permissions.py::
test_update_planner_snapshot_row_percentage_succeeds` — a
`PLANNER_SNAPSHOT` equipment row PATCHed with
`{"percentage_of_reference_year": 50}` must reach
`DataEntryService.update`; 403s without the fix.

## Related

- [951-edit-rights-per-dataset-permissions.md](951-edit-rights-per-dataset-permissions.md)
  — the permission layer this amends.
