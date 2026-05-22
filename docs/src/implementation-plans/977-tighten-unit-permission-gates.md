---
status: draft
issue: 977
last_updated: 2026-05-22
title: "Tighten unit-scoped permission gates"
summary: "Close three pre-existing permission soft-spots: 6 carbon_report endpoints + 3 unit_results endpoints get unit gating; remove the coarse modules.* fallback in files.py and data_sync.py."
---

## Problem

Issue [#977] surfaced three pre-existing permission soft-spots discovered while
shipping the PR #974 follow-up (`institutional_id` threading through the policy
layer for `carbon_report_module*` and `taxonomies`). Re-audited against current
`dev` on 2026-05-22; results below reflect ground truth, not the original issue
snapshot.

### Finding 1 — `backend/app/api/v1/carbon_report.py` (2 of 6 endpoints still open)

The original audit listed six endpoints with no gate. Four have since been gated
(they now call `require_unit_access` after loading the unit). Two endpoints
remain ungated — both resolve a unit indirectly via `carbon_report_id`:

| Endpoint | Function | Line | Status |
| --- | --- | --- | --- |
| `GET /unit/{unit_id}/` | `list_carbon_reports_by_unit` | 48 | gated (55) |
| `GET /unit/{unit_id}/year/{year}/` | `get_carbon_report_by_unit_and_year` | 61 | gated (69) |
| `POST /` | `create_carbon_report` | 78 | gated (85) |
| `GET /{carbon_report_id}` | `get_carbon_report` | 158 | gated (169) |
| `GET /{carbon_report_id}/modules/` | `list_carbon_report_modules` | 177 | **open** |
| `PATCH /{carbon_report_id}/modules/{module_type_id}/status` | `update_carbon_report_module_status` | 203 | **open** |

The two open endpoints only verify the report exists; any logged-in user can
list module statuses or mutate them for any report.

### Finding 2 — `backend/app/api/v1/unit_results.py` (3 of 3 endpoints open)

All three endpoints take `unit_id` in the path but only depend on
`get_current_user`. The downstream `UnitTotalsService` performs no permission
checks (`user=current_user` is passed but unused for gating).

| Endpoint | Function | Line |
| --- | --- | --- |
| `GET /{unit_id}/results` | `get_unit_results` | 45 |
| `GET /{unit_id}/{year}/totals` | `get_unit_totals` | 57 |
| `GET /{unit_id}/yearly-validated-emissions` | `get_validated_emissions` | 87 |

### Finding 3 — coarse `is_permitted("modules.*", action)` fallback

Used as the unit-agnostic "OR" branch when the `backoffice.data_management.*`
primary gate misses. The `fnmatch` glob does match scoped keys
(`modules.X/0184`), so the call succeeds for scoped users — but it answers
"does this user have <action> on at least one module on at least one unit",
which is not the same as "for the unit referenced in this request". A
principal of unit A with `modules.headcount/A` edit can write or delete a
file associated with unit B.

Verified call sites (current `dev`, line numbers reverified 2026-05-22):

- `backend/app/api/v1/data_sync.py:728` — sync action
- `backend/app/api/v1/data_sync.py:1309` — view action
- `backend/app/api/v1/files.py:129` — view (download)
- `backend/app/api/v1/files.py:207` — view (list)
- `backend/app/api/v1/files.py:300` — edit (upload)
- `backend/app/api/v1/files.py:348` — edit (delete)

## Decision applied

Confirmed by the user before plan drafting; do not re-litigate during
implementation:

- **Findings 1 + 2** — add unit-loading + permission check to the 2 open
  `carbon_report.py` endpoints and all 3 `unit_results.py` endpoints. Lift the
  helper `_check_module_permission_for_unit` (currently
  `backend/app/api/v1/carbon_report_module.py:123-153`) to a shared location
  (`backend/app/core/policy.py`) so the same shape is available to
  `files.py` and `data_sync.py` after the fallback is removed.
- **Finding 3** — **remove** the `is_permitted("modules.*", ...)` coarse
  fallback in `files.py` and `data_sync.py` entirely. Routes must rely on the
  explicit `backoffice.data_management.*` (for bulk ops) or a unit-aware
  per-route gate. No `is_permitted_for_unit` shim — single path only.
  (Honors memory "no backward compat" / "no dual-path bloat" — project is
  pre-v1.x.)

## Files to change

### Source — helper to lift

- `backend/app/api/v1/carbon_report_module.py:123-153` —
  `_check_module_permission_for_unit`. Helper signature is already correct
  (`*, current_user, module_id, action, db, unit_id`) and returns the loaded
  `Unit`.

### Destination — shared helper

- `backend/app/core/policy.py` — add `check_module_permission_for_unit` next to
  `require_unit_access` (line 587) and `check_module_permission` (line 524).
  Drop the leading underscore on lift (now public). Adjust the import in
  `carbon_report_module.py` to consume from `app.core.policy`.

### Routes to gate

- `backend/app/api/v1/carbon_report.py`
  - `list_carbon_report_modules` (177) — load `report.unit_id` → `unit` →
    `require_unit_access(current_user, unit)` before delegating to
    `CarbonReportModuleService`. Mirror the shape of `get_carbon_report`
    (158-169).
  - `update_carbon_report_module_status` (203) — same shape: resolve
    `report.unit_id`, load unit, gate before mutating.

- `backend/app/api/v1/unit_results.py`
  - `get_unit_results` (45) — note this endpoint currently returns a hardcoded
    mock dict (`unit_results` at line 16). The `unit_id` path parameter is not
    even consumed. Gate still applies: load unit from `unit_id`, call
    `require_unit_access`. Mock-data return shape is out of scope.
  - `get_unit_totals` (57) — load unit, `require_unit_access`, then call
    service.
  - `get_validated_emissions` (87) — same.

### Routes to de-fallback (remove `modules.*`)

- `backend/app/api/v1/data_sync.py`
  - `:728` (within the sync handler) — drop the
    `or await is_permitted(current_user, "modules.*", "sync")` branch.
    Surviving gate: `backoffice.data_management.sync` (primary). If any
    sync-action handler is called by a scoped (non-backoffice) user today, the
    plan's implementation step must pick its new primary gate — flagged as an
    open question.
  - `:1309` (within the view handler) — drop the `modules.*` view fallback.
    Surviving gate: `backoffice.data_management.view`.
  - Update the surrounding docstring / `HTTPException(detail=...)` messages
    that mention `modules.*` (lines 734, 1315).
- `backend/app/api/v1/files.py`
  - `:129` (download), `:207` (list), `:300` (upload), `:348` (delete) — drop
    the `modules.*` branch in all four. Surviving gate per route is the
    `backoffice.data_management.{view,edit}` primary already present in the
    `await is_permitted(...)` clause immediately above each fallback. Update
    the docstrings (lines 112, 191, 293, 341) and HTTPException details
    (136, 214, 307, 355) to drop the "or modules.* …" prose.

## Approach

### 4.1 Lift the helper (refactor, no behavior change)

1. Move `_check_module_permission_for_unit` (`carbon_report_module.py:123-153`)
   into `backend/app/core/policy.py` as `check_module_permission_for_unit`
   (public). Keep the signature and behavior identical:
   ```python
   async def check_module_permission_for_unit(
       *, current_user, module_id, action, db, unit_id
   ) -> Unit
   ```
2. Update `carbon_report_module.py` to import from `app.core.policy`. Delete
   the local definition. Confirm all existing call sites
   (`carbon_report_module.py:288, 384, 440, 614, 725, 792, …`) still pass.
3. This step alone must keep all existing tests green — it is a pure
   refactor. Verify with the targeted permission-scope e2e tests in
   step 6 (Verification).

### 4.2 Gate `carbon_report.py` (2 endpoints) and `unit_results.py` (3 endpoints)

Recommendation: use `require_unit_access` (not the module-level helper) for
both files. Rationale:

- These endpoints are **unit-scoped reports**, not module-data CRUD. There is
  no `carbon_report` bucket in `ModuleType` (`backend/app/models/module_type.py:10-32`
  — buckets are `headcount`, `professional_travel`, `buildings`,
  `equipment_electric_consumption`, `purchase`, `research_facilities`,
  `external_cloud_and_ai`, `process_emissions`). Picking a module to anchor
  the check would be arbitrary.
- `require_unit_access` already gates on `institutional_id` for principals
  while letting backoffice / superadmin pass — exactly the desired shape.
- Mirrors the four already-gated endpoints in `carbon_report.py` (lines 55,
  69, 85, 169).

Concrete edits:

1. `carbon_report.py::list_carbon_report_modules` — after the existing report
   existence check (lines 190-193), add:
   ```python
   unit = await db.get(Unit, report.unit_id)
   require_unit_access(current_user, unit)
   ```
2. `carbon_report.py::update_carbon_report_module_status` — same insert after
   lines 218-222. Must precede the mutating `module_service.update_status`
   call.
3. `unit_results.py::get_unit_results` — at the top of the function: load
   unit, gate, then return mock (the function will be rewritten when the
   mock is replaced — out of scope for #977 but the gate ships now).
4. `unit_results.py::get_unit_totals` — top of function, before the service
   call.
5. `unit_results.py::get_validated_emissions` — top of function, before the
   service call.
6. Each file needs added imports: `from app.core.policy import require_unit_access`,
   `from app.models.unit import Unit` (the imports may already exist in
   `carbon_report.py`; verify and don't double-add).

### 4.3 Remove the `modules.*` fallback from `files.py` and `data_sync.py`

The plan does **not** add the lifted `check_module_permission_for_unit` to
these routes — it removes the fallback and keeps the surviving
`backoffice.data_management.*` primary. Per-route audit:

| File:Line | Primary gate (today) | Action |
| --- | --- | --- |
| `data_sync.py:728` (sync) | `backoffice.data_management.sync` | drop `modules.*` fallback |
| `data_sync.py:1309` (view) | `backoffice.data_management.view` | drop `modules.*` fallback |
| `files.py:129` (download) | `backoffice.data_management.view` | drop `modules.*` fallback |
| `files.py:207` (list) | `backoffice.data_management.view` | drop `modules.*` fallback |
| `files.py:300` (upload) | `backoffice.data_management.edit` | drop `modules.*` fallback |
| `files.py:348` (delete) | `backoffice.data_management.edit` | drop `modules.*` fallback |

If during implementation any of these routes turns out to be exercised by a
non-backoffice user today (scoped principal hits the route in
production), the implementation phase must either:

- promote the route to a `check_module_permission_for_unit` gate (extracting
  the unit and module identity from the request body / file metadata), or
- accept that the route is backoffice-only (single primary gate). Decision
  to be recorded in the implementation PR, not here. See Open Questions.

### 4.4 Keep `is_permitted` glob behavior (do not refactor)

`is_permitted` (`backend/app/core/security.py:196-221`) keeps its existing
glob behavior. The bug was at the call site (passing `"modules.*"`), not in
the function. Restricting the function's glob behavior would be a separate
refactor and is **out of scope** for #977 — flagged as an Open Question.

## Tests

All tests go in `backend/tests/integration/v1/test_permission_scope_e2e.py`
(or a sibling file in the same directory) and use the existing helpers
`_principal`, `_std`, `_backoffice`, `_superadmin`. Each test uses
parametrize or three explicit functions for the three-actor matrix:

- cross-unit principal → 403
- in-unit principal → 200
- global backoffice → 200

Proposed test functions (one per endpoint touched):

```python
# carbon_report.py
async def test_list_carbon_report_modules_scoped()
async def test_update_carbon_report_module_status_scoped()

# unit_results.py
async def test_get_unit_results_scoped()
async def test_get_unit_totals_scoped()
async def test_get_validated_emissions_scoped()

# files.py — verify modules.* fallback removed
async def test_files_download_rejects_scoped_principal_without_backoffice()
async def test_files_list_rejects_scoped_principal_without_backoffice()
async def test_files_upload_rejects_scoped_principal_without_backoffice()
async def test_files_delete_rejects_scoped_principal_without_backoffice()

# data_sync.py — same
async def test_data_sync_sync_rejects_scoped_principal_without_backoffice()
async def test_data_sync_view_rejects_scoped_principal_without_backoffice()
```

Notes:
- The `files.py` / `data_sync.py` tests must specifically construct a
  principal who has `modules.<x>/A` perms (the old fallback admit-set) and
  assert 403 against a route now requiring `backoffice.data_management.*`.
  Without that assertion the regression is not pinned (memory: "Bugs ship
  with regression tests" — every fix must have a test that would have
  caught it).
- Helper lift (4.1) is exercised by the existing
  `test_permission_scope_e2e.py` invariants — no new test required, but the
  full file must pass after the import path change.

## Verification

```bash
cd backend
uv run pytest tests/integration/v1/test_permission_scope_e2e.py -xvs
uv run pytest tests/integration/v1/ -k "carbon_report or unit_results or files or data_sync" -xvs

# Manual smoke (after make backend-dev):
make backend-dev
# 1. Cross-unit principal — expect 403:
curl -H "Authorization: Bearer $UNIT_A_PRINCIPAL_TOKEN" \
  http://localhost:8000/v1/unit_results/<unit-B-id>/results
curl -H "Authorization: Bearer $UNIT_A_PRINCIPAL_TOKEN" \
  -X PATCH http://localhost:8000/v1/carbon_report/<report-on-unit-B>/modules/1/status \
  -d '{"status": 2}'

# 2. Global backoffice — expect 200:
curl -H "Authorization: Bearer $BACKOFFICE_TOKEN" \
  http://localhost:8000/v1/unit_results/<any-unit-id>/results

# 3. Scoped principal with modules.headcount/A but no backoffice.data_management.view
#    on /v1/files/... against unit B — expect 403 (was 200 with old fallback):
curl -H "Authorization: Bearer $UNIT_A_MODULE_TOKEN" \
  http://localhost:8000/v1/files/...
```

Implementation PR must record actual response codes in the description so
reviewers can confirm the gates landed.

## Open questions

- **(a) Module-level vs unit-level for `carbon_report.py` / `unit_results.py`** —
  recommendation is `require_unit_access` (justified in §4.2). If reviewers
  prefer a module-level check, the question becomes *which* `ModuleType`
  bucket anchors a unit-scoped report. There is no `carbon_report` bucket
  today. Default to `require_unit_access` unless an alternative is raised
  in the implementation PR.
- **(b) Routes relying only on the `modules.*` fallback** — confirm during
  implementation that no production usage flows through a scoped user
  without `backoffice.data_management.*`. If any does, the answer is either
  promotion to `check_module_permission_for_unit` (with route-specific
  module-id resolution) or accepting the route is backoffice-only. Decision
  belongs in the implementation PR.
- **(c) Rename on lift** — `_check_module_permission_for_unit` is a poor
  name for a helper that now also serves non-module unit checks via its
  re-use sites. Proposal: name the lifted version
  `check_module_permission_for_unit` (drop the underscore, keep the
  `module_` because the helper still takes a `module_id` arg). If the
  implementation phase decides to also use the helper for non-module unit
  checks, rename further.
- **(d) Restrict `is_permitted` glob support entirely** — separate refactor,
  out of scope for #977. The function's glob behavior is not itself broken
  (it does what it advertises); only the call-site usage of `"modules.*"`
  was semantically wrong. File a follow-up issue if the team wants to
  retire glob support.

[#977]: https://github.com/EPFL-ENAC/co2-calculator/issues/977
