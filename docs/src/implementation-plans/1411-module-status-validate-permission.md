---
status: delivered
issue: 1411
---

# 1411 — Hide module-status validate button from standard users + consolidate frontend permissions

## Context

In the left module sidebar (`Co2ModuleSidebar` → `ModuleTotalResult`), the
**Validate / Unvalidate** button is rendered unconditionally. A standard user
(own-scope) can reach a module page they may edit (e.g. professional travel)
and sees the button, even though validating a module's status is a unit-level
operation the backend already rejects with 403
(`require_module_unit_scope`). The button must be **absent** for standard
users.

The fix follows project philosophy (see `docs/src/backend/06-PERMISSION-SYSTEM.md`):
the frontend **never branches on roles** — it gates UI on **permissions only**.
We introduce a dedicated custom permission whose **key is the resource** and
**action is the verb**: `module.status/<cf>` + action `edit`, where `<cf>` is a
cost-center `institutional_id`. One key governs the validate button across all
modules; only unit-breadth users (principals) receive it.

This change also consolidates the frontend permission surface into a single
entry point and collapses the router guards, per the same review.

## Decisions (confirmed with user)

1. **Single entry point, pure leaf retained.** Consumers call `authStore.*`
   exclusively. The stateless predicates stay in a store-free
   `src/utils/permission.ts` leaf (so `permission.spec.ts` keeps working — the
   store imports the http/i18n chain that crashes Playwright's pure-test
   runner). `src/constant/permissions.ts` is deleted; its types/enum fold into
   the leaf. Net: 3 files → 2.
2. **Permission:** `module.status/<cf>` with action `edit` (no new action
   vocabulary). Granted to **principal only** (unit scope), matching who can
   currently validate.
3. **Guards:** merge `requireMetaPermission` + `requireModuleEditPermission`
   into one meta-driven `permissionGuard`; delete the unused
   `requirePermission` factory and the **dead** `meta.roles` branch in
   `authGuard` (no route uses `meta.roles` — it is the app's only `roles_raw`
   conditional).

## Changes

### Backend — grant the permission

`backend/app/models/user.py` → `calculate_user_permissions`, in the
`CO2_USER_PRINCIPAL` (unit-scope) branch alongside the `modules.*` grants:

```python
permissions[f"module.status{scope_key}"] = merge_actions(
    permissions.get(f"module.status{scope_key}"), ["edit"],
)
```

`scope_key` is `/<institutional_id>` for a unit role, so the emitted key is
`module.status/<cf>`. Standard (own), backoffice, and superadmin branches are
untouched, so they never receive it.

Backend enforcement of the PATCH endpoint stays `require_module_unit_scope`
(already correct). `module.status` is the UI-affordance mirror; do **not**
add a second enforcement check.

### Frontend — consolidate to two files

- **`src/utils/permission.ts` (pure leaf):** keep the predicates
  (`hasPermission`, `hasAnyScopePermission`, `hasBackOfficeAreaPermission`,
  `getModulePermissionPath`). Fold in from the deleted `constant/permissions.ts`:
  the `PermissionAction` enum and the `FlatUserPermissions` / `ModulePermissions`
  types. Add a constant `MODULE_STATUS_PERMISSION = 'module.status'`. No
  store/http/i18n imports.
- **Delete `src/constant/permissions.ts`.** Update every importer of
  `PermissionAction` (Co2Header, Co2Sidebar, ModuleTable, SubModuleSection,
  HeadcountMemberSelect, HomePage, routes.ts, permissionGuard.ts) to import it
  from `src/stores/auth` (re-exported there) so callers use the one entry
  point. The leaf and `permission.spec.ts` import it from `utils/permission`.
- **`src/stores/auth.ts` (stateful entry point):** re-export `PermissionAction`
  (and the permission types) from the leaf. Add a named helper:

  ```ts
  function hasUserCanValidateModuleStatus(): boolean {
    return hasUserPermission(MODULE_STATUS_PERMISSION, PermissionAction.EDIT);
  }
  ```

  `hasUserPermission` already appends the selected unit's `institutional_id`,
  so it matches `module.status/<cf>` for a principal and is false for a
  standard user (own key never granted).

### Frontend — gate the button

`src/components/organisms/module/ModuleTotalResult.vue`: add
`const canValidate = computed(() => authStore.hasUserCanValidateModuleStatus())`
and `v-if="canValidate"` on **all three** validate `q-btn` instances
(mini sidebar ~L25, sidebar body ~L76, module-page card ~L129). Import/use
`useAuthStore`.

### Frontend — collapse guards

`src/router/guards/permissionGuard.ts`: replace the three exports with one:

```ts
export function permissionGuard(to): NavigationGuardReturn {
  if (window.__LIGHTHOUSE_BYPASS__) return true;
  const authStore = useAuthStore();
  if (to.meta.moduleEdit) {
    // module route: workspace-scoped view+edit
    const module = to.params.module as Module;
    if (!authStore.hasUserModulePermission(module, PermissionAction.VIEW))
      return { name: "unauthorized" };
    if (!authStore.hasUserModulePermission(module, PermissionAction.EDIT))
      return { name: "unauthorized" };
    return true;
  }
  const path = to.meta.requiredPermission as string | undefined; // backoffice: any-scope
  if (!path) return true;
  const action =
    (to.meta.requiredAction as PermissionAction) ?? PermissionAction.VIEW;
  return authStore.hasUserAnyScopePermission(path, action)
    ? true
    : { name: "unauthorized" };
}
```

`src/router/routes.ts`: module route (~L178) `beforeEnter: [permissionGuard, moduleEnabledGuard()]` + add `moduleEdit: true` to its `meta`. All back-office `beforeEnter: requireMetaPermission` → `permissionGuard`.

`src/router/guards/authGuard.ts`: delete the `meta.roles` block (lines ~39-48) — dead and role-based.

### Frontend — dead code removed (review pass)

The `module.status` approach supersedes scope-inference, so the now-orphaned
`hasUserUnitScopePermission` (store) and `hasUnitScopePermission` (leaf) — zero
production consumers — plus their 4 unit tests were removed. This reinforces the
"dedicated key, never infer breadth on the frontend" rule.

## Tests (regression)

- **Backend (load-bearing automated guard):** `backend/tests/unit/utils/test_permissions.py`
  — principal with unit scope → `result["module.status/<cf>"]` contains
  `"edit"`; standard-user role → no key starting with `module.status`; plus the
  domain-isolation matrix widened to allow the principal `module.status` prefix.
  This catches the regression that matters going forward: a standard user
  starting to receive the affordance. Run via `uv run pytest`.
- **Frontend DOM (`v-if`): manual verification, deliberately not automated.**
  The gate is a 3-line `v-if` over the already-tested `hasUserPermission`
  predicate. A pure unit test of the predicate would pass whether or not the
  button is gated (it exercises `hasPermission`, not the wiring) — a hand-wave
  we do not ship. A true automated guard needs either ~200 lines of bespoke
  module-page mock scaffolding (no precedent here) or a Quasar+i18n+Pinia CT
  mount harness (the current CT harness mounts only a bare `App`). Both are
  disproportionate for this change; the DOM must be verified manually (steps
  below). **Not yet observed in the implementing session** — pending a manual
  run against the app.

## Verification

1. `cd backend && uv run pytest tests/unit/models/test_user_base_calculate_permissions.py tests/unit/utils/test_permissions.py`
2. `cd frontend && npm run test-ct` (runs `tests/unit`, incl. permission.spec.ts)
3. `cd frontend && make type-check` (vue-tsc; `rtk tsc` green ≠ husky pass).
4. Manual (test-mode login role selector): log in **standard**, open
   professional-travel module → Validate button **absent** in sidebar + page.
   Log in **principal** → button **present** and toggles. Backoffice/superadmin
   routes still gate correctly (guard collapse regression).
