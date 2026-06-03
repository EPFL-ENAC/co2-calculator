# Bot Review TODOs: PR #1381

## Source Branch: `feat/862-backoffice-page-permissions`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR refactors authorization across backend + frontend by (1) moving backoffice access to a **page-driven permission model** (`backoffice.{reporting,users,documentation,ui_texts,configuration,pipeline_operations,logs}`) and removing the `system.*` family, and (2) making module breadth **explicit in permission keys** via a discriminated `RoleScope` union and `/own` suffix for standard users.

**Changes:**

- Replace implicit scope inference with explicit `GlobalScope | UnitScope | OwnScope | AffiliationScope` and encode breadth in permission keys (`modules.X/<unit>` vs `modules.X/<unit>/own`).
- Update UI gating + route guards for the new backoffice page permissions and `/own`-aware module checks.
- Consolidate permission documentation into `docs/src/backend/06-PERMISSION-SYSTEM.md` and remove the older permissions sub-pages from MkDocs nav.

**Blocking review findings (require changes):**

- **Frontend: `hasUserUnitScopePermission` is not workspace-scoped (can leak UI controls across units).**  
  In `frontend/src/stores/auth.ts`, `hasUserUnitScopePermission()` claims “for the selected workspace” but forwards a bare `path` into `hasUnitScopePermission()` without appending the selected unit’s `institutional_id`. As a result, a user who is principal in _any_ unit could see unit-level controls while viewing a different workspace.  
  **Suggested fix:** append `workspaceStore.selectedUnit?.institutional_id` (similar to `hasUserModulePermission`) and check the unit key (`modules.X/<iid>`) only.
- **Sidebar super-admin gating is broken and super-admin-only disabling is commented out.**  
  In `frontend/src/components/layout/Co2Sidebar.vue`, `hasSuperAdminRole` is currently checking `ROLES.BackOfficeMetier` (not `ROLES.SuperAdmin`) and the `item.superAdminOnly` disabling is commented out. This will incorrectly treat non-superadmins as superadmin (and/or fail to disable restricted items).  
  **Suggested fix:** restore `ROLES.SuperAdmin` check and re-enable the `superAdminOnly` branch; remove the inline `todo` + commented-out logic.
- **Unexpected destructive Alembic migration included.**  
  `backend/alembic/versions/2026_06_02_1343-c0384764d161_what_did_i_miss.py` drops multiple indexes (including unique/GIN indexes). This is unrelated to the PR’s stated authorization scope and has major operational risk.  
  **Suggested fix:** remove this migration from the PR (or justify it with explicit requirements + safe migration plan).
- **API/docs string inconsistency for permissions.**  
  In the generated `frontend/src/types/api/openapi.d.ts`, examples show `Permission denied: backoffice.configuration view` (missing the dot before `view`), while other places use `backoffice.configuration.view`. This comes from backend doc/example strings and makes troubleshooting inconsistent.  
  **Suggested fix:** standardize error/example strings to `backoffice.configuration.view`.

### Reviewed changes

Copilot reviewed 54 out of 55 changed files in this pull request and generated no comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                           | Description                                                                                      |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| frontend/src/utils/permission.ts                                               | Removes `system.*` backoffice area matching; adds unit-breadth helper (`/own` aware).            |
| frontend/src/stores/auth.ts                                                    | Updates module permission lookup to accept `/own`; adds unit-breadth accessor.                   |
| frontend/src/router/routes.ts                                                  | Switches backoffice route guards to per-page permissions (`backoffice.*`).                       |
| frontend/src/constant/permissions.ts                                           | Updates permission key types for page-driven backoffice + `/own` module key shapes.              |
| frontend/src/components/layout/Co2Sidebar.vue                                  | Adjusts sidebar gating (currently introduces incorrect superadmin logic).                        |
| frontend/src/types/api/openapi.d.ts                                            | Regenerated OpenAPI types reflecting new permissions and new endpoints.                          |
| backend/app/models/user.py                                                     | Introduces discriminated `Scope` union; emits explicit `/own` keys; page-driven backoffice keys. |
| backend/app/utils/permissions.py                                               | Updates `has_permission` to match `/own`; adds `resolve_module_scope`.                           |
| backend/app/utils/scoping.py                                                   | Moves affiliation anchor default to `backoffice.reporting`; adds module-flow dual gate helpers.  |
| backend/app/core/policy.py                                                     | Adds `require_module_unit_scope` to prevent unit-level operations for own-scoped users.          |
| backend/app/api/v1/carbon_report.py                                            | Gates module status patch using `require_module_unit_scope`.                                     |
| backend/app/api/v1/{audit,year_configuration,files,factors}.py                 | Re-gates endpoints to new page permissions (`backoffice.configuration/logs/...`).                |
| backend/app/api/v1/data_sync.py                                                | Splits/adjusts sync + pipeline status gates per new model (config vs module sync).               |
| backend/app/providers/role_provider.py                                         | Emits explicit scope kinds (unit vs own vs affiliation vs global).                               |
| backend/app/providers/test_fixtures.py                                         | Updates test role fixtures to explicit scopes.                                                   |
| backend/tests/\*\*                                                             | Migrates tests to explicit scope kinds + `/own` keys; updates access expectations.               |
| docs/src/backend/06-PERMISSION-SYSTEM.md                                       | Consolidates permissions documentation into one canonical reference.                             |
| docs/src/implementation-plans/862-backoffice-update-permissions.md             | Updates plan to page-driven backoffice permission model.                                         |
| docs/src/implementation-plans/role-scope-explicit-own-unit.md                  | Adds plan for explicit RoleScope + `/own` key model.                                             |
| docs/src/implementation-plans/fix-other-name-entra-authentication-hardening.md | Updates a cross-reference to point at the consolidated permission doc.                           |
| docs/mkdocs.yml                                                                | Removes the old “Developer Guide: Permissions” nav entries.                                      |
| docs/src/backend/permissions/{index,model,matrix,how-to-add,audit}.md          | Removes now-redundant permission sub-pages (content moved to 06-PERMISSION-SYSTEM).              |
| backend/alembic/versions/2026_06_02_1343-c0384764d161_what_did_i_miss.py       | Adds migration dropping indexes (appears accidental / unrelated; high risk).                     |

</details>

---

### File: `backend/alembic/versions/2026_06_02_1343-c0384764d161_what_did_i_miss.py` (Line 13) — github-advanced-security[bot]

## CodeQL / Unused import

Import of 'sqlmodel' is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/676)

## Action Items

### Critical: logic, security, correctness

- [ ] **frontend/src/stores/auth.ts** — `hasUserUnitScopePermission` (L221-227) forwards the bare `path` into `hasUnitScopePermission` without the workspace unit, so a principal in _any_ unit sees unit-level controls while viewing a different workspace. Fix: read `workspaceStore.selectedUnit?.institutional_id`, return false if absent, and check only the unit key `${path}/${iid}` (mirror `hasUserPermission` L165-172 but **without** the `/own` fallback — excluding own-scope is the function's whole purpose). Update the docstring claim accordingly.
- [ ] **frontend/src/components/layout/Co2Sidebar.vue** — `hasSuperAdminRole` (L29-35) matches `ROLES.BackOfficeMetier` instead of `ROLES.SuperAdmin`, and the `superAdminOnly` branch (L44) is commented out. Net effect: backoffice-metier users are treated as super admin and `superAdminOnly` items are never disabled. Fix: switch the role check to `ROLES.SuperAdmin`, re-enable `if (item.superAdminOnly === true) return true;`, drop the `todo` comment.
- [ ] **backend/alembic/versions/2026_06_02_1343-c0384764d161_what_did_i_miss.py** — auto-generated migration that drops 7 existing indexes (incl. unique partial + GIN), unrelated to this auth PR; classic autogenerate false-positive `drop_index` set (models exist, autogenerate didn't see them). Fix: delete the file. If a real schema change was intended, regenerate via `make db-revision` and prune the spurious `drop_index` calls. (This also resolves the GHAS "unused `sqlmodel` import" alert — moot once removed.)

### Maintainability / refactoring

- [ ] **backend/app/api/v1/files.py** (L92) — OpenAPI response-example string `"Permission denied: backoffice.configuration view"` is missing the dot before `view`; inconsistent with `backoffice.configuration.view` at L156 and elsewhere. Fix: add the dot. Note: the bot cited the generated `openapi.d.ts`, but the source of truth is this docstring example — fixing it here regenerates the type correctly.

---
