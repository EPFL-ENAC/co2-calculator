---
status: delivered
issue: 2453
last_updated: 2026-08-28
title: "Unit-specific CSV/API uploads are user-owned — inline edit and delete restored"
summary: "#951 bucketed every ingested row into the locked IMPORTED branch. The real line is per-year vs unit-specific: a CSV/API upload into one's OWN module carries carbon_report_module_id and is the operator's own data, so it gets the same edit/delete rights as manual entry. Adds CSV_MODULE_UNIT_SPECIFIC (2) and API_MODULE_UNIT_SPECIFIC (4) to the user branch, backend and frontend."
---

# Unit-specific uploads are user-owned (#2453)

## Problem

Rows imported by CSV into a module (reported on Process Emissions, but the bug
is module-wide) were neither editable inline nor deletable. Manually added
rows in the same table were.

#951 shipped a two-way provenance bucket keyed on `DataEntry.source`, with
only `USER_MANUAL` and `PLANNER_SNAPSHOT` in the `USER` branch — so **every**
ingested row locked, including one the operator uploaded into their own
module a minute earlier.

## Root cause

The bucketing read "manual vs uploaded". The line the product actually draws
is **who owns the data**, which the source enum already encodes:

| Source                         | Meaning                      | Branch     |
| ------------------------------ | ---------------------------- | ---------- |
| `USER_MANUAL` (0)              | typed into the module table  | `user`     |
| `CSV_MODULE_PER_YEAR` (1)      | backoffice per-year CSV      | `imported` |
| `CSV_MODULE_UNIT_SPECIFIC` (2) | CSV into one's own module    | **`user`** |
| `API_MODULE_PER_YEAR` (3)      | backoffice per-year API sync | `imported` |
| `API_MODULE_UNIT_SPECIFIC` (4) | API into one's own module    | **`user`** |
| `EXTERNAL_INTEGRATION` (5)     | third-party import           | `imported` |
| `PLANNER_SNAPSHOT` (6)         | Simulator Plan prefill       | `user`     |

A job gets `EntityType.MODULE_UNIT_SPECIFIC` (→ source 2/4) exactly when its
config carries `carbon_report_module_id` (`api/v1/data_sync.py:841`), which
only the in-module upload sets (`ModuleTable.vue:745`). Backoffice per-year
uploads never do. So the enum member is a reliable proxy for "the operator
uploaded this into their own module".

This also aligns the edit policy with re-upload semantics, which already
treated unit-specific rows as operator-owned: `BULK_PER_YEAR_SOURCES`
(`models/data_entry.py`) excludes them from the per-year replace-delete, so a
backoffice per-year ingest never wipes a user's own upload. The two rules are
independent, though — do not derive one from the other.

## Change

Two constants, per #951's accepted "hardcoded in TWO places that must move
together" tradeoff:

- `backend/app/core/data_entry_permissions.py` — `_USER_BRANCH_SOURCES` gains
  `CSV_MODULE_UNIT_SPECIFIC` and `API_MODULE_UNIT_SPECIFIC`.
- `frontend/src/utils/dataEntryPolicy.ts` — `USER_BRANCH_SOURCES` becomes
  `{0, 2, 4, 6}`.

Everything downstream follows for free: `writable_fields_for_row` and
`can_delete` in `CarbonReportModuleWorkflow.update`/`.delete`, and the
`data_entry_policies` payload the frontend gates the table on.

## Scope: this is module-wide, not Process-Emissions-only

The fix lives in the shared bucketing function, so it flips every module's
unit-specific rows to the user branch. Most visible beyond the reported
module: **Equipment** — those rows move from the IMPORTED whitelist
(`sub_class`, active/standby usage) to the USER one, which additionally grants
`equipment_class` and makes the row deletable. That is the intended reading of
#951's "same behavior as manual entry", confirmed on #2453.

Unchanged: backoffice per-year rows stay fully locked, `EXTERNAL_INTEGRATION`
stays locked, and planner/embodied-energy types stay policy-exempt.

## Tests

The two tests that encoded the old bucketing are the regression tests — each
split in two so both halves are asserted explicitly:

- `backend/tests/unit/core/test_data_entry_permissions.py` —
  `test_unit_specific_ingest_is_user` (new) and
  `test_backoffice_per_year_ingest_is_imported`.
- `frontend/tests/unit/dataEntryPolicy.spec.ts` — `branchOf` for `[2, 4]` is
  `user`, for `[1, 3, 5]` is `imported`.

Both fail without the change.
