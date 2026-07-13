---
status: proposed
issue: 951
last_updated: 2026-07-10
title: "Edit rights per permissions on each dataset — provenance-keyed data-entry permissions (code defaults + DB overrides)"
summary: "Introduce a named data-entry permission layer keyed on DataEntry.source provenance (imported vs user), with backend-defined defaults merged with DB-stored overrides editable from the backoffice, enforced in the module mutation workflow and surfaced to the frontend as effective policies."
---

# Edit rights per permissions on each dataset (permission-based redesign)

## Problem (from #951)

Issue #951 specifies, per module, which fields of BackOffice-imported rows vs
user-added rows may be edited, and whether a row is deletable. Summary of the
matrix (source table in French on the issue):

| Module                     | Imported (BackOffice) row                                                                | User (manual) row — editable fields                                                          |
| -------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Headcount                  | locked, not deletable                                                                    | `Name`, `Position`, `SCIPER`, `EPT`                                                          |
| Process Emissions          | locked, not deletable                                                                    | `Emitted Gas`, `Sub-category`, `Quantity`                                                    |
| Buildings — combustion     | locked, not deletable                                                                    | `Heating type`, `Quantity` (`Unit` never editable)                                           |
| Buildings — rooms          | locked, not deletable                                                                    | `Building`, `Room`, `Type`, `Allocation ratio`                                               |
| **Equipment**              | **not deletable; `sub_class`, `active usage`, `standby usage` editable; `class` locked** | `Class`, `Sub-class`, `Active usage`, `Standby usage`                                        |
| External Cloud             | locked, not deletable                                                                    | `Provider`, `Service Type`, `Spending`, `Currency`                                           |
| External AI                | locked, not deletable                                                                    | `Provider`, `Use`, `Number of users`, `Frequency`                                            |
| Prof. Travel — Plane/Train | locked, not deletable                                                                    | `From`, `To`, `Date`, `Number of trips`, `Traveler`                                          |
| Purchase                   | locked, not deletable                                                                    | `Item Description`, `Supplier`, `UNSPSC description`, `Quantity`, `Total Amount`, `Currency` |
| Purchase — Centralized     | locked, not deletable                                                                    | `Item Description`, `Annual Consumption` (open clarification: align with Cloud/AI?)          |
| Research Facilities        | locked, not deletable                                                                    | `Research facilities`, `Use`, `Unit`                                                         |

User rows are always manually addable and always deletable. Two product
clarifications remain open on #951 (Centralized Purchases matrix shape;
delete-icon visibility on deactivated modules) — flagged below, not decided.

## Design brief (maintainer, #1554/#1747 review)

> "It should be 'permission based' using the 'source' column of the
> data_entry — create new data-entry permissions. It concerns only user
> principal and user standard because it's inside a module. Non-modifiable /
> non-deletable for imported module data; for equipment, authorized
> modification of some fields only; another permission for manual insertion by
> field name. Permissions are stored dynamically in the DB (with defaults
> created for the app, managed on the backoffice) and the system merges
> backend-defined permissions and DB-defined permissions."

This plan replaces the previous static-matrix plan on PR #1747 with that
permission-based design.

## Verified codebase facts that shape the design

- **RBAC today is 100% code-derived, nothing in DB.**
  `backend/app/models/user.py:67` (`calculate_user_permissions`) maps roles →
  a flat dict `{"modules.equipment/<unit>": ["view","edit","sync"], ...}` at
  request time. Roles come from ACCRED sync. There is **no permission table**
  anywhere; the new DB-stored permissions are net-new machinery.
- **Roles in scope**: `CO2_USER_PRINCIPAL` (unit breadth, all 8 modules) and
  `CO2_USER_STD` (own breadth, only `professional_travel` and
  `external_cloud_and_ai`) — `user.py:183-273`. Backoffice roles get zero
  `modules.*` keys, so they cannot call the module mutation routes at all;
  "concerns only principal/standard" therefore falls out of the existing
  route gate for free, no extra role check needed.
- **Module-level gate**: `check_module_permission_for_unit`
  (`backend/app/core/policy.py:644`) already runs at the top of `create`
  (`backend/app/api/v1/carbon_report_module.py:853`), `update` (`:974`) and
  `delete` (`:1048`). The new layer composes strictly AFTER it.
- **`DataEntry.source`** (`backend/app/models/data_entry.py:149`) is a
  nullable int; `DataEntrySourceEnum` (`data_entry.py:53`): `USER_MANUAL=0`,
  `CSV_MODULE_PER_YEAR=1`, `CSV_MODULE_UNIT_SPECIFIC=2`,
  `API_MODULE_PER_YEAR=3`, `API_MODULE_UNIT_SPECIFIC=4`,
  `EXTERNAL_INTEGRATION=5`.
- **GOTCHA — manual creates never stamp `source`.** `USER_MANUAL` is
  referenced nowhere except its enum definition. The UI create path
  (`CarbonReportModuleWorkflow.create` →
  `DataEntryService.create`, `backend/app/services/data_entry_service.py:112`)
  passes no `source`, so manual rows persist with `source = NULL`. Ingest
  paths DO stamp it (`base_csv_provider.py:779`, `:1500`, with
  `created_by_id = job_id`). So today: NULL ≈ manual, non-NULL = imported —
  but only if no pre-tracking imported rows exist with NULL (backfill risk,
  see Migration).
- **GOTCHA — the one existing provenance rule is dead code.**
  `_evaluate_resource_access_policy` (`backend/app/core/policy.py:122-236`,
  professional_travel `provider == "api"` → read-only) and its wrapper
  `check_resource_access` (`backend/app/services/authorization_service.py:146`)
  have **no callers in any API route** (only a docstring mention in
  `main.py:208`). It is precedent in shape only; nothing enforces per-row
  provenance today. The new layer supersedes it; the dead policy branch
  should be retired or delegated to the new resolver.
- **Update overlays blindly.** `CarbonReportModuleWorkflow.update`
  (`backend/app/workflows/carbon_report_module.py:141`) loads the existing
  entry (line 152) and merges `item_data` over persisted data — any field in
  the PATCH body wins. It already has the entry in hand, which makes it the
  natural enforcement point (no extra query).
- **`note` is patched through the same endpoint.** `ModuleTable.vue`
  `saveNote()` sends `PATCH {note}` (`frontend/src/components/organisms/module/ModuleTable.vue:523-533`).
  Notes must stay writable on locked imported rows (the Equipment
  power-change-request flow depends on it, issue #266) — `note` needs to be
  an always-allowed field, not part of the matrix.
- **Frontend gating today is module-level only.** `ModuleTable.vue:869-883`
  disables ALL editing via `modules.X` edit permission + validated state +
  backoffice disable; field editability is static per module config
  (`frontend/src/constant/module-config/*.ts`: `editableInline`, `readOnly`,
  `readOnlyWhenFilled`). **`source` is not serialized to the frontend** —
  `DataEntryResponse`/`DataEntryResponseGen`
  (`backend/app/schemas/data_entry.py:89-101`) don't carry it, so the UI
  cannot distinguish imported from manual rows at all today.
- **DB-config precedent**: `YearConfiguration`
  (`backend/app/models/year_configuration.py`) — a small config table with a
  JSON column, provider-scoped, edited from the backoffice. The new
  permission table follows this precedent.
- **Equipment fields** (`backend/app/modules/equipment/schemas.py:92-128`):
  `equipment_class` (kind), `sub_class` (subkind), `active_usage_hours_per_week`,
  `standby_usage_hours_per_week`, `name`, `note`. Usage hours are a live
  default from the Factor when unset (`schemas.py:210-232`) — an imported row
  with editable usage hours is exactly the "complete missing fields" case the
  brief describes.

## Design

### Concept: a third authorization axis

Authorization becomes three composed layers, each answering one question:

1. **RBAC (existing, unchanged)** — _may this user act on this module in this
   unit?_ `modules.X/<unit>` keys, `check_module_permission_for_unit`.
2. **Breadth (existing, unchanged)** — _which rows can they see/touch?_
   own/unit/global via `resolve_module_scope` + data filters.
3. **Data-entry permissions (NEW)** — _given this row's provenance, which
   operations and which fields?_ Named permissions resolved from
   backend defaults merged with DB overrides.

Layer 3 is deliberately **role-agnostic**: it keys on the row (module,
submodule, provenance), not on the caller. Since only principal/standard can
reach these routes (layer 1), the brief's "concerns only user principal and
user standard" is satisfied without duplicating role logic. If a future role
must bypass row locks (e.g. a backoffice correction flow), that becomes an
explicit bypass grant, not an implicit role check.

### Permission vocabulary and naming

The brief sketches `module_data_entry_non-modifiable`, `data_entry_***_to_complete`.
Improvements: (a) express grants positively (what IS allowed — deny-by-default
like the rest of the codebase), (b) keep the grantee scope OUT of the key
(provenance/module/submodule are structured columns, not string suffixes —
unlike `modules.X/<unit>` there is no need to flatten these into the key
since they are row properties, not user properties), (c) reuse the existing
dot-notation style.

Permission keys (the complete vocabulary):

| Key                           | Meaning                                                                                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `data_entry.create`           | Manual insertion of a new row (only meaningful on the `user` branch)                                                                     |
| `data_entry.delete`           | Delete the row                                                                                                                           |
| `data_entry.update.*`         | Update any data field                                                                                                                    |
| `data_entry.update.<field>`   | Update exactly this field (e.g. `data_entry.update.sub_class`)                                                                           |
| `data_entry.complete.<field>` | OPTIONAL, phase 3: write the field only while it is empty (fill-once — the "to_complete" idea; frontend precedent: `readOnlyWhenFilled`) |

Notes on the vocabulary:

- "Manual insertion **by field name**" (brief) is folded into
  `data_entry.create` + the `user`-branch update allow-list: the create form
  exposes exactly the fields the user branch may update. A distinct
  `data_entry.create.<field>` axis is not needed for the #951 matrix (every
  module's user rows expose one fixed field set) and would double the
  registry for no current behavior difference. Flagged as an accepted
  simplification (open question 4).
- `data_entry.complete.<field>` is specified but NOT required for #951 —
  Equipment usage hours are "editable", not "fill-once", per the issue. It is
  in the vocabulary so the backoffice UI and resolver support it from day one
  without a schema change (open question 3).

### Provenance derivation (the `source` → branch rule)

```python
class Provenance(str, Enum):
    USER = "user"          # source == USER_MANUAL
    IMPORTED = "imported"  # any CSV_* / API_* / EXTERNAL_INTEGRATION

def provenance_of(source: int | None) -> Provenance:
    if source is None or source == DataEntrySourceEnum.USER_MANUAL:
        return Provenance.USER
    return Provenance.IMPORTED
```

`NULL → USER` is required for today's manual rows (never stamped), but it is
a **fail-open** mapping for any pre-tracking imported rows. Two hardening
steps ship with this plan: stamp `USER_MANUAL` on the manual create path
(bug fix), and backfill NULL-source rows created by ingestion jobs
(Migration step 2). Grouping all non-manual sources into one `imported`
branch matches the #951 matrix exactly (it never distinguishes CSV from API);
per-source granularity can be added later as extra enum values in the
override table without schema change.

### Backend-defined defaults (the code layer)

New file `backend/app/core/data_entry_permissions.py`:

```python
@dataclass(frozen=True)
class BranchGrants:
    create: bool                       # user branch only; ignored on imported
    delete: bool
    update: frozenset[str] | Literal["*"] | None   # None = no update at all

DEFAULT_GRANTS: dict[tuple[ModuleTypeEnum, DataEntryTypeEnum | None, Provenance], BranchGrants]
```

One entry per (module, submodule-or-None, provenance), encoding the #951
matrix. `None` submodule = applies to all `data_entry_type`s of the module;
a row with an explicit submodule is more specific and wins (needed e.g. for
Buildings, where combustion and rooms differ, and Purchase, where
`purchases_centralized` differs from the other purchase types).

Equipment defaults (the flagship case):

```python
(equipment, None, IMPORTED): BranchGrants(
    create=False, delete=False,
    update=frozenset({"sub_class",
                      "active_usage_hours_per_week",
                      "standby_usage_hours_per_week"})),
(equipment, None, USER): BranchGrants(
    create=True, delete=True,
    update=frozenset({"equipment_class", "sub_class",
                      "active_usage_hours_per_week",
                      "standby_usage_hours_per_week", "name"})),
```

`note` is NOT listed anywhere: it is metadata, always writable (constant
`ALWAYS_WRITABLE_FIELDS = {"note"}` in the same file), preserving the
comment/power-request flow on locked rows.

Field names in the registry are validated at import time against each
handler's `update_dto` model fields (`BaseModuleHandler` registry) — a typo'd
field name fails CI, not production.

### DB-defined overrides (the dynamic layer)

New table `data_entry_permissions` (migration):

| column                      | type                                                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `id`                        | PK                                                                                                                         |
| `module_type_id`            | int, indexed (ModuleTypeEnum)                                                                                              |
| `data_entry_type_id`        | int NULL (NULL = whole module)                                                                                             |
| `provenance`                | enum `user` / `imported`                                                                                                   |
| `permission`                | text — one vocabulary key (`data_entry.delete`, `data_entry.update.sub_class`, `data_entry.update.*`, `data_entry.create`) |
| `allow`                     | bool — True grants, False revokes                                                                                          |
| `updated_by_id`             | FK users.id NULL                                                                                                           |
| `created_at` / `updated_at` | timestamps                                                                                                                 |

Unique on (`module_type_id`, `data_entry_type_id`, `provenance`, `permission`).

**Merge / precedence** (deny-by-default, most-specific-wins):

1. Start from `DEFAULT_GRANTS` for (module, submodule, provenance) —
   submodule-specific default beats module-wide default.
2. Apply DB rows for the module-wide scope (`data_entry_type_id IS NULL`):
   `allow=True` adds the permission, `allow=False` removes it.
3. Apply DB rows for the exact submodule — these beat module-wide rows.
4. `data_entry.update.*` grants/revokes the whole update axis; per-field rows
   then fine-tune on top (a `update.*` revoke + one `update.sub_class` allow
   yields exactly one editable field).

**Defaults stay in code; the DB stores only deltas.** This is the key
divergence from "seed all defaults into the DB": seeding copies would drift
from code on every release and make "what changed vs default" invisible. With
delta-only storage, a fresh deployment is correct with an empty table, the
backoffice shows _effective = default ⊕ overrides_ with a "reset to default"
that just deletes rows, and code-default evolution ships like any other code
change. (Trade-off flagged in open question 1, since the brief said
"defaults created for the app on the backoffice?" with a question mark.)

**Resolution + caching.** `EffectivePolicyResolver` (same core file): loads
all override rows once per process into an in-memory cache keyed by
(module, submodule, provenance) with a short TTL (60 s) — the table is tiny
(tens of rows) and near-static; a TTL avoids cross-worker invalidation
machinery. Backoffice writes bust the local cache immediately; other workers
converge within the TTL. Exposes:

```python
async def get_effective_policy(module_type, data_entry_type, source) -> RowPolicy
# RowPolicy = {create: bool, delete: bool, editable_fields: frozenset[str] | "*"}
```

### Backend enforcement points

All three live in `CarbonReportModuleWorkflow`
(`backend/app/workflows/carbon_report_module.py`) — after the route-level
RBAC gate, before the service write; the workflow already has the loaded
entry and the module context, so no extra queries:

1. **`update` (workflow line ~152, entry already loaded).** Compute
   `policy = get_effective_policy(module, entry.data_entry_type, entry.source)`.
   Reject 403 (structured detail: `{"code": "FIELD_NOT_EDITABLE", "fields": [...]}`)
   when `item_data` contains a key outside
   `policy.editable_fields ∪ ALWAYS_WRITABLE_FIELDS` **whose value differs
   from the persisted value** — value-diffing (not key-presence) because edit
   dialogs may echo the full row back; an echoed unchanged locked field must
   not 403. Keys not in the handler's `update_dto` are already rejected by
   validation and stay out of scope.
2. **`delete` (workflow `delete`, line ~237).** Load the entry (moves the
   existing fetch in `DataEntryService.delete` up, or fetch here), 403 if
   `not policy.delete`. The route already maps `PermissionError` → 403
   (`carbon_report_module.py:1102-1109`).
3. **`create` (workflow `create`).** 403 if `not policy_for(USER).create`;
   on success **stamp `source=DataEntrySourceEnum.USER_MANUAL` and
   `created_by_id=current_user.id`** — fixing the never-stamped bug. Restrict
   accepted fields to the USER branch's editable set (+ always-writable),
   consistent with "manual insertion by field name".

Bulk ingestion paths (`bulk_create`, `bulk_copy`, `bulk_delete_by_source`)
are intentionally NOT gated — they are the system writing imported data, the
very thing the policy protects from users.

Retire the dead professional_travel branch of
`_evaluate_resource_access_policy` (`policy.py:170-225`) in the same PR or a
follow-up: its `provider == "api"` intent is subsumed by the
`imported`-branch lock (verify travel API ingest stamps
`API_MODULE_PER_YEAR`; it does — `professional_travel_api_provider.py`).

### API surface for the frontend

The frontend must learn effective permissions without re-implementing the
matrix (same principle as `FlatUserPermissions`,
`frontend/src/utils/permission.ts`):

1. **Submodule payload carries both branches.** Extend `SubmoduleResponse`
   (list endpoint `get_submodule`, `carbon_report_module.py:634`) with:

   ```json
   "data_entry_policies": {
     "user":     {"create": true,  "delete": true,  "editable_fields": ["equipment_class", "sub_class", ...]},
     "imported": {"create": false, "delete": false, "editable_fields": ["sub_class", "active_usage_hours_per_week", "standby_usage_hours_per_week"]}
   }
   ```

2. **Each row carries its branch.** Add `provenance: "user" | "imported"`
   (computed from `source` at serialization) to `DataEntryResponseGen` /
   `DataEntryResponse` / `HeadcountItemResponse`. One string per row + one
   policy object per table keeps payloads flat (vs. per-row field lists,
   which repeat the same frozenset N times — the approach in the old plan,
   discarded).

3. No separate permissions endpoint needed: the table page already fetches
   the submodule payload; the create form uses the `user` branch of the same
   payload. (If a standalone endpoint is later wanted for the backoffice
   editor, it reads the same resolver.)

### Frontend gating

- `ModuleTable.vue`: per-row `rowPolicy = policies[row.provenance]`;
  - delete icon (`:210`) hidden/disabled when `!rowPolicy.delete` (existing
    `isDisabled` module-level gate stays AND-ed on top);
  - inline-editable cells (`col.editableInline`, `:141`) render read-only
    when `col.id ∉ rowPolicy.editable_fields`;
  - edit dialog: pass `disabledFields` to `ModuleForm.vue` so out-of-policy
    inputs are disabled (fields stay visible — users should see the values);
  - note button: unchanged (never policy-gated).
- `ModuleForm.vue` (create mode): render only fields in the `user` branch
  `editable_fields` (+ note); hide the Add button entirely when
  `policies.user.create` is false.
- Static config (`module-config/*.ts` `editableInline`/`readOnly`) remains
  the UI-layout default; effective editability = static config AND policy.
  Do NOT delete the static flags — they encode layout concerns (e.g.
  Buildings `Unit` never editable even on user rows).
- Types in `frontend/src/utils/permission.ts` (or a sibling
  `dataEntryPolicy.ts` leaf): `DataEntryPolicies`, `RowPolicy`, helper
  `isFieldEditable(policies, provenance, fieldId)` — unit-testable, store-free.

### Backoffice management UI (phase 2)

New section under the existing superadmin-only `backoffice.configuration`
permission (no new backoffice permission key needed):

- Read view: matrix per module/submodule/provenance showing **effective**
  grants, with per-cell badge default vs overridden.
- Write: toggling a cell writes/updates an override row; "reset to default"
  deletes the override rows for that scope.
- Endpoints (`backend/app/api/v1/backoffice.py` or a new
  `backoffice_permissions.py`), gated by
  `has_permission(perms, "backoffice.configuration", "edit")`:
  - `GET /v1/backoffice/data-entry-permissions` → defaults + overrides + effective
  - `PUT /v1/backoffice/data-entry-permissions` (upsert override rows)
  - `DELETE /v1/backoffice/data-entry-permissions?...` (reset scope)
- Audit: reuse the versioning service pattern (`AuditChangeTypeEnum`) for
  override changes — who changed which grant when.

Phase 2 is optional for shipping #951: with an empty override table the
system enforces the code defaults, which ARE the #951 matrix. This decouples
the user-facing behavior (must-have) from the admin tooling (nice-to-have).

## Where the brief collides with the existing code (critical assessment)

1. **"Stored dynamically in the DB … merges backend and DB permissions" vs. a
   fully code-derived RBAC.** Nothing in the current system persists
   permissions (`user.py:67` derives everything from ACCRED roles per
   request). The merge requirement is honored, but scoped to THIS layer only:
   role→module permissions stay code-derived. Extending DB-dynamism to
   `modules.*` grants would fight the ACCRED role sync and is explicitly out
   of scope.
2. **"Using the source column" is sound but the column is dirty.** Manual
   entries have `source = NULL` (`USER_MANUAL` never stamped anywhere;
   `data_entry_service.py:112-138` only sets it when a caller passes it, and
   the UI workflow never does). The design tolerates NULL (→ `user` branch)
   but ships the stamping fix + a backfill; without the backfill, any
   pre-tracking imported rows would become editable/deletable (fail-open).
3. **"A permission for manual insertion by field name."** Implemented as
   `data_entry.create` + the user-branch field allow-list rather than
   per-field create permissions — the #951 matrix never needs a field
   creatable-but-not-updatable (or vice versa). Accepted simplification,
   reversible later by adding `data_entry.create.<field>` rows (vocabulary
   and table schema already accommodate it).
4. **"module_data_entry_non-modifiable non-deletable" (negative grants).**
   Inverted to positive grants with deny-by-default, matching
   `has_permission` semantics everywhere else in the codebase
   (`utils/permissions.py:37`). Negative expression survives only as
   `allow=False` override rows (revoking a code default).
5. **The one precedent for per-row provenance rules is dead code** —
   `_evaluate_resource_access_policy`'s `provider=="api"` rule has no route
   callers. Good news: no behavioral conflict to migrate; bad news: nothing
   to reuse — enforcement is genuinely new, and Prof. Travel API rows are
   editable today (a live bug #951 fixes).
6. **`note` via the same PATCH route** would be bricked on imported rows by a
   naive allow-list — hence `ALWAYS_WRITABLE_FIELDS`. Any future
   metadata-ish field (e.g. tags) joins that set, not the matrix.
7. **Equipment `to_response` merges factor values into fields**
   (`equipment/schemas.py:242-271`): `sub_class` displays factor-preferred.
   Frontend must gate on the FIELD id, backend on the persisted `data` key —
   they match (`sub_class`), but tests must cover the "edit a
   factor-displayed value on an imported row" path explicitly.

## Compared with the previous plan (PR #1747)

**Kept:**

- The two-layer composition: provenance rules run strictly AFTER
  `check_module_permission_for_unit`; no new `modules.*` key.
- The #951 matrix content itself, now as `DEFAULT_GRANTS` instead of a
  hardcoded final matrix.
- Enforcement in the update/delete mutation paths; `create` stays
  user-branch.
- "Backend is source of truth, frontend consumes computed flags" principle,
  and the frontend touch-points (ModuleTable delete affordance, form field
  disabling).
- Both open product questions (Centralized Purchases, delete icon on
  deactivated modules).

**Discarded / replaced:**

- **Static-only matrix** (`data_entry_field_policy.py` with no DB, no
  backoffice control) → replaced by defaults + `data_entry_permissions`
  override table + resolver, per the design brief. The old plan had no
  dynamism at all — the core reason for this rewrite.
- **Per-row `editable_fields`/`deletable` on every row response** → replaced
  by per-submodule `data_entry_policies` (two branches) + per-row
  `provenance`; payload is O(1) instead of O(rows), and the create form gets
  the user branch for free.
- **`source is None → user branch` treated as safe** → challenged: the old
  plan didn't know manual creates never stamp `USER_MANUAL` and imported
  pre-tracking rows may be NULL. This plan adds the stamping fix + backfill.
- **Key-presence rejection on PATCH** → value-diff rejection (echoed
  unchanged fields from edit dialogs must not 403), plus the `note`
  always-writable carve-out the old plan missed.
- **No create gating** in the old plan (create "untouched") → now gated by
  `data_entry.create` and used to stamp provenance.
- The old plan's citation of the professional_travel `provider=="api"` policy
  as active enforcement precedent → corrected (dead code, retired here).

## Migration & rollout

1. **Alembic migration**: create `data_entry_permissions` (empty — defaults
   live in code). No seed rows.
2. **Backfill migration (data)**: `UPDATE data_entries SET source = 0 WHERE
source IS NULL AND created_by_id IN (SELECT id FROM users ...)`; rows with
   `created_by_id` matching ingestion job ids get the appropriate imported
   source (job → provider type join). Rows with NULL `created_by_id` AND NULL
   `source`: report count first — decision needed (open question 5). Ship as
   a reviewed, logged migration, not a silent one.
3. **Code fix**: stamp `USER_MANUAL` + `created_by_id` on the manual create
   path (independent, land first — it is a prerequisite bug fix).
4. **Backend enforcement + response fields** (one release) with an env-flag
   `DATA_ENTRY_POLICY_ENFORCE` supporting `log_only` for one deploy cycle on
   staging/prod — surfaces would-be 403s (from bots, scripts, stale UIs) in
   logs before flipping to `enforce`.
5. **Frontend gating** ships in the same release as backend `enforce` (a UI
   that shows editable fields which then 403 is a UX regression; log_only
   covers the gap).
6. **Phase 2**: backoffice management UI + audit.
7. **Phase 3 (optional)**: `data_entry.complete.<field>` semantics if product
   wants fill-once fields.

## Testing strategy

- **Unit — resolver** (`backend/tests/.../test_data_entry_permissions.py`):
  defaults-only resolution for every (module, submodule, provenance) in the
  #951 matrix (table-driven); override add / revoke / submodule-beats-module
  precedence; `update.*` wildcard interplay; NULL source → user branch;
  registry field names validated against handler DTOs.
- **Integration — routes**: per module: imported row — locked field PATCH →
  403 with `FIELD_NOT_EDITABLE`, allowed field PATCH → 200, echoed unchanged
  locked field → 200, `note` PATCH → 200, DELETE → 403; user row — full
  field PATCH + DELETE → 200; POST stamps `source=0`; Equipment imported:
  `sub_class`/usage-hours 200, `equipment_class` 403. Override tests: insert
  an `allow=False` row, assert flipped behavior + cache bust.
- **Migration test**: backfill classifies job-created vs user-created NULLs
  correctly on a fixture DB.
- **Frontend**: unit tests for `isFieldEditable`; component tests for
  ModuleTable (delete icon per provenance, inline cell read-only) and
  ModuleForm (disabled fields, hidden Add button).
- **Regression**: professional travel API rows (previously editable — the
  fixed live bug) and the Equipment note/power-request dialog on imported
  rows.

## Steps

- [ ] Fix manual-create stamping: `source=USER_MANUAL`, `created_by_id`
      (`workflows/carbon_report_module.py` → `DataEntryService.create`).
- [ ] `backend/app/core/data_entry_permissions.py`: `Provenance`,
      `provenance_of`, `BranchGrants`, `DEFAULT_GRANTS` (#951 matrix),
      `ALWAYS_WRITABLE_FIELDS`, import-time field validation.
- [ ] Migration: `data_entry_permissions` table + model
      (`backend/app/models/data_entry_permission.py`).
- [ ] Backfill migration for NULL-source rows (after counting/reporting).
- [ ] `EffectivePolicyResolver` (TTL cache, override merge, bust hook).
- [ ] Enforce in `CarbonReportModuleWorkflow.update/delete/create`
      (value-diff on update; `PermissionError`/403 mapping; env-flag
      `log_only` mode).
- [ ] Serialize `provenance` per row + `data_entry_policies` per submodule
      response (`schemas/data_entry.py`, `get_submodule` route).
- [ ] Retire dead `_evaluate_resource_access_policy` travel branch (or
      delegate to resolver).
- [ ] Frontend: policy types + `isFieldEditable`; `ModuleTable.vue` per-row
      delete/inline gating; `ModuleForm.vue` disabled/hidden fields + Add
      button gating.
- [ ] Backend + frontend tests per strategy above.
- [ ] Phase 2: backoffice endpoints + configuration UI + audit of overrides.

## Open questions (product decisions guessed — need sign-off)

1. **Defaults location**: this plan keeps defaults in code and stores only
   deltas in DB (empty table = spec behavior). The brief hints at "defaults
   created for the app on the backoffice?" — if you want defaults
   materialized as DB rows (seeded at migration/startup), say so; the
   resolver then reads DB-only and re-seeding/versioning of defaults must be
   designed (drift risk documented above).
2. **Who may edit overrides**: assumed superadmin-only via
   `backoffice.configuration`. Should CO2_BACKOFFICE_METIER get read (or
   write) access?
3. **Fill-once semantics**: is `data_entry.complete.<field>` (editable only
   while empty) actually wanted anywhere, or is plain field editability
   enough for the "to complete" idea? #951 never requires fill-once.
4. **Per-field create grants**: accepted simplification — create form fields
   = user-branch update allow-list. Confirm no module needs
   creatable-but-not-updatable fields (or the reverse).
5. **NULL-source backfill**: how to classify rows with `source IS NULL` and
   no resolvable creator? Proposal: default them to `imported` (fail-closed)
   after a count report — confirm.
6. **Unresolved from #951**: Centralized Purchases matrix — align with
   External Cloud/AI or keep the distinct 2-field shape? (`DEFAULT_GRANTS`
   blocked on this for `purchases_centralized`.)
7. **Unresolved from #951**: delete-icon visibility when a module is
   deactivated (interacts with the existing `isDisabled` gate in
   `ModuleTable.vue:876-883`).
8. **Standard users**: matrix applies identically to STD users (own-breadth,
   travel + cloud/AI only)? Assumed yes — breadth already restricts them to
   their own rows; provenance rules then apply on top.
9. **Scope of enforcement for `sync`/CSV re-upload flows**: per-year
   full-replace ingest deletes imported rows wholesale
   (`bulk_delete_by_source`) — assumed exempt from `data_entry.delete`
   (system operation). Confirm.
