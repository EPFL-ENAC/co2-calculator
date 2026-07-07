---
status: proposed
issue: 951
last_updated: 2026-07-07
title: "Edit rights per permissions on each dataset (per-module, per-source field policy)"
summary: "Gate which fields are editable and whether a row is deletable based on data provenance (BackOffice-imported vs user-added), per module, on top of the existing modules.* RBAC gate."
---

# Edit rights per permissions on each dataset

## Problem (from #951)

Issue #951 specifies, per module, which fields BackOffice-imported data vs
user-added data may have edited/deleted. Full matrix (French source table) —
BackOffice-imported rows are **never** deletable and mostly not editable
(Equipment is the one exception: `sub_class`, `active_usage`,
`standby_usage` stay editable even on BackOffice rows; `class` does not);
user-added rows are always deletable and have a fixed field allowlist per
module:

| Module                     | BackOffice row                                                                       | User row                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| Headcount                  | locked                                                                               | `Name`, `Position`, `SCIPER`, `EPT`                                                          |
| Process Emissions          | locked                                                                               | `Emitted Gas`, `Sub-category`, `Quantity`                                                    |
| Buildings — combustion     | locked                                                                               | `Heating type`, `Quantity` (`Unit` never editable)                                           |
| Buildings — rooms          | locked                                                                               | `Building`, `Room`, `Type`, `Allocation ratio`                                               |
| Equipment                  | not deletable; `sub-class`, `Active usage`, `Standby usage` editable, `class` locked | `Class`, `Sub-class`, `Active usage`, `Standby usage`                                        |
| External Cloud             | locked                                                                               | `Provider`, `Service Type`, `Spending`, `Currency`                                           |
| External AI                | locked                                                                               | `Provider`, `Use`, `Number of users`, `Frequency`                                            |
| Prof. Travel — Plane/Train | locked                                                                               | `From`, `To`, `Date`, `Number of trips`, `Traveler`                                          |
| Purchase                   | locked                                                                               | `Item Description`, `Supplier`, `UNSPSC description`, `Quantity`, `Total Amount`, `Currency` |
| Purchase — Centralized     | locked                                                                               | `Item Description`, `Annual Consumption`                                                     |
| Research Facilities        | locked                                                                               | `Research facilities`, `Use`, `Unit`                                                         |

All user rows: manual add always allowed, always deletable. Issue has two
open clarifications from the reporter, unresolved as of this writing:
whether Centralized Purchases' matrix should match External Cloud/AI, and
delete-icon visibility when a module is deactivated. Both are called out as
open questions below, not decided here.

## Design

This is a **data-provenance** rule, not a role-based one: it answers "given
this row's origin, which fields may be touched" — independent of _who_ is
asking. It composes with, and sits strictly after, the existing RBAC gate;
it does not replace it and does not need a new `modules.*` permission key.

**Existing building blocks (verified in code):**

- `backend/app/models/data_entry.py:53-66` — `DataEntrySourceEnum`
  (`USER_MANUAL`, `CSV_MODULE_PER_YEAR`, `CSV_MODULE_UNIT_SPECIFIC`,
  `API_MODULE_PER_YEAR`, `API_MODULE_UNIT_SPECIFIC`,
  `EXTERNAL_INTEGRATION`) already stamped on every `DataEntry.source`
  (`data_entry.py:149-153`). This is the exact "BackOffice data vs user
  data" axis the issue's table needs — `USER_MANUAL` = user row, every
  other value = BackOffice/imported row.
- `backend/app/core/policy.py:122-236` (`_evaluate_resource_access_policy`)
  already has precedent for a source-based lock: for `professional_travel`,
  `provider == "api"` → read-only for everyone
  (`policy.py:175-180`). #951 generalizes this shape to all modules and
  adds field-level granularity, not just whole-row lock.
- `backend/app/core/policy.py:644` (`check_module_permission_for_unit`) is
  the existing RBAC gate already called at the top of both mutation routes
  (`carbon_report_module.py:974-980` in `update`, `:1048-1053` in
  `delete`). The new provenance check runs **after** this, on top, not
  instead of it — a PRINCIPAL who is authorized to edit a unit's Equipment
  module still can't touch a BackOffice row's `class` field.
- `backend/app/utils/permissions.py:104-132` (`resolve_module_scope`) is
  the own/unit/global breadth logic — unrelated axis, left untouched.

**New pieces:**

1. `backend/app/core/data_entry_field_policy.py` (new file) — one static
   matrix, `MODULE_FIELD_POLICY: dict[ModuleTypeEnum, ModuleFieldPolicy]`,
   encoding the table above as
   `ModuleFieldPolicy(backoffice_editable_fields=frozenset(...),
backoffice_deletable=bool, user_editable_fields=frozenset(...) |
"all", user_deletable=bool)`. One file, one shape, all modules —
   avoids one-off checks scattered per route (mirrors "reuse existing
   patterns": this is the travel-like dynamic-module convention already
   used elsewhere in the codebase).
2. `get_row_policy(module_type: ModuleTypeEnum, source: int | None) ->
RowPolicy` — `source is None or source ==
DataEntrySourceEnum.USER_MANUAL` picks the user branch, everything else
   picks the BackOffice branch. Returns `{editable_fields:
frozenset[str] | Literal["all"], deletable: bool}`.
3. Enforcement in the two existing mutation routes:
   - `update` (`carbon_report_module.py:952-1028`): after the existing
     `check_module_permission_for_unit` call, load the target `DataEntry`
     (source + data_entry_type already needed downstream), compute
     `get_row_policy(...)`, and 403 if any key in `item_data` is not in
     `editable_fields` (unless `"all"`).
   - `delete` (`carbon_report_module.py:1031-...`): same lookup, 403 if
     `not deletable`.
   - `create` (`carbon_report_module.py:815`) is untouched — new rows are
     always `source=USER_MANUAL`.
4. Response shape: attach the computed `editable_fields` /`deletable` to
   the row response (`DataEntryResponse` / `HeadcountItemResponse`) so the
   frontend never recomputes the matrix — mirrors the "backend is source
   of truth, never reimplement formulas client-side" convention already
   in force for permissions (`frontend/src/utils/permission.ts` consumes a
   backend-computed `FlatUserPermissions` shape the same way).
5. Frontend: `frontend/src/components/organisms/module/ModuleTable.vue`
   reads `row.deletable` to show/hide the delete icon (per the open
   clarification on deactivated-module delete-icon behavior — not
   resolved by this plan) and each module form component reads
   `row.editable_fields` to disable inputs outside the set. No role
   check, no reimplementation of the table — just reading backend flags,
   per the frontend-never-checks-roles convention.

## Steps

- [ ] Add `backend/app/core/data_entry_field_policy.py`: `ModuleFieldPolicy`
      dataclass/TypedDict + `MODULE_FIELD_POLICY` matrix for all 11 modules
      per the table above, `get_row_policy(module_type, source) -> RowPolicy`.
      Comment inline on Equipment's asymmetric BackOffice row and flag
      Centralized Purchases as pending clarification (open question below).
- [ ] Wire `get_row_policy` into `update`
      (`backend/app/api/v1/carbon_report_module.py:952`): load the entry,
      reject (403) any `item_data` key outside `editable_fields`.
- [ ] Wire `get_row_policy` into `delete`
      (`backend/app/api/v1/carbon_report_module.py:1031`): reject (403) if
      `not deletable`.
- [ ] Extend `DataEntryResponse`/`HeadcountItemResponse` (and equivalents
      returned by list/get) to carry `editable_fields` + `deletable`,
      computed via `get_row_policy` at serialization time.
- [ ] Frontend: `ModuleTable.vue` — hide/disable delete affordance when
      `row.deletable` is false.
- [ ] Frontend: per-module form/edit components — disable inputs whose
      field key is not in `row.editable_fields`.
- [ ] Backend tests: unit tests for `get_row_policy` per module/source
      combination; integration tests on `update`/`delete` — BackOffice row
      rejects out-of-allowlist field edit and delete, user-manual row
      accepts both (memory: bugs/behavior changes ship with regression
      tests).
- [ ] Open question (unresolved in #951, do not decide here): should
      Centralized Purchases' matrix mirror External Cloud/AI's shape
      instead of its current distinct one? Needs sign-off before locking
      `MODULE_FIELD_POLICY` for that module.
- [ ] Open question (unresolved in #951): exact delete-icon visibility
      rule when a module is deactivated — confirm before finalizing
      `ModuleTable.vue` changes.
