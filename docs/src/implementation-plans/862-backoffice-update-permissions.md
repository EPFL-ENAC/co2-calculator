---
status: in-progress
issue: 862
last_updated: 2026-06-02
title: "Update backoffice permissions (page-driven model)"
summary: "Replace the system.users super-admin gate with one permission per backoffice page (configuration, pipeline_operations, logs, ui_texts), scope only backoffice.reporting by affiliation, and move the #459 affiliation anchor to backoffice.reporting."
---

## Context

Backoffice access is currently a two-tier flag system (`limitedAccess` =
Backoffice Administrator + Super Admin; `superAdminOnly` = Super Admin) and a
single backend gate, `system.users.edit`, stands in for "is super admin".
That gate is overloaded — it guards Logs, Configuration, and Pipeline
Operations alike — so it cannot express per-page access or per-page data
scope.

This plan adopts a **page-driven permission model**: one permission per
frontend page, and the permission a page uses to reach a backend endpoint
also determines that call's **data scope**. Permissions trickle down from the
frontend UX to the backend.

This supersedes the earlier `system.users`-based draft of this plan and is
coordinated with #459 (affiliation scoping). Naming stays **underscored**
(`backoffice.pipeline_operations`, not `-`) to match every existing key and
the generated OpenAPI contract. The `calco2.superadmin` →
`calco2.backoffice.admin` role rename is **deferred to a separate PR**; this
change is built against the current name.

## Target model

### Backoffice pages → permissions

| Page                  | Permission                       | Actions            | Roles               | Scope                                      |
| --------------------- | -------------------------------- | ------------------ | ------------------- | ------------------------------------------ |
| Reporting             | `backoffice.reporting`           | view, export       | metier, superadmin  | affiliation (metier) / global (superadmin) |
| User Management       | `backoffice.users`               | view, edit, export | metier, superadmin  | global (scope-less)                        |
| Documentation Editing | `backoffice.documentation`       | view, edit         | metier, superadmin  | global (scope-less)                        |
| UI Texts Editing      | `backoffice.ui_texts` (**new**)  | view, edit         | metier, superadmin  | global (scope-less)                        |
| Configuration         | `backoffice.configuration`       | view, edit         | **superadmin only** | global (scope-less)                        |
| Pipeline Operations   | `backoffice.pipeline_operations` | view, edit         | **superadmin only** | global (scope-less)                        |
| Logs                  | `backoffice.logs`                | view               | **superadmin only** | global (scope-less)                        |

`system.users` is **removed**: its three roles above replace it.
`backoffice.data_management` is renamed to `backoffice.configuration` (the
Configuration page); the metier role no longer receives it at all.

### Module pages → permissions

Unchanged in shape: `modules.<name>` with `view, edit, sync`, unit-scoped for
`calco2.user.principal` and own-scoped for `calco2.user.standard`
(`professional_travel` + `external_cloud_and_ai`). See the [role-permission matrix](../backend/06-PERMISSION-SYSTEM.md#role-permission-matrix).

### Scope-from-permission principle

The permission that authorises a call also fixes its scope. The data-sync
endpoints make this concrete:

- Triggered from a **module page** → gated by `modules.<name>.sync` → scoped
  to the caller's unit `institutional_id`.
- Triggered from the **Configuration / Pipeline Operations page** → gated by
  `backoffice.configuration` / `backoffice.pipeline_operations` → **global**.

> **Resolved (2026-06-02): split endpoints per page.** Module-page sync stays
> on the unit-scoped `modules.<name>.sync` endpoints; backoffice global sync
> gets its own endpoint(s) gated by `backoffice.pipeline_operations` /
> `backoffice.configuration`. No shared endpoint serves both scopes.

## Changes

### Backend

1. **`app/models/user.py::calculate_user_permissions`** — emit the new keys.
   - Superadmin (global): bare `backoffice.reporting`, `backoffice.users`,
     `backoffice.documentation`, `backoffice.ui_texts`,
     `backoffice.configuration`, `backoffice.pipeline_operations`,
     `backoffice.logs`. Drop `system.users`.
   - Metier (affiliation-scoped): `backoffice.reporting/<aff>` only;
     `backoffice.users`, `backoffice.documentation`, `backoffice.ui_texts`
     **scope-less** (no `/aff` suffix). No configuration/pipeline/logs.
2. **Affiliation anchor → `backoffice.reporting`.** Update
   `derive_backoffice_affiliations` and `gate_backoffice` defaults
   (`app/utils/permissions.py`, `app/utils/scoping.py`) and the
   `backoffice_reporting.py` / `backoffice.py` call sites. `backoffice.users`
   is no longer scoped, so it can no longer be the anchor.
3. **Re-gate `system.users` routes** to the page permission:
   - `app/api/v1/audit.py` (4×) → `backoffice.logs` / view.
   - `app/api/v1/year_configuration.py` (3×) → `backoffice.configuration` / edit.
   - `app/api/v1/data_sync.py`: **split** the write/trigger endpoints —
     backoffice (global) sync gets dedicated endpoints gated by
     `backoffice.pipeline_operations` / `backoffice.configuration` / edit;
     module-page sync stays unit-scoped on `modules.<name>.sync`. Read
     endpoints follow the `backoffice.data_management` → `backoffice.configuration`
     rename.

### Frontend

4. **`src/constant/permissions.ts`** — add `backoffice.configuration`,
   `backoffice.pipeline_operations`, `backoffice.logs`, `backoffice.ui_texts`;
   remove `system.users`; rename `data_management` → `configuration`.
5. **`src/router/routes.ts`** — guard each backoffice route with its own page
   permission (configuration/pipeline_operations/logs), not `backoffice.users`
   or `system.users`.
6. **`src/constant/navigation.ts`** — keep Configuration/Pipeline/Logs as
   super-admin pages; the per-page guard now enforces it.
7. **Regenerate OpenAPI types** (`openapi.d.ts`) from backend docstrings —
   do not hand-edit.

### Docs

8. Update the [matrix](../backend/06-PERMISSION-SYSTEM.md#role-permission-matrix)
   and [model](../backend/06-PERMISSION-SYSTEM.md#permission-model) sections of
   the consolidated [06-PERMISSION-SYSTEM](../backend/06-PERMISSION-SYSTEM.md)
   in the same PR: new keys and the affiliation-anchor change.

## Cleanup (fold in or split as a follow-up)

Surfaced while auditing; low-risk removals:

- Delete unused `User.has_role`, `User.has_role_global`, `User.refresh_permissions`
  (zero callers; `refresh_permissions` also assigns a non-field).
- `app/core/security.py::check_permission` has no application caller (test-only) —
  remove or document.
- `modules.*` `sync` action is granted but never enforced via a route gate —
  wire it (per the scope principle) or drop it.
- Stray `co2.*` role strings: `unit_service.py:74`, `auth.py:338` default
  `role="co2.user.std"` — only `calco2.*` match a real `RoleName`.

## Verification

1. `calco2.superadmin` → all seven backoffice pages reachable; API mutations
   on configuration / pipeline / logs return 200.
2. `calco2.backoffice.metier` → Configuration, Pipeline Operations, Logs
   return 403 and the tabs/routes redirect to `/unauthorized`; Reporting is
   affiliation-scoped; Users / Documentation / UI Texts are reachable
   unscoped.
3. Affiliation narrowing keys off `backoffice.reporting` (regression test in
   `test_permission_scope_e2e.py`).
4. `test_user_base_calculate_permissions.py` updated for the new key set and
   green; `matrix.md` regenerated to match `calculate_user_permissions`.
5. `make type-check` (vue-tsc) and backend `uv run pytest` green.
