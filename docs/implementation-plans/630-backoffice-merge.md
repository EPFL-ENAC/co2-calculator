# Backoffice Merge Implementation Plan

## Goals

Consolidate the System section into Backoffice, so the final backoffice sidebar contains these pages in order:

1. Reporting _(already exists)_
2. User Management _(already exists)_
3. Documentation Editing _(already exists — Texts section removed)_
4. UI Texts Editing _(new — receives Texts section from Documentation Editing)_
5. Logs _(new — from System, tab disabled for non-Superadmins)_

Remove all UI exposition of the System section (header button, system-route sidebar, system navigation).

---

## Current State

### Backoffice nav (`BACKOFFICE_NAV` in `navigation.ts`)

| Key                                | Route                              | Path                                |
| ---------------------------------- | ---------------------------------- | ----------------------------------- |
| `BACKOFFICE_REPORTING`             | `backoffice-reporting`             | `back-office/reporting`             |
| `BACKOFFICE_USER_MANAGEMENT`       | `backoffice-user-management`       | `back-office/user-management`       |
| `BACKOFFICE_DATA_MANAGEMENT`       | `backoffice-data-management`       | `back-office/data-management`       |
| `BACKOFFICE_DOCUMENTATION_EDITING` | `backoffice-documentation-editing` | `back-office/documentation-editing` |

### System nav (`SYSTEM_NAV` in `navigation.ts`)

| Key                        | Route                      | Path                       |
| -------------------------- | -------------------------- | -------------------------- |
| `SYSTEM_USER_MANAGEMENT`   | `system-user-management`   | `system/user-management`   |
| `SYSTEM_MODULE_MANAGEMENT` | `system-module-management` | `system/module-management` |
| `SYSTEM_LOGS`              | `system-logs`              | `system/logs`              |

### System UI entry points (in `Co2Header.vue`)

- Button `user_management_system_button_label` → navigates to `system-user-management` (shown when `hasSystemAccess && !isInSystemRoute`)
- Button "Back to Calculator" (shown when `hasSystemAccess && isInSystemRoute`)
- Button for dev docs (shown when `hasSystemAccess && isInSystemRoute`)

---

## Changes Required

### 1. `frontend/src/constant/navigation.ts`

**a) Add `superAdminOnly` field to `NavItem` interface**

```ts
export interface NavItem {
  routeName: string;
  icon: string;
  description?: string;
  limitedAccess?: boolean;
  superAdminOnly?: boolean; // tab visible but disabled unless user has superadmin role
}
```

**b) Add two new entries and reorder `BACKOFFICE_NAV`**

Final key order must match sidebar display order:

```ts
export const BACKOFFICE_NAV: Record<string, NavItem> = {
  BACKOFFICE_REPORTING: { ... },           // unchanged
  BACKOFFICE_USER_MANAGEMENT: { ... },     // unchanged
  BACKOFFICE_DATA_MANAGEMENT: { ... },     // unchanged (stays between user mgmt and doc editing)
  BACKOFFICE_DOCUMENTATION_EDITING: { ... }, // unchanged
  BACKOFFICE_UI_TEXTS_EDITING: {
    routeName: 'backoffice-ui-texts-editing',
    description: 'backoffice-ui-texts-editing-description',
    icon: 'o_translate',
  },
  BACKOFFICE_LOGS: {
    routeName: 'backoffice-logs',
    description: 'backoffice-logs-description',
    icon: 'o_list_alt',
    superAdminOnly: true,
  },
};
```

> Note: `SYSTEM_NAV` can remain in the file for now (system routes are kept as dead routes) but will no longer be referenced in the UI.

---

### 2. `frontend/src/router/routes.ts`

**a) Add two new backoffice routes** (after existing backoffice routes, before system routes):

```ts
{
  path: 'back-office/ui-texts-editing',
  name: BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.routeName,
  component: () => import('pages/back-office/UITextsEditingPage.vue'),
  beforeEnter: requirePermission('backoffice.users', 'view'),
  meta: {
    requiresAuth: true,
    note: 'Back Office - UI translation text management via GitHub',
    breadcrumb: false,
    isBackOffice: true,
  },
},
{
  path: 'back-office/logs',
  name: BACKOFFICE_NAV.BACKOFFICE_LOGS.routeName,
  component: () => import('pages/system/LogsPage.vue'),
  beforeEnter: requirePermission('system.users', 'edit'),
  meta: {
    requiresAuth: true,
    note: 'Back Office - Audit logs (superadmin only)',
    breadcrumb: false,
    isBackOffice: true,
  },
},
```

> Reuses `pages/system/LogsPage.vue` directly — no need to copy.
> `requirePermission('system.users', 'edit')` acts as the hard route guard; the sidebar's `superAdminOnly` flag handles the visual disabled state.

---

### 3. `frontend/src/components/layout/Co2Sidebar.vue`

**a) Add superadmin role check**

Import `ROLES` from `src/constant/roles` and add a computed:

```ts
import { ROLES } from "src/constant/roles";

const hasSuperAdminRole = computed(() => {
  return (
    authStore.user?.roles_raw?.some((x) => x.role === ROLES.SuperAdmin) ?? false
  );
});
```

**b) Update `isItemDisabled`**

```ts
function isItemDisabled(item: NavItem): boolean {
  if (item.superAdminOnly === true && !hasSuperAdminRole.value) return true;
  if (item.limitedAccess === true && !hasBackOfficeEditPermission.value)
    return true;
  return false;
}
```

---

### 4. `frontend/src/components/layout/Co2Header.vue`

Remove all system-section UI. Delete the following:

- `import { isBackOfficeRoute, isSystemRoute }` → change to `import { isBackOfficeRoute }` (drop `isSystemRoute`)
- `hasSystemAccess` computed property
- `isInSystemRoute` computed property
- The three `<q-btn>` elements that reference `hasSystemAccess`:
  1. Dev docs button (`v-if="hasSystemAccess && isInSystemRoute"`)
  2. "System Management" nav button (`v-if="hasSystemAccess && !isInSystemRoute"`)
  3. "Back to Calculator" button for system route (`v-if="hasSystemAccess && isInSystemRoute"`)

The existing backoffice buttons (`hasBackOfficeAccess`) are untouched.

---

### 5. `frontend/src/pages/back-office/UITextsEditingPage.vue` _(new file)_

Create this page by extracting the Texts section from `DocumentationEditingPage.vue`.

**Content:**

- `NavigationHeader` using `BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING`
- The `rows` computed (all 18 GitHub links to i18n `.ts` files)
- The translation table (`q-table`) with existing columns
- The i18n keys (`documentation_editing_translation_title`, `documentation_editing_translation_description_part_1`, etc.)
- Same styles (`.page`, `.table-spacing`, `.github-btn`) copied from DocumentationEditingPage

---

### 6. `frontend/src/pages/back-office/DocumentationEditingPage.vue`

Remove the Texts section:

- Delete the entire `rows` computed (lines 10–135)
- Delete the `<h1>` + description block for translations (first `text-h2` section)
- Delete the first `<q-table>` block that uses `:rows="rows"`
- Keep: `docRows` computed, the Documentation `<h1>` section, and the second `<q-table>`
- Update `NavigationHeader` — it already uses `BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING`, no change needed there

---

### 7. `frontend/src/i18n/backoffice.ts`

Add i18n entries for the two new nav items:

```ts
[BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.routeName]: {
  en: 'UI Texts Editing',
  fr: 'Édition des textes UI',
},
[BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.description]: {
  en: 'Edit UI translation files for all modules.',
  fr: 'Modifier les fichiers de traduction UI pour tous les modules.',
},
[BACKOFFICE_NAV.BACKOFFICE_LOGS.routeName]: {
  en: 'Logs',
  fr: 'Journaux',
},
[BACKOFFICE_NAV.BACKOFFICE_LOGS.description]: {
  en: 'View system audit logs. Superadmin access only.',
  fr: 'Consulter les journaux d\'audit. Accès superadmin uniquement.',
},
```

---

## File Change Summary

| File                                                 | Change                                                                                                         |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `src/constant/navigation.ts`                         | Add `superAdminOnly` to `NavItem`; add `BACKOFFICE_UI_TEXTS_EDITING` and `BACKOFFICE_LOGS` to `BACKOFFICE_NAV` |
| `src/router/routes.ts`                               | Add `backoffice-ui-texts-editing` and `backoffice-logs` routes                                                 |
| `src/components/layout/Co2Sidebar.vue`               | Add superadmin check; update `isItemDisabled`                                                                  |
| `src/components/layout/Co2Header.vue`                | Remove all system-section buttons and computeds                                                                |
| `src/pages/back-office/UITextsEditingPage.vue`       | **New file** — extracted Texts section                                                                         |
| `src/pages/back-office/DocumentationEditingPage.vue` | Remove Texts section (keep Documentation section only)                                                         |
| `src/i18n/backoffice.ts`                             | Add 4 new i18n keys for new nav items                                                                          |
