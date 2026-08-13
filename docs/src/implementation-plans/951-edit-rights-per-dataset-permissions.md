---
status: in-progress
issue: 951
last_updated: 2026-08-13
title: "Edit rights per permissions on each dataset — hardcoded provenance-keyed data-entry permissions"
summary: "Enforce, per module/submodule, which fields of BackOffice-imported rows vs user-added rows may be edited and whether a row is deletable — keyed on DataEntry.source provenance, matrix hardcoded in code (no DB table, no backoffice UI), enforced in the module mutation workflow and surfaced to the frontend via a per-submodule policy object."
---

# Edit rights per permissions on each dataset (hardcoded provenance matrix)

## Problem (from #951)

Issue #951 specifies, per module, which fields of BackOffice-imported rows vs
user-added rows may be edited, and whether a row is deletable. Summary of the
matrix (source table in French on the issue):

| Module                     | Imported (BackOffice) row                                                                | User (manual) row — editable fields                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Headcount                  | locked, not deletable                                                                    | `Name`, `Position`, `SCIPER`, `EPT`                                                               |
| Process Emissions          | locked, not deletable                                                                    | `Emitted Gas`, `Sub-category`, `Quantity`                                                         |
| Buildings — combustion     | locked, not deletable                                                                    | `Heating type`, `Quantity` (`Unit` never editable)                                                |
| Buildings — rooms          | locked, not deletable                                                                    | `Building`, `Room`, `Type`, `Allocation ratio`                                                    |
| **Equipment**              | **not deletable; `sub_class`, `active usage`, `standby usage` editable; `class` locked** | `Class`, `Sub-class`, `Active usage`, `Standby usage`                                             |
| External Cloud             | locked, not deletable                                                                    | `Provider`, `Service Type`, `Spending`, `Currency`                                                |
| External AI                | locked, not deletable                                                                    | `Provider`, `Use`, `Number of users`, `Frequency`                                                 |
| Prof. Travel — Plane/Train | locked, not deletable                                                                    | `From`, `To`, `Date`, `Number of trips`, `Traveler`                                               |
| Purchase                   | locked, not deletable                                                                    | `Item Description`, `Supplier`, `UNSPSC description`, `Quantity`, `Total Amount`, `Currency`      |
| Purchase — Centralized     | locked, not deletable                                                                    | `Item Description`, `Annual Consumption` (kept distinct from Cloud/AI shape — decided 2026-08-13) |
| Research Facilities        | locked, not deletable                                                                    | `Research facilities`, `Use`, `Unit`                                                              |

User rows are always manually addable and always deletable.

## Design brief (maintainer, #1554/#1747 review)

> "It should be 'permission based' using the 'source' column of the
> data_entry — create new data-entry permissions. It concerns only user
> principal and user standard because it's inside a module. Non-modifiable /
> non-deletable for imported module data; for equipment, authorized
> modification of some fields only; another permission for manual insertion by
> field name. Permissions are stored dynamically in the DB (with defaults
> created for the app, managed on the backoffice) and the system merges
> backend-defined permissions and DB-defined permissions."

The "stored dynamically in the DB / backoffice-managed" half of the brief is
**explicitly descoped** (decision 2026-08-13, see Revision note). Everything
else — provenance-keyed, positive grants, field-level granularity for
Equipment — stands.

## Revision note (2026-08-13, supersedes the 2026-07-10 version)

The prior version of this plan added a `data_entry_permissions` DB table, an
`EffectivePolicyResolver` with TTL cache and override-merge precedence, and a
Phase 2 backoffice management UI + audit trail. On review, that machinery was
overzealous for the actual requirement: the #951 matrix is a fixed,
known-at-code-time table, nobody has asked for it to be edited without a
deploy, and a DB layer that starts empty and does nothing until a UI exists
to write to it is unused complexity carried for a hypothetical.

**Dropped:** `data_entry_permissions` table/migration, resolver/cache,
override-merge precedence rules, the `data_entry.*` string permission
vocabulary (it existed to be stored/edited in DB text columns — no DB, no
need), backoffice endpoints, backoffice UI, audit trail, NULL-source backfill
migration (see Migration & rollout).

**Kept:** provenance derivation from `DataEntry.source`, the three-layer
authorization model (RBAC → breadth → data-entry permissions), field-level
grants for Equipment, `note` as always-writable, enforcement in the
create/update/delete workflow methods, the frontend policy surface.

If DB-editable permissions become an actual need later, the matrix's shape
(`(module, submodule, provenance) → editable fields`) is the same shape a DB
table would take — reintroducing it is additive, not a rewrite.

## Verified codebase facts that shape the design

- **RBAC today is 100% code-derived, nothing in DB.**
  `backend/app/models/user.py:67` (`calculate_user_permissions`) maps roles →
  a flat dict `{"modules.equipment/<unit>": ["view","edit","sync"], ...}` at
  request time. Roles come from ACCRED sync. There is **no permission table**
  anywhere, and this plan does not add one.
- **Roles in scope**: `CO2_USER_PRINCIPAL` (unit breadth, all 8 modules) and
  `CO2_USER_STD` (own breadth, only `professional_travel` and
  `external_cloud_and_ai`) — `user.py:183-273`. Backoffice roles get zero
  `modules.*` keys, so they cannot call the module mutation routes at all;
  "concerns only principal/standard" falls out of the existing route gate for
  free, no extra role check needed.
- **Module-level gate**: `check_module_permission_for_unit`
  (`backend/app/core/policy.py:710`) already runs at the top of `create`,
  `update`, and `delete` in `backend/app/api/v1/carbon_report_module.py`. The
  new layer composes strictly AFTER it.
- **`DataEntry.source`** (`backend/app/models/data_entry.py:66-76`) is a
  nullable int; `DataEntrySourceEnum`: `USER_MANUAL=0`,
  `CSV_MODULE_PER_YEAR=1`, `CSV_MODULE_UNIT_SPECIFIC=2`,
  `API_MODULE_PER_YEAR=3`, `API_MODULE_UNIT_SPECIFIC=4`,
  `EXTERNAL_INTEGRATION=5`. Already serialized on responses as a raw
  `source: int | None` field (shipped 2026-07-16, commit `961b7034`) — this
  plan reuses that field as-is, no new `provenance` field is added to the
  API (see API surface).
- **GOTCHA — manual creates never stamp `source`.** `USER_MANUAL` is
  referenced nowhere except its enum definition. The UI create path
  (`CarbonReportModuleWorkflow.create` → `DataEntryService.create`) passes no
  `source`, so manual rows persist with `source = NULL`. Ingest paths DO
  stamp it (since commit `e6977b5f0`, 2026-03-18). This plan ships the
  stamping fix (see Migration & rollout).
- **GOTCHA — CSV ingestion had a stamping gap.** `DataEntry`/`source` shipped
  2026-01-23 (`c054e94f`); the CSV provider went live 2026-02-12 (`b314b33b`)
  _without_ stamping `source`; stamping was added 2026-03-18 (`e6977b5f0`).
  Any imported row created in that ~5-week window would carry `source =
NULL`, indistinguishable from a manual row. Decision 2026-08-13: no
  backfill migration — accept the risk and fix forward (see Migration &
  rollout).
- **GOTCHA — the one existing provenance rule is dead code.**
  `_evaluate_resource_access_policy` (`backend/app/core/policy.py:122-236`,
  professional_travel `provider == "api"` → read-only) and its wrapper
  `check_resource_access` have **no callers in any API route**. This plan
  supersedes it; the dead branch should be retired in the same PR.
- **Update overlays blindly.** `CarbonReportModuleWorkflow.update`
  (`backend/app/workflows/carbon_report_module.py:205`) loads the existing
  entry and merges `item_data` over persisted data — any field in the PATCH
  body wins. It already has the entry in hand, which makes it the natural
  enforcement point (no extra query).
- **`note` is patched through the same endpoint.** `ModuleTable.vue`
  `saveNote()` sends `PATCH {note}`. Notes must stay writable on locked
  imported rows (the Equipment power-change-request flow depends on it,
  issue #266) — `note` is an always-allowed field, not part of the matrix.
- **Frontend gating today is module-level only.** `ModuleTable.vue:869-883`
  disables ALL editing via `modules.X` edit permission + validated state +
  backoffice disable; field editability is static per module config
  (`frontend/src/constant/module-config/*.ts`: `editableInline`, `readOnly`,
  `readOnlyWhenFilled`). The frontend has no per-row provenance gating today.
- **Equipment fields** (`backend/app/modules/equipment/data_entries.py:73-97`):
  `equipment_class` (kind), `sub_class` (subkind), `active_usage_hours_per_week`,
  `standby_usage_hours_per_week`, `name`, `note`. Usage hours are a live
  default from the Factor when unset — an imported row with editable usage
  hours is exactly the "complete missing fields" case the brief describes.
- **Equipment `to_response` merges factor values into fields** — `sub_class`
  can display a factor-preferred value that differs from what's persisted in
  `data`. The value-diff check (see enforcement) MUST diff against the
  persisted `data` column, not the serialized response, or an untouched
  locked field with a factor-merged display value will false-403.
- **Planner rows share the same workflow methods.** `CarbonReportModuleWorkflow.create`
  and `.update` branch directly on `DataEntryTypeEnum.planner_purchase` /
  `planner_purchase_budget` (simulator "what-if" snapshot rows); `planner_headcount`
  exists too (`DataEntryTypeEnum.is_planner_kind`, a property, 80+ range,
  `models/data_entry.py:51-61`). None of these are in the #951 matrix, and a
  module-wide `(purchase, None, …)` entry would otherwise silently apply
  reporting-data locks to planner snapshot rows. Planner-kind entries must be
  exempt from this policy layer entirely (same treatment as bulk ingestion,
  not a "fully open" matrix entry) — checked via the existing
  `is_planner_kind` property before any policy lookup.
- **`building_embodied_energy` is system-derived, not user-facing.**
  `EmbodiedEnergyWorkflow.post_create`/`post_update`/`post_delete`
  (`backend/app/workflows/embodied_energy.py`) call
  `CarbonReportModuleWorkflow.create/update/delete` internally as a side
  effect of room (`building`) mutations, using the acting user's context. It
  has no frontend table, is never directly user-edited, and isn't in the
  #951 matrix. Same exemption as planner:
  `SYSTEM_MANAGED_TYPES = {DataEntryTypeEnum.building_embodied_energy}`,
  checked alongside `is_planner_kind`.
- **GOTCHA — Simulator Plan prefill reuses the regular `data_entry_type`,
  not a planner-kind one, and was missed by both exemptions above (found by
  code review after initial implementation, 2026-08-13).**
  `SimulatorPlanService.prefill_module_from_reference`
  (`backend/app/services/simulator_plan_service.py:500-514`) copies a
  reference-year row into a plan module with the SAME
  `data_entry_type_id` — `building`, `energy_combustion`, an equipment
  kind, etc. — stamped `source=DataEntrySourceEnum.PLANNER_SNAPSHOT`
  (value `6`, a source enum member this plan's "Verified codebase facts"
  section had not accounted for). Only headcount prefill uses a true
  planner-kind type (`planner_headcount`, already exempt); every other
  prefilled module (`PLANNER_PREFILLED_MODULE_TYPES` in
  `module_type.py`: process_emissions, buildings, equipment,
  research_facilities, external_cloud_and_ai) shares its type with real
  calculator rows, so `is_policy_exempt()` (keyed on type) can't catch it —
  `provenance_of()` was silently resolving these to `IMPORTED`, locking and
  making non-deletable every prefilled plan row app-wide (the "% of
  reference year" slider, equipment usage, etc.) — the opposite of the
  intended behavior; a plan row is the user's own editable data, not
  externally imported. Fixed in `provenance_of()`:
  `PLANNER_SNAPSHOT` resolves to `Provenance.USER`, same as `USER_MANUAL`
  and `None`.
- **Create DTOs are already the create-field authority.** Cross-checked every
  module's `*Create` DTO against its matrix row: Purchase requires
  `purchase_institutional_code`, Purchase Centralized requires `unit` +
  `coef_to_kg`, Equipment requires `equipment_id` — none are in the
  user-branch _update_ editable set. The create DTOs are already scoped to
  exactly the fields a manual entry should expose; the permission layer must
  NOT re-derive an allow-list for create fields from the update grants (see
  Backend enforcement points).

## Design

### Concept: a third authorization axis

Authorization is three composed layers, each answering one question:

1. **RBAC (existing, unchanged)** — _may this user act on this module in this
   unit?_ `modules.X/<unit>` keys, `check_module_permission_for_unit`.
2. **Breadth (existing, unchanged)** — _which rows can they see/touch?_
   own/unit/global via `resolve_module_scope` + data filters.
3. **Data-entry permissions (NEW)** — _given this row's provenance, which
   operations and which fields?_ A hardcoded lookup, no DB.

Layer 3 is deliberately **role-agnostic**: it keys on the row (module,
submodule, provenance), not on the caller. Since only principal/standard can
reach these routes (layer 1), "concerns only user principal and user
standard" is satisfied without duplicating role logic.

### Provenance derivation

```python
class Provenance(str, Enum):
    USER = "user"          # source is None or USER_MANUAL
    IMPORTED = "imported"  # any CSV_* / API_* / EXTERNAL_INTEGRATION

def provenance_of(source: int | None) -> Provenance:
    if source is None or source == DataEntrySourceEnum.USER_MANUAL:
        return Provenance.USER
    return Provenance.IMPORTED
```

No new API field: `source` is already on every row response. The frontend
derives the same two-way bucket from `source` with a one-line helper mirroring
`provenance_of` (documented with a comment pointing back to the backend
function, so the two don't silently drift) — this is display/gating routing,
not a computed business value, so it's an accepted exception to
"backend computes, frontend renders."

### The matrix (hardcoded)

New file `backend/app/core/data_entry_permissions.py`:

```python
# create/delete are not stored per module: per the #951 matrix, user rows are
# ALWAYS manually addable and deletable, imported rows NEVER are — no module
# is an exception. Only which fields are updatable varies per module.
PERMISSIONS: dict[tuple[ModuleTypeEnum, DataEntryTypeEnum | None, Provenance], frozenset[str] | None]
# value = the updatable field set for that (module, submodule, provenance); None = no field updatable

ALWAYS_WRITABLE_FIELDS = frozenset({"note"})

def can_create(provenance: Provenance) -> bool:
    return provenance == Provenance.USER

def can_delete(provenance: Provenance) -> bool:
    return provenance == Provenance.USER
```

One entry per (module, submodule-or-None, provenance), encoding the #951
matrix's editable-field column. `None` submodule = applies to all
`data_entry_type`s of the module; an entry with an explicit submodule is more
specific and wins (needed for Buildings, where combustion and rooms differ,
and Purchase, where `purchases_centralized` differs from the other purchase
types).

Equipment (the flagship case):

```python
(equipment, None, IMPORTED): frozenset({"sub_class",
                                        "active_usage_hours_per_week",
                                        "standby_usage_hours_per_week"}),
(equipment, None, USER): frozenset({"equipment_class", "sub_class",
                                    "active_usage_hours_per_week",
                                    "standby_usage_hours_per_week"}),
# "name" stays locked even on USER rows — not named in the #951 matrix
# (Class/Sub-class/Active/Standby usage only). Resolved 2026-08-13.
```

**Coverage validated at import time**: every `(module, submodule)` pair in
the existing `MODULE_TYPE_TO_DATA_ENTRY_TYPES` registry
(`backend/app/models/module_type.py`), **excluding `SYSTEM_MANAGED_TYPES`
and planner-kind types** (`is_planner_kind`), must have both a `USER` and
`IMPORTED` entry (module-wide or submodule-specific) — a missing entry raises
at import, not a silent full-lock at runtime (no silent fallbacks). Field
names in each entry are validated at import time against the handler's
`update_dto` model fields — a typo'd field name fails CI, not production.

**USER-branch scope, and fields the issue text doesn't literally name
(resolved 2026-08-13):** the #951 "editable fields" column is a whitelist
for BOTH branches — it caps what a user may update on their own row, not
just what's locked on an imported one. (An earlier version of this plan
treated the USER branch as unrestricted — "any field the Update DTO
accepts" — reasoning that #951 only meant to restrict imported rows. That
was corrected after review: it would have silently _removed_ editability
users have today, e.g. locking a purchase's institutional code or a train's
cabin class, with nobody having asked for that regression.) Several real
DTO fields aren't literally named in the issue's table; each was resolved
individually rather than guessed:

| Field                                                  | Resolution | Why                                                                                                                                |
| ------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `cabin_class` (plane, train)                           | Editable   | Travel-detail field, in scope of "From/To/Date/trips" intent.                                                                      |
| `origin_natural_key`/`destination_natural_key` (train) | Editable   | Paired with `origin_name`/`destination_name` in the station picker — locking one without the other breaks editing a train's route. |
| `purchase_institutional_code`                          | Editable   | This IS "UNSPSC description" — has its own update validator, proof it's a live path.                                               |
| `purchase_additional_code`                             | Locked     | Not named in the matrix.                                                                                                           |
| Equipment `name`                                       | Locked     | Matrix lists Class/Sub-class/Active/Standby usage only.                                                                            |
| `researchfacility_type` (animal_facilities)            | Locked     | Not named in the matrix (shared row with `research_facilities`).                                                                   |

Two fields the matrix DOES name but can never be granted regardless of this
table, because they have no Update DTO path for anyone (Create-only field):
Headcount's "SCIPER" (`user_institutional_id`) and Prof. Travel's "Traveler"
(same field name). Flagged, not silently worked around — if product wants
these editable, that's a separate DTO change, out of scope here.

### Backend enforcement points

All three live in `CarbonReportModuleWorkflow`
(`backend/app/workflows/carbon_report_module.py`) — after the route-level
RBAC gate, before the service write; the workflow already has the loaded
entry and module context, no extra queries. **First check in all three:**
`if data_entry_type.is_planner_kind or data_entry_type in SYSTEM_MANAGED_TYPES:
skip policy entirely` — planner snapshot rows and system-derived rows
(embodied energy) are out of #951's scope (see Verified codebase facts).

1. **`update` (entry already loaded).** Compute
   `editable = PERMISSIONS[module, entry.data_entry_type, provenance_of(entry.source)] or frozenset()`
   (submodule-specific entry wins over the module-wide one). Reject 403
   (structured detail: `{"code": "FIELD_NOT_EDITABLE", "fields": [...]}`) when
   `item_data` contains a key outside
   `editable ∪ ALWAYS_WRITABLE_FIELDS` **whose value differs from the
   persisted `data` column** (not the serialized response — Equipment's
   `to_response` merges factor-preferred values into fields like `sub_class`,
   so response value ≠ persisted value) — value-diffing, not key-presence,
   because edit dialogs may echo the full row back; an echoed unchanged
   locked field must not 403.
2. **`delete`.** Load the entry, 403 if `not can_delete(provenance_of(entry.source))`
   — i.e. delete is only ever allowed on `user` rows. The route already maps
   `PermissionError` → 403.
3. **`create`.** No permission check needed here: `create()` only ever
   produces `user`-branch rows (imported rows come from bulk ingestion, not
   this path), and `can_create` is always true for `user`. This step is pure
   bug fix: **stamp `source=DataEntrySourceEnum.USER_MANUAL` and
   `created_by_id=current_user.id`** on success — fixing the never-stamped
   bug. Accepted fields are whatever the module's `*Create` DTO already
   defines — several DTOs require creation-only fields absent from the
   update-editable set (Purchase's `purchase_institutional_code`, Purchase
   Centralized's `unit` + `coef_to_kg`, Equipment's `equipment_id`) — the DTO
   is already the correct, working scope for "manual insertion by field
   name," don't re-derive one from `PERMISSIONS`.

Bulk ingestion paths (`bulk_create`, `bulk_copy`, `bulk_delete_by_source`) are
intentionally NOT gated — they are the system writing imported data, the very
thing the policy protects from users.

Retire the dead professional_travel branch of
`_evaluate_resource_access_policy` (`policy.py:170-225`) in the same PR: its
`provider == "api"` intent is subsumed by the `imported`-branch lock (travel
API ingest stamps `API_MODULE_PER_YEAR` — verified in
`professional_travel_api_provider.py`).

### API surface for the frontend

The frontend must learn effective permissions without re-implementing the
matrix (same principle as `FlatUserPermissions`,
`frontend/src/utils/permission.ts`):

- **Submodule payload carries both branches.** Extend `SubmoduleResponse`
  (`get_submodule`, `carbon_report_module.py`) with:

  ```json
  "data_entry_policies": {
    "user":     {"create": true,  "delete": true,  "editable_fields": ["equipment_class", "sub_class", ...]},
    "imported": {"create": false, "delete": false, "editable_fields": ["sub_class", "active_usage_hours_per_week", "standby_usage_hours_per_week"]}
  }
  ```

  `create`/`delete` come from `can_create`/`can_delete` (constants per
  provenance); `editable_fields` from a direct `PERMISSIONS` lookup — no
  cache needed, it's an in-process constant dict read.

- **Each row already carries `source`.** No new per-row field; the frontend
  buckets it into `user`/`imported` locally (see Provenance derivation).
- No separate permissions endpoint: the table page already fetches the
  submodule payload; the create form only needs `policies.user.create`
  from it (whether the Add button shows at all) — **not** its
  `editable_fields`, which is an UPDATE whitelist and does not describe
  create fields (see below).

### Frontend gating

- `ModuleTable.vue`: per-row `rowPolicy = policies[branchOf(row.source)]`;
  - delete icon hidden/disabled when `!rowPolicy.delete` (existing
    `isDisabled` module-level gate stays AND-ed on top);
  - inline-editable cells (`col.editableInline`) render read-only when
    `col.id ∉ rowPolicy.editable_fields`;
  - edit dialog: pass `disabledFields` to `ModuleForm.vue` so out-of-policy
    inputs are disabled (fields stay visible — users should see the values);
  - note button: unchanged (never policy-gated).
- `ModuleForm.vue` (create mode): **field set is unchanged** — still driven
  by the module's existing static create form / DTO, same as today.
  `policies.user.editable_fields` is an UPDATE whitelist, not a create
  field list (Equipment create needs `equipment_id`, Purchase Centralized
  needs `unit`/`coef_to_kg` — neither is in the update whitelist; treating
  it as the create field set would omit required inputs and 422 every
  create). The only policy input to create mode is
  `policies.user.create`: hide the Add button entirely when false (always
  true today).
- Static config (`module-config/*.ts` `editableInline`/`readOnly`) remains
  the UI-layout default; effective editability = static config AND policy. Do
  NOT delete the static flags — they encode layout concerns (e.g. Buildings
  `Unit` never editable even on user rows).
- New types in `frontend/src/utils/permission.ts` (or a sibling
  `dataEntryPolicy.ts` leaf): `DataEntryPolicies`, `RowPolicy`, helpers
  `branchOf(source)` and `isFieldEditable(policies, source, fieldId)` —
  unit-testable, store-free. `policies` is `null` for exempt submodules
  (planner, embodied energy — see backend); `isFieldEditable` must treat
  `null` as "no #951 gating" (don't lock everything by mistaking absence
  for an empty allow-list), mirroring the backend's own exemption.

## Migration & rollout

1. **Code fix (land first, independent prerequisite):** stamp
   `source=USER_MANUAL` + `created_by_id` on the manual create path.
2. **No backfill migration.** Decision 2026-08-13: existing rows with
   `source IS NULL` are treated as `user` branch, including the small window
   of pre-2026-03-18 imported rows if any survive — accepted risk, fixed
   forward rather than scripted.
3. **Backend enforcement + response fields**, one release, straight to
   enforce — no rollout flag. The matrix is static and unit-tested per
   #951 row; nothing left to observe in log-only mode that tests don't
   already cover.
4. **Frontend gating** ships in the same release as backend enforcement (a UI
   that shows editable fields which then 403s is a UX regression to avoid).
5. Retire dead `_evaluate_resource_access_policy` travel branch, same PR or
   immediate follow-up.

## Testing strategy

- **Unit — matrix**: coverage test asserting every non-planner `(module,
submodule)` in the module registry has both `USER` and `IMPORTED` entries;
  table-driven resolution test for every row of the #951 matrix;
  `provenance_of` including `NULL → user`; registry field names validated
  against handler DTOs.
- **Integration — routes**: per module: imported row — locked field PATCH →
  403 with `FIELD_NOT_EDITABLE`, allowed field PATCH → 200, echoed unchanged
  locked field → 200, `note` PATCH → 200, DELETE → 403; user row — full field
  PATCH + DELETE → 200; POST stamps `source=0` and succeeds with exactly the
  Create DTO's required fields (not the update-editable set). Equipment
  imported: `sub_class`/usage-hours 200, `equipment_class` 403, and editing an
  imported row's factor-merged `sub_class` display value back unchanged → 200
  (value-diff against persisted data, not response). Planner: `planner_purchase`
  / `planner_purchase_budget` / `planner_headcount` create/update/delete are
  unaffected by policy regardless of `source`.
- **Frontend**: unit tests for `branchOf` / `isFieldEditable`; component
  tests for ModuleTable (delete icon per provenance, inline cell read-only)
  and ModuleForm (disabled fields, hidden Add button).
- **Regression**: professional travel API rows (previously editable — the
  fixed live bug) and the Equipment note/power-request dialog on imported
  rows.

## Steps

- [x] Fix manual-create stamping: `source=USER_MANUAL`, `created_by_id`
      (`workflows/carbon_report_module.py` → `DataEntryService.create`).
- [x] `backend/app/core/data_entry_permissions.py`: `Provenance`,
      `provenance_of`, `can_create`, `can_delete`, `PERMISSIONS` (#951
      matrix), `ALWAYS_WRITABLE_FIELDS`, `SYSTEM_MANAGED_TYPES`,
      `is_policy_exempt`, `submodule_policies`, import-time coverage +
      field validation (`_validate_registry`).
- [x] Enforce in `CarbonReportModuleWorkflow.update/create/delete`
      (planner/system-managed short-circuit first; value-diff against
      persisted `data` on update; create stamps only, no field re-check;
      403 with structured detail).
- [x] Serialize `data_entry_policies` per submodule response
      (`SubmoduleResponse`, `DataEntryService.get_submodule_data`). Also
      added `source` to the generic `DataEntryResponse` — the enforcement
      code needs it and it was only on `DataEntryResponseGen` (per-handler
      responses), a real gap `ty` caught, not just a lint nit.
- [x] Retire dead `_evaluate_resource_access_policy` travel branch (kept
      `check_resource_access`/other resource types — still legitimately
      reusable; only removed the professional_travel-specific rule and its
      4 now-obsolete tests in `test_policy.py`).
- [x] Frontend: `utils/dataEntryPolicy.ts` (`DataEntryPolicies`, `RowPolicy`,
      `branchOf`, `isFieldEditable`, `isRowDeletable`); `ModuleItem.source` +
      `Submodule.data_entry_policies` types; `ModuleTable.vue` per-row delete
      button and inline-cell gating (reuses the existing
      `isRowConditionallyReadOnly` read-only-span rendering path — no new
      visual state introduced).
- [x] Backend tests (matrix coverage, enforcement, submodule-response
      wiring, retired-policy regression) — all green, `ruff`/`ty` clean.
- [x] Frontend tests: `dataEntryPolicy.spec.ts` (27 assertions × 3
      browsers) for the pure helpers; full `test-ct` suite (348 specs)
      green after the `ModuleTable.vue` wiring.

**Deferred, not done in this pass:**

- **Modal `<module-form>` edit dialog per-field disabling.** The dialog at
  `ModuleTable.vue:344` (`editDialogOpen`/`editInputs`/`editRowData`) has no
  traceable open-trigger in the current code — those refs are declared and
  reset to `null` but never assigned a value anywhere found. Likely
  vestigial or gated behind a flow not exercised in this pass (possibly
  superseded by `EquipmentPowerFeedbackDialog`, the actual #266 power-request
  UI). Wiring `disabledFields` into a dialog whose trigger is unconfirmed
  risked guessing at dead code; flagged for the next PR that touches it
  rather than guessed at here.
- **`ModuleForm.vue` Add-button `policies.user.create` gating.** `can_create`
  is a provenance constant, always `true` for every module today (no #951
  row has a create exception) — wiring a prop for a value that never
  varies is pure speculative complexity right now. Trivial one-line addition
  if a future module ever needs `create=false`.
- **Component-level test for `ModuleTable.vue`'s new gating** (mounting the
  component and asserting the delete icon/inline cell actually render
  disabled). No existing component-test file covers `ModuleTable.vue` at
  all (2432 lines, no CT harness for it yet) — the pure logic
  (`isFieldEditable`/`isRowDeletable`) is fully unit-tested; the two-line
  template wiring that calls it is not independently exercised through the
  DOM. Building a `ModuleTable.vue` CT harness from scratch is a
  significant, separate undertaking, not a #951-sized addition.

## Open questions (need sign-off)

1. **Delete-icon visibility when a module is deactivated** — interacts with
   the existing `isDisabled` gate in `ModuleTable.vue:876-883`. Unresolved
   from #951; assumed AND-ed with the existing gate.
2. **Standard users** — matrix applies identically to STD users
   (own-breadth, travel + cloud/AI only)? Assumed yes — breadth already
   restricts them to their own rows; provenance rules apply on top.
3. **Scope of enforcement for `sync`/CSV re-upload flows** — per-year
   full-replace ingest deletes imported rows wholesale
   (`bulk_delete_by_source`) — assumed exempt from delete gating (system
   operation). Confirm.

Resolved 2026-08-13 (kept for record): Centralized Purchases keeps its
distinct 2-field shape; NULL-source rows get no backfill (fix forward);
dynamic DB-stored permissions and the backoffice UI are out of scope;
`create`/`delete` are provenance-constants not per-module grants, no `"*"`
wildcard, no rollout flag (ponytail-review, applied in full); the #951
"editable fields" column is a literal per-field whitelist for the USER
branch too (not "any DTO field") — see "USER-branch scope" above for the
individually-resolved fields this uncovered (cabin_class, train natural
keys, purchase_institutional_code editable; purchase_additional_code,
equipment name, animal researchfacility_type locked).
`DataEntryResponse` (generic, used by `.get()`) needed its own `source`
field — it was only on `DataEntryResponseGen` (per-handler responses),
caught by `ty`, not by mocked unit tests. `openapi.d.ts` was already ~4
weeks / 44 backend commits stale before this change; regenerating it is a
separate follow-up, not bundled here — this plan's own frontend types are
hand-written (see Frontend gating), not generated-schema-dependent.

## Manual QA finding: frontend inline-editing was never enabled for most modules (2026-08-13)

Manual testing surfaced that Headcount's Name/Position/SCIPER/EPT showed as
non-editable regardless of provenance. Root cause: `editableInline` on
`ModuleField` gates whether a column renders as an input at all — this
plan's per-row policy check only decides whether an _already inline-
editable_ column is locked for a given row. Headcount's `memberFields`/
`studentFields` never set `editableInline` on any field, so the #951
mechanism had nothing to act on: cells rendered as plain text in both
directions before and after this plan's changes, masking the gap.

Audited every module-config file's `editableInline` flags against the
backend's USER editable-field sets. Already correct (no changes needed):
Equipment, External Cloud/AI, Process Emissions, Purchase Centralized,
Buildings — combustion. **Fixed** (flag added on exactly the fields the
backend now allows, per module):

- Headcount member: `name`, `sius_code`, `fte` (`user_institutional_id` —
  see SCIPER note below).
- Headcount student: `fte`.
- Buildings — rooms: `building_name`, `room_name`, `room_allocation_ratio`
  (`room_type` was already correct; `room_surface_square_meter` stays
  locked, not in the #951 matrix).
- Research Facilities (both submodules): `researchfacility_name`, `use`,
  `use_unit` (common only) (`researchfacility_type` stays locked, animal-
  specific, not named in the matrix).
- Purchase (main, non-centralized kinds): `name`, `supplier`.
- Professional Travel: `departure_date` only (see below — origin/
  destination deferred).

**Deferred — Professional Travel `origin_iata`/`origin_name` +
`destination_iata`/`destination_name`.** Backend already allows these for
USER rows, but the CREATE form resolves them via a `direction-input`/
autocomplete component (pairing the display name with an IATA code or
`origin_natural_key`/`destination_natural_key`), while `ModuleTable.vue`'s
generic inline-editable branch only supports plain `QInput`/`QSelect` or
the `module-inline-select` kind/subkind component. Flipping
`editableInline: true` on a bare text field would let a user edit the
display name inline while leaving its paired code/natural_key stale —
exactly the desync the backend explicitly grants both fields together to
avoid (see PERMISSIONS comment on train's fields). Needs either a proper
inline autocomplete component or a decision that this pair is edit-dialog-
only; not done in this pass.

## SCIPER (user_institutional_id) made updatable on a user's own Headcount row (2026-08-13)

Manual QA also surfaced the product call: SCIPER should be editable when
the row was user-created, reversing this plan's earlier framing of it as
"Create-only, no Update DTO path for anyone." Implemented:

- `HeadCountUpdate` gained `user_institutional_id` (validator mirrors
  Create's: non-empty after strip).
- `CarbonReportModuleWorkflow.update()` now re-runs create()'s
  `(user_institutional_id, sius_code)` uniqueness check when either field
  changes, `exclude_id=item_id` — the DTO alone can't enforce this, and it
  was never needed on update before because the field wasn't writable.
- PERMISSIONS: headcount member USER branch gained
  `user_institutional_id`. IMPORTED stays locked — this only applies to a
  user's own row.
- Frontend: `editableInline: true` (plain text field, no autocomplete
  complexity, unlike Traveler below).

**Not extended to Prof. Travel's "Traveler"** (same underlying
`user_institutional_id` field, same matrix wording) — it needs the same
DTO + uniqueness-check work AND a richer inline component (see the
deferred origin/destination note above; Traveler is itself an autocomplete
select in the create form, not a plain text box). Tracked as a follow-up.

## Second code-review round (2026-08-13, post-commit)

Six findings on the committed backend+frontend diff; four fixed, two
rejected with reasoning kept here rather than silently dropped:

1. **Fixed — kind-change side effect on a locked field wasn't checked.**
   `clear_dependent_fields_on_kind_change()` (pre-existing, not #951's)
   nulls Purchase's `purchase_additional_code` when
   `purchase_institutional_code` (the kind field, USER-editable) changes —
   my value-diff only inspected the caller's literal `item_data`, never the
   post-mutation `update_payload`, so this null wasn't policy-checked.
   Empirically confirmed the field really does get nulled and persisted.
   Decision: **allow it** — a stale dependent code invalidated by its own
   permitted primary-field change is a data-integrity cascade, not a user
   attempting to write a locked field; blocking it would make
   `purchase_institutional_code` uneditable on any row that already has an
   additional code, breaking the very editability this round confirmed.
   Documented at the check site and pinned with
   `test_update_purchase_kind_change_clears_locked_dependent_field`.
2. **Fixed — `None` from `submodule_policies()` conflated two different
   meanings.** Exempt-submodule (deliberate, "no #951 gating") and a
   hypothetical future registry gap (a `DataEntryTypeEnum` member never
   added to `MODULE_TYPE_TO_DATA_ENTRY_TYPES`) both silently returned
   `None` — the frontend can't tell them apart, and a real gap would render
   every field editable / delete enabled until the backend's own
   enforcement rejected the submit. Added `find_uncovered_types()` +
   folded into `_validate_registry()`: any enum member that's neither
   policy-exempt nor registered now fails at import, not silently.
3. **Not changed, strengthened comments instead — frontend hardcodes the
   backend's source→branch bucketing.** Already a deliberate, user-approved
   tradeoff (reuse `source`, no new API field). Real drift risk if a future
   `DataEntrySourceEnum` member is added without updating both sides — now
   cross-referenced explicitly in both `data_entry.py`'s docstring and
   `dataEntryPolicy.ts`'s comment, so the next editor is pointed at the
   pair.
4. **Fixed — `data_entry_policies` was a loose `dict[str, dict[str,
object]]`, not a typed schema.** Added `RowPolicy`/`DataEntryPolicies`
   Pydantic models in `schemas/carbon_report_response.py`;
   `submodule_policies()` now returns the typed model. Wire shape (JSON)
   is unchanged, so this didn't touch the frontend contract.
5. **Rejected — `_validate_registry()` runs at import time instead of a
   FastAPI lifespan check.** The guardrail this echoes (boot-time checks
   belong in the lifespan, not Settings validators) was about
   environment-dependent validation failing unpredictably per-process
   (the migration Job incident, PR #1775). This check has no such
   dependency: it's a pure function of hardcoded data (the PERMISSIONS
   dict, the module registry, each handler's static DTO fields) that
   either always passes or always fails, identically, regardless of which
   process imports it. Fail-fast-everywhere is the correct behavior for a
   deterministic check like this, not a problem to route through the
   lifespan.
6. **Rejected — `delete()` does two DB round-trips (fetch for the policy
   check, then `DataEntryService.delete()`'s own internal fetch).** Already
   an explicitly accepted tradeoff in this plan's original enforcement-point
   design (see "Backend enforcement points" above) — a rarely-hit path, not
   worth the added complexity of threading a pre-fetched entry through
   `DataEntryService.delete()`.
