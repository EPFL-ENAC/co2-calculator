# Update Backoffice Permissions (Issue #862 / modified from #168)

## Context

The backoffice currently has two permission tiers: "limitedAccess" (Backoffice Administrator + Super Admin) and "superAdminOnly" (Super Admin alone). The new spec requires that the **Configuration** and **Pipeline Operations** tabs join **Logs** as Super Admin-only, while all other backoffice tabs remain accessible to both Backoffice Administrator and Super Admin.

### Role → tab access table

| Tab                     | BackofficeAdministrator (`calco2.backoffice.metier`) | SuperAdmin (`calco2.superadmin`) |
| ----------------------- | ---------------------------------------------------- | -------------------------------- |
| Reporting               | ✅                                                   | ✅                               |
| User Management         | ✅                                                   | ✅                               |
| Documentation Editing   | ✅                                                   | ✅                               |
| UI Texts Editing        | ✅                                                   | ✅                               |
| **Configuration**       | ❌                                                   | ✅                               |
| **Pipeline Operations** | ❌                                                   | ✅                               |
| **Logs**                | ❌                                                   | ✅                               |

---

## Changes

### 1. `frontend/src/constant/navigation.ts`

Change both items from `limitedAccess: true` → `superAdminOnly: true`. Remove the stale comment above `BACKOFFICE_PIPELINE_OPERATIONS` that described the old access rule.

- `BACKOFFICE_DATA_MANAGEMENT`: `limitedAccess: true` → `superAdminOnly: true`
- `BACKOFFICE_PIPELINE_OPERATIONS`: `limitedAccess: true` → `superAdminOnly: true`

`Co2Sidebar.vue` already handles `superAdminOnly` correctly and the SA short-circuit already applies — no sidebar changes needed.

### 2. `frontend/src/router/routes.ts`

Change the `beforeEnter` guard for the two routes from `backoffice.users / EDIT` to `system.users / EDIT` (matching the pattern already used by the Logs route):

- `back-office/data-management`: `requirePermission('backoffice.users', PermissionAction.EDIT)` → `requirePermission('system.users', PermissionAction.EDIT)`
- `back-office/pipeline-operations`: same change

### 3. `backend/app/api/v1/year_configuration.py`

The Configuration tab's write operations are guarded with `backoffice.data_management.edit`. Change those guards to `system.users.edit` to enforce SuperAdmin-only at the API level (three locations):

```python
# before
if not await is_permitted(current_user, "backoffice.data_management", "edit"):
# after
if not await is_permitted(current_user, "system.users", "edit"):
```

Update matching error-detail strings and docstrings from "backoffice data managers" → "super administrators".

### 4. `backend/app/api/v1/data_sync.py`

The Pipeline Operations tab's trigger/sync operations are guarded with `backoffice.data_management.sync`. Change those to `system.users.edit`:

- `require_permission("backoffice.data_management", "sync")` → `require_permission("system.users", "edit")`
- `is_permitted(current_user, "backoffice.data_management", "sync")` → `is_permitted(current_user, "system.users", "edit")`

**Leave `backoffice.data_management.view` guards unchanged** — those view endpoints are also consumed by regular module pages and must remain accessible to BackofficeMetier.

Update affected docstrings from `backoffice.data_management.sync` → `system.users.edit` and "backoffice data manager" → "super administrator".

---

## Verification

1. Log in as `calco2.backoffice.metier` → Configuration and Pipeline Operations tabs appear disabled in the sidebar; direct navigation to `/back-office/data-management` and `/back-office/pipeline-operations` redirects to `/unauthorized`.
2. Attempt a year-configuration mutation or a sync trigger via the API with a BackofficeMetier token → expect HTTP 403.
3. Log in as `calco2.superadmin` → all three restricted tabs (Configuration, Pipeline Operations, Logs) are accessible.
4. BackofficeMetier can still access Reporting, User Management, Documentation Editing, UI Texts Editing.
