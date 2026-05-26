---
status: in_progress
issue: 459
last_updated: 2026-05-26
title: "Backoffice ACCRED affiliation scoping"
summary: "Scope backoffice.* permissions by ACCRED-provided affiliation so each backoffice manager sees only their sub-perimeter."
---

## Phase 2 (2026-05-26): production sortpath shape + frontend gate

Phase 1 (PR #1271) shipped against a single-token sortpath assumption ("Engineering"). The first real ACCRED payloads showed sortpath is a space-separated 4-level path (e.g. `"EPFL ENAC ENAC-SG ENAC-IT"`), so the affiliation-suffixed permission keys looked like `backoffice.users/EPFL ENAC ENAC-SG ENAC-IT` — readable but unusable as a sub-perimeter token. Phase 2 resolves Open Question #1 and closes the Phase 1 frontend follow-up.

**Backend — LVL3 trim** (`backend/app/providers/role_provider.py`):

- ACCRED sortpath is now split on whitespace and reduced to LVL3 (index 2, e.g. `"ENAC-SG"`) before being assigned to `RoleScope.affiliation`. The cut-off was confirmed against real EPFL payloads: LVL3 is the unit-of-interest for backoffice scoping; LVL4 is too granular and LVL1/2 are too broad.
- Authorizations whose sortpath has fewer than 3 levels are logged at warning level and dropped (cannot resolve a meaningful affiliation). Picked "strict skip" over "use deepest token" to surface upstream data issues rather than silently miscategorise users.
- Module-level constant `AFFILIATION_LEVEL = 3` documents the level choice; tests pin the trim (`test_accred_fetch_roles_with_backoffice_metier` uses a 4-token sortpath) and the skip path (`test_accred_backoffice_metier_short_sortpath_skipped`).

**Backend — principal no longer grants backoffice.users.edit** (`backend/app/models/user.py`):

- The Phase 1 plan inherited a grant where `CO2_USER_PRINCIPAL` emitted an un-scoped `backoffice.users: ["edit"]` "so principals could assign std roles." Per the current role spec (Standard/Principal are unit-area roles; Backoffice Admin/Super Admin are the only backoffice-area roles), this was a leak: a principal could pass `has_permission("backoffice.users", "edit", any_scope=True)` and reach backoffice surfaces. Removed.
- Knock-on test updates: `test_user_principal_unit_scope` now asserts no `backoffice.*` keys leak from principal-only roles; the `TestRoleCompositionKeys` cases for `principal-A`, `std+principal-same-unit`, `principal-A+std-B` drop the `{backoffice.users}` allowance and move it to `forbidden`.

**Frontend — generic back-office area gate** (`frontend/src/utils/permission.ts`, `frontend/src/stores/auth.ts`, `frontend/src/components/layout/Co2Header.vue`):

- Added `hasBackOfficeAreaPermission(permissions, action)` which scans for any `backoffice.*` OR `system.*` key (bare or `/<aff>`-suffixed) granting `action`. Both prefixes are matched because the back-office area covers both `backoffice.*` features (reporting, users, data management, documentation) and `system.*` features (Super Admin tabs: configuration, pipeline operations, logs). Exposed via `authStore.hasUserBackOfficeAreaPermission(action)`.
- `Co2Header.vue`'s `hasBackOfficeAccess` computed now calls the broader helper. Affiliation-scoped users (whose only key shape is `backoffice.X/ENAC-SG`) AND Super Admins with only `system.*` grants both see the entry button.
- Comment fix at `backoffice_reporting.py:_affiliation_predicate` to reflect the real sortpath shape ("space-separated 4-level hierarchy; `role_provider.py` extracts LVL3").

**Frontend — path-specific any-scope guard** (`frontend/src/utils/permission.ts`, `frontend/src/stores/auth.ts`, `frontend/src/router/guards/permissionGuard.ts`, `frontend/src/components/layout/Co2Sidebar.vue`):

- Closes the Phase 1 frontend follow-up. Added `hasAnyScopePermission(permissions, path, action)` mirroring the backend's `has_permission(..., any_scope=True)`: matches the bare path OR any `path/<*>` variant. Exposed via `authStore.hasUserAnyScopePermission(path, action)`.
- `requirePermission(path, action)` in `permissionGuard.ts` now uses the any-scope check, so an `ENAC-SG`-scoped backoffice admin can enter `back-office/*` routes despite holding only `backoffice.users/ENAC-SG`. The guard now also emits `console.warn` on denial — previously the unauthorized redirect was silent, making misconfigured permissions hard to diagnose.
- `Co2Sidebar.vue`'s `hasBackOfficeEditPermission` switched to the any-scope check (same root cause).
- Module routes are unaffected — they use `requireModuleEditPermission` (workspace-scoped), which keeps unit isolation. The any-scope mode is documented as "do not use for unit-data routes" in `permission.ts`.

**Regression coverage**: `frontend/tests/unit/permission.spec.ts` — 11 cases total: 7 for `hasBackOfficeAreaPermission` (scoped/bare backoffice keys, reporting-only scoped user, `system.*` key, action mismatch, module-only user, null permissions) + 4 for `hasAnyScopePermission` (scoped edit, bare edit, path isolation against module keys, prefix isolation against `backoffice.users_other`).

**Backend — open the broader `/backoffice/*` surface to scoped users** (`backend/app/api/v1/backoffice.py`, `backend/app/utils/scoping.py`):

- Reverses the Phase 1 "left explicit" decision after evidence that the strict gate blocks normal navigation for ENAC-SG (and other LVL3) backoffice admins. All six endpoints — `/units`, `/export`, `/years`, `/report/usage`, `/report/detailed`, `/report/results` — drop `Depends(require_permission(...))` for `Depends(get_current_active_user)` + inline `gate_backoffice(user, action)` from the new `app.utils.scoping` module.
- Server-side affiliation enforcement: `narrow_path_affiliation(filters.path_affiliation, is_global, affiliations)` intersects the caller-supplied `path_affiliation` query param with the caller's affiliation set; a scoped user cannot escape their scope by passing a foreign affiliation. Empty intersection → empty result (defence-in-depth, mirroring the existing `/backoffice-reporting/units` pattern).
- `/years` had no `path_affiliation` filter at all, so the query was extended with `JOIN units ON CarbonReport.unit_id = units.id` + the affiliation predicate when the caller is scoped. Global callers keep the original distinct-year query (no join).
- `_affiliation_predicate` and the gate helper moved out of `backoffice_reporting.py` into `app/utils/scoping.py` (`build_affiliation_predicate`, `gate_backoffice`, `narrow_path_affiliation`). `backoffice_reporting.py` now imports the shared versions; behaviour unchanged (Phase 1 e2e tests still green).
- Regression coverage: `TestBackofficeYearsAffiliationScoping` in `backend/tests/integration/v1/test_permission_scope_e2e.py` — 5 cases pinning global/scoped/cross-affiliation/std-denied/principal-denied behavior. The principal-denied case is the explicit pin for the Phase 2 grant removal (`CO2_USER_PRINCIPAL` no longer leaks `backoffice.users.edit`).

**Backend — sweep remaining `data_sync.py` strict gates + tighten data_management action set** (`backend/app/api/v1/data_sync.py`, `backend/app/utils/scoping.py`, `backend/app/models/user.py`):

- Added FastAPI dependency factory `require_any_scope(action, anchor_path)` in `scoping.py` — drop-in replacement for `require_permission` for routes that only need the 403 gate (not the affiliation tuple). Converted 10 strict-gated `view`-action routes in `data_sync.py` (`/jobs/by-status`, `/jobs/year/{year}`, `/jobs/year/{year}/latest`, `/workers`, `/active-pipelines`, `/active-pipelines/year/{year}`, `/recalculation-status`, `/pipelines`, `/pipelines/{pipeline_id}`, plus a tenth view-gated endpoint). Sync-action routes (`/dispatch`, `/factor reupload`, etc., 6 total) stay on strict `require_permission` — they are Super-Admin-only per the role spec.
- Tightened the `CO2_BACKOFFICE_METIER` permission emission: scoped backoffice metier now gets `backoffice.data_management/<aff>: ["view", "export"]` only (was `["view", "edit", "export", "sync"]`). Matches the EPFL role spec — Backoffice Administrator has read/export but not write/sync on data_management; Super Admin keeps the full set on the bare key. Closes the latent leak where opening a sync route any-scope would have inadvertently granted scoped users pipeline-trigger / factor-mutation rights.
- Regression coverage: `TestBackofficeAffiliationScoping.test_affiliation_scope_emits_scoped_keys_only` now asserts the full action sets for all four scoped keys; new `test_scoped_backoffice_lacks_data_management_sync` and `test_superadmin_has_data_management_edit_and_sync` pin the asymmetry. The `TestActivePipelinesPerYearGate` e2e class already covers the any-scope gate pattern end-to-end.

---

## Delivered (Phase 1)

Shipped in PR #1271 on `feat/459-backoffice-accred-affiliation-scoping`. Divergences from the original plan:

- **URL prefix**: the affected endpoints are mounted at `/api/v1/backoffice-reporting/{affiliations,units}` (not `/api/v1/backoffice/...`). The plan referenced the file path `backend/app/api/v1/backoffice_reporting.py` correctly; only the public URL was misstated.
- **`as_scope_key` branching**: backoffice metier with `RoleScope(institutional_id=...)` falls back to un-scoped keys rather than emitting a meaningless `backoffice.users/<iid>`. ACCRED never produces this shape today (only `GlobalScope` or `RoleScope(affiliation=...)`), so the defensive un-scoped degrade is safer than introducing a key shape no consumer matches.
- **Permission helper**: added `derive_backoffice_affiliations(permissions, anchor_path)` in `backend/app/utils/permissions.py` to parse `(is_global, affiliations)` from the permission dict — both endpoints share it via `_gate_backoffice_users_view` in `backend/app/api/v1/backoffice_reporting.py`.
- **`path_name` predicate**: implemented as `concat(' ', coalesce(path_name, ''), ' ') ILIKE '% <aff> %'`, which covers both observed separators (`' > '` and plain space) in a single clause, handles NULL `path_name`, and avoids the `SV ↔ SVOPS` boundary bug.
- **Empty-affiliation semantic** (open question #6): chose `200 []` — the gate accepts (the user is a backoffice manager) and the predicate filters everything out.
- **Cross-endpoint blast radius** (open question #5): the broader `/api/v1/backoffice/*` surface (`backend/app/api/v1/backoffice.py`: list reporting units, exports; `backend/app/api/v1/data_sync.py`: sync endpoints; `backend/app/api/v1/factors.py`) still gates via `require_permission`, so affiliation-scoped users will now 403 on those routes. This is the security-correct posture (an SV manager has no business exporting global user lists or triggering global syncs) and is left explicit. Follow-up scoping for these endpoints, if needed, can reuse `_gate_backoffice_users_view` + `_affiliation_predicate`.

The four pinning tests in `TestBackofficeScopingCurrentBehavior` were replaced by `TestBackofficeAffiliationScoping` + `TestHasPermissionAnyScopeAffiliation` in `backend/tests/unit/utils/test_permissions.py`. The `test_backoffice_and_system_keys_never_scoped` invariant was split into a strict `system.*` invariant and a relaxed `backoffice.*` rule that allows non-digit (affiliation) suffixes. End-to-end coverage lives in `TestBackofficeAffiliationScopeEndToEnd` in `backend/tests/integration/v1/test_permission_scope_e2e.py`.

## Known follow-up (frontend)

`frontend/src/utils/permission.ts:hasPermission()` does a strict `path in permissions` lookup. After this PR, an affiliation-scoped backoffice user holds only `backoffice.users/<aff>` keys (no bare `backoffice.users`), so the following call sites will hide menu items and block navigation for them:

- `frontend/src/components/layout/Co2Header.vue:53` — backoffice header entry.
- `frontend/src/components/layout/Co2Sidebar.vue:23` — backoffice sidebar entry.
- `frontend/src/router/routes.ts` (8 occurrences) — backoffice route guards.

This is out of scope for this PR (backend-only per the issue scope), but is a hard prerequisite for affiliation-scoped backoffice users to actually USE the affiliation-filtered endpoints. Recommended fix: extend `hasPermission()` (or add a sibling `hasAnyScopePermission()`) to fall back to `path/<*>` keys when the bare key is absent, mirroring the backend `any_scope=True` mode. Track as a follow-up issue.

---

## Problem

`RoleScope.affiliation` exists on the user model (`backend/app/models/user.py:31`) and the ACCRED provider already populates it from the `reason.resource.sortpath` field of each `calco2.backoffice.metier` authorization (`backend/app/providers/role_provider.py:544-554`). However, the affiliation is currently ignored downstream:

- `as_scope_key()` returns `""` for any `RoleScope` with only an affiliation set (`backend/app/models/user.py:137-138, 142-143`), with an inline comment acknowledging the gap.
- `calculate_user_permissions()` emits a fixed, **unscoped** key set for `CO2_BACKOFFICE_METIER` — `backoffice.reporting`, `backoffice.users`, `backoffice.data_management`, `backoffice.documentation` — regardless of whether the role is `GlobalScope` or `RoleScope(affiliation=...)` (`backend/app/models/user.py:164-186`).
- `/backoffice/affiliations` and `/backoffice/units` (`backend/app/api/v1/backoffice_reporting.py:20-108`) gate on `require_permission("backoffice.users", "view")` and return **all active units** with no per-caller filtering.

Concrete impact: a Faculty SV backoffice manager whose ACCRED `sortpath` resolves to `"SV"` has the same blast radius as a global backoffice admin — they see STI, IC, ENAC, CDH, CDM units in the affiliation/unit dropdowns and reporting tables. This violates the EPFL accreditation model and the explicit ACCRED contract that backoffice roles are sub-perimeter-bound.

## Decision applied

Backoffice "sub-perimeter" comes from **ACCRED-provided affiliation(s) on the user**. Populate `RoleScope.affiliation` from ACCRED (already done); emit `backoffice.*/{affiliation}` keys; filter `/backoffice/affiliations`, `/backoffice/units`, and any backoffice reporting endpoints by the user's affiliations.

`GlobalScope` (superadmin, plus any backoffice role explicitly granted globally) continues to bypass affiliation filtering. Affiliation acts purely as a narrowing predicate on top of the existing permission gate.

## Files to change

- `backend/app/models/user.py`
  - `as_scope_key()` (lines 127-145): return `f"/{s.affiliation}"` instead of `""` when only `affiliation` is set.
  - `calculate_user_permissions()` (lines 164-186): for `CO2_BACKOFFICE_METIER` with `RoleScope(affiliation=...)`, emit `backoffice.reporting/{affiliation}`, `backoffice.users/{affiliation}`, `backoffice.data_management/{affiliation}`, `backoffice.documentation/{affiliation}`. `GlobalScope` keeps the bare keys.
- `backend/app/api/v1/backoffice_reporting.py`
  - `list_affiliations()` (lines 20-59): swap `require_permission("backoffice.users", "view")` for an inline gate that uses `has_permission(..., any_scope=True)`, then filter by the caller's affiliation set.
  - `list_units()` (lines 62-108): same gate change + same affiliation filter.
- `backend/tests/unit/models/test_user.py` (or the existing matching test file — locate during impl): add cases for `as_scope_key(RoleScope(affiliation="SV"))` → `"/SV"` and `calculate_user_permissions([backoffice_metier @ affiliation=SV])` emitting only the four `backoffice.*/SV` keys.
- `backend/tests/integration/v1/test_permission_scope_e2e.py`: add `_backoffice_scoped(affiliation)` helper and three new test methods (see Tests section).

Files explicitly **not** changed:

- `backend/app/providers/role_provider.py` — ACCRED → `RoleScope.affiliation` mapping is already in place (verified at lines 544-554; covered by `test_role_provider.py:301-335`).
- `backend/app/utils/permissions.py` — `has_permission(..., any_scope=True)` already supports the lookup pattern we need; no signature change.
- `backend/app/core/security.py` — `require_permission`/`is_permitted` keep their current shape; the backoffice endpoints simply stop using `require_permission` and inline a scoped check, mirroring the taxonomy-route precedent already documented in `utils/permissions.py:32-38`.
- `frontend/src/components/organisms/backoffice/reporting/` — backend-side narrowing is sufficient; the existing dropdowns already render whatever the API returns.

## Approach

1. **Fix `as_scope_key`** (`backend/app/models/user.py:127-145`). Replace the two `if s.affiliation: return ""` branches with `return f"/{s.affiliation}"`. Both the `RoleScope` and `dict` branches need updating. This is a single-line semantic change but it is load-bearing for everything downstream.

2. **Branch `calculate_user_permissions` on scope type for backoffice** (`backend/app/models/user.py:164-186`). The current code emits the same four bare keys whether `is_global_scope(scope)` or `is_role_scope(scope)`. Split the branch:
   - If `is_global_scope(scope)`: keep emitting the bare keys (`backoffice.reporting`, `backoffice.users`, `backoffice.data_management`, `backoffice.documentation`) — global backoffice keeps cross-affiliation reach.
   - If `is_role_scope(scope)` and `scope_key` (from `as_scope_key`) is non-empty: emit `backoffice.reporting{scope_key}`, `backoffice.users{scope_key}`, `backoffice.data_management{scope_key}`, `backoffice.documentation{scope_key}`. A user with two `CO2_BACKOFFICE_METIER` roles on `SV` and `STI` ends up with both `backoffice.users/SV` and `backoffice.users/STI` (natural union via the merge_actions pattern).
   - The `CO2_SUPERADMIN` branch (line 275-303) already requires `is_global_scope`, no change.

3. **Swap the endpoint gate** in `backend/app/api/v1/backoffice_reporting.py`. Replace `current_user: User = Depends(require_permission("backoffice.users", "view"))` on both endpoints with `current_user: User = Depends(get_current_active_user)` and call `has_permission(current_user.calculate_permissions(), "backoffice.users", "view", any_scope=True)` at the top of each handler — raise `HTTPException(403)` on miss. Rationale: `require_permission` does a literal-path lookup via `is_permitted` → `fnmatch` (`backend/app/core/security.py:210-217`) which fails for users whose only key is `backoffice.users/SV`. The `any_scope=True` path on `has_permission` (`backend/app/utils/permissions.py:55-67`) is the exact mechanism we need and matches the taxonomy precedent.

4. **Derive the caller's affiliation set** inside each handler. Pseudocode:

   ```python
   perms = current_user.calculate_permissions()
   is_global = "backoffice.users" in perms  # bare key only emitted for GlobalScope
   affiliations = {
       k.removeprefix("backoffice.users/")
       for k in perms
       if k.startswith("backoffice.users/")
   }
   ```

   If `is_global` is true, skip the affiliation predicate entirely. Otherwise apply it. (Use `backoffice.users` as the canonical anchor because both endpoints already gate on that key; the four backoffice keys are emitted in lockstep so any one would work.)

5. **Apply the affiliation predicate to the SQL queries.** Both endpoints already build a `select(Unit)` (lines 41, 77). For affiliation-scoped callers, add an `OR`-joined `path_name ILIKE` clause per affiliation. The recommended shape (see Open Questions for the field choice):

   ```python
   from sqlalchemy import or_
   if not is_global and affiliations:
       query = query.where(
           or_(*[col(Unit.path_name).ilike(f"% {aff} %") for aff in affiliations])
       )
   elif not is_global and not affiliations:
       return []  # defence-in-depth: scoped user with no affiliations sees nothing
   ```

   Whitespace boundaries (`% {aff} %`) avoid `SV` matching `SVOPS` etc. The `path_name` column is space-separated (`"EHE ASSOCIATIONS SCIENC-CULT 180C"`, see `backend/app/models/unit.py:76-79`).

6. **Multi-affiliation users (multiple `CO2_BACKOFFICE_METIER` roles)** are handled as a union: the permissions dict naturally accumulates one scoped key per affiliation, and the SQL predicate is an `OR` across the set. A user with affiliations `{SV, STI}` sees the union of SV's and STI's units.

7. **`GlobalScope` backoffice / superadmin** keep the bare `backoffice.users` key, so the `is_global` short-circuit in step 4 skips filtering and they see everything as today.

## Tests

### Backend unit tests (`backend/tests/unit/models/test_user.py` and `backend/tests/unit/utils/test_permissions.py`)

- `test_as_scope_key_affiliation_returns_prefixed_string`: `as_scope_key(RoleScope(affiliation="SV"))` → `"/SV"`, both via the `RoleScope` object branch and via the `dict` branch.
- `test_as_scope_key_global_still_returns_empty`: regression guard for `GlobalScope()` → `""`.
- `test_calculate_user_permissions_backoffice_metier_with_affiliation_emits_scoped_keys`: a single `CO2_BACKOFFICE_METIER @ affiliation=SV` role yields exactly `{backoffice.reporting/SV, backoffice.users/SV, backoffice.data_management/SV, backoffice.documentation/SV}` with correct action lists, and **no** bare `backoffice.*` keys.
- `test_calculate_user_permissions_backoffice_metier_global_unchanged`: regression guard — `GlobalScope` still emits bare keys.
- `test_calculate_user_permissions_backoffice_multi_affiliation_unions`: two `CO2_BACKOFFICE_METIER` roles on `SV` and `STI` yield both `backoffice.users/SV` and `backoffice.users/STI`.
- `test_has_permission_any_scope_matches_affiliation_keys`: `has_permission({"backoffice.users/SV": ["view"]}, "backoffice.users", "view", any_scope=True)` → `True`; same call with `any_scope=False` → `False` (pins the rationale for the endpoint change in step 3).

### Backend integration tests (`backend/tests/integration/v1/test_permission_scope_e2e.py`)

Add a helper alongside the existing `_principal`/`_std`/`_backoffice`/`_superadmin`:

```python
def _backoffice_scoped(affiliation: str) -> Role:
    return Role(role=RoleName.CO2_BACKOFFICE_METIER, on=RoleScope(affiliation=affiliation))
```

Add a new test class `TestBackofficeAffiliationScopeEndToEnd` covering `/api/v1/backoffice/units` (and the same shape for `/affiliations` if convenient):

- `test_global_backoffice_sees_all_units`: caller with `_backoffice()` (GlobalScope) → 200, full unit list. Pins the global short-circuit.
- `test_scoped_backoffice_sees_only_in_affiliation_units`: caller with `_backoffice_scoped("SV")` against a fixture that returns one SV unit and one STI unit → 200, response contains only the SV unit.
- `test_scoped_backoffice_cross_affiliation_returns_empty`: same caller against an STI-only fixture → 200 with empty list (the request is permitted — the user has `backoffice.users/SV` — but the predicate filters everything out). This is the cross-affiliation isolation guarantee.
- `test_scoped_backoffice_no_affiliations_denied_or_empty`: caller with role wired but affiliation set empty (defence-in-depth from step 5) → 200 empty. Document the chosen semantic in the assertion.
- `test_unscoped_request_denied_for_non_backoffice`: caller with only `_std(UNIT_IID)` → 403. Confirms the gate still rejects non-backoffice callers.
- `test_superadmin_sees_all_units`: regression guard, mirrors the pattern at line 174.

Use the existing `_wire` pattern for dependency overrides; supplement with a unit-list fixture function rather than reusing `_ALL_MEMBERS` (which is headcount-specific).

## Verification

```bash
cd backend
uv run pytest tests/unit/utils/test_permissions.py tests/unit/models/test_user.py -xvs
uv run pytest tests/integration/v1/test_permission_scope_e2e.py -xvs
make backend-dev   # then curl /api/v1/backoffice/units with a scoped backoffice token, verify filtered result
```

Sanity-check the full backoffice suite as well — `uv run pytest tests/integration/v1/test_backoffice_reporting.py -xvs` if such a file exists; otherwise run the broader integration sweep `uv run pytest tests/integration/v1/ -xvs`.

Manual e2e (post-deploy):

1. Log in as a known SV-scoped backoffice user.
2. Open the Reporting page, inspect the affiliation dropdown — should only list SV-tree units (Faculty SV + its institutes).
3. Open the Units table — only SV units should appear.
4. Repeat as a global backoffice / superadmin — every active unit should appear.

## Open questions

1. **Which `Unit` field matches ACCRED `sortpath`?** The test fixture uses `"Engineering"` (a school-name-shaped string); production values are unconfirmed. Candidates:
   - `path_name` (e.g. `"EHE ASSOCIATIONS SCIENC-CULT 180C"`) — human-readable, space-separated, supports `ILIKE` boundary matching. **Recommended** unless evidence shows otherwise.
   - `path_institutional_code` (numeric, space-separated) — would require an `affiliation→code` lookup table; not justified by current data.
   - A new dedicated column populated during ACCRED unit sync — overkill for v0.x.
     Confirm the production `sortpath` shape against a real ACCRED payload before locking step 5.

2. **ACCRED `sortpath` shape: single string or list?** Read of `role_provider.py:544-554` and the existing test (`test_role_provider.py:312`) shows a single string per authorization. A user with multiple sub-perimeters has multiple `CO2_BACKOFFICE_METIER` authorizations, each with its own `sortpath`, which our union-via-key-accumulation handles cleanly. Confirm with a real ACCRED payload that `sortpath` never returns a list/comma-string.

3. **Union vs intersection across affiliations.** The plan assumes union (a user with `{SV, STI}` sees both). This matches the natural multi-role semantics of every other role in the system and the implicit ACCRED contract (each authorization is an additive grant). Confirm with the product owner that no scenario calls for intersection.

4. **`backoffice.documentation` scoping.** Should documentation editing also be sub-perimeter-bound, or is documentation a shared corpus across the whole calculator (in which case `backoffice.documentation` stays unscoped even for affiliation-scoped backoffice users)? Plan currently treats it the same as the other three — scope it. Easy to reverse before merge if product disagrees.

5. **Endpoints beyond `/affiliations` and `/units`.** Issue title mentions "Reporting" generically. Audit `backend/app/api/v1/` for any other route gated on `backoffice.*` that returns unit-keyed data (e.g. backoffice carbon-report listings, export endpoints). If any exist, they need the same `any_scope=True` + predicate treatment; list them in the implementation PR description.

6. **Empty-affiliation scoped user — 200 with `[]` or 403?** Plan picks `200 []` (defence-in-depth: gate passes, predicate filters everything). Alternative is 403. Pick one explicitly during implementation and pin with the test from the Tests section.
