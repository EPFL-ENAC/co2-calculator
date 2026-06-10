/**
 * Permission utility functions for checking user permissions.
 *
 * These utilities work with the flat permission structure returned by the backend.
 * They provide type-safe, null-safe ways to check user permissions.
 *
 * Permission types/enums (mirroring the backend keys) live here too, so this
 * stays a store-free leaf importable by pure unit tests.
 */

import { MODULES, type Module } from 'src/constant/modules';

/** Actions that can be performed on a permission resource. */
export enum PermissionAction {
  /** View/read access. */
  VIEW = 'view',
  /** Edit/write access (create/update/delete, and the validate affordance). */
  EDIT = 'edit',
  /** Export/download access. */
  EXPORT = 'export',
}

/** Allowed actions on a single resource, as returned by the backend. */
export interface ModulePermissions {
  view?: boolean;
  edit?: boolean;
  export?: boolean;
}

/**
 * Flat permissions dict as returned by `GET /session`: dot-notation keys with
 * an action list as value. Module keys carry an explicit scope suffix
 * (`modules.X/<unit>` or `modules.X/<unit>/own`); the index signature covers
 * those plus custom affordances like `module.status/<cf>`.
 */
export interface FlatUserPermissions {
  'backoffice.reporting'?: ModulePermissions;
  'backoffice.users'?: ModulePermissions;
  'backoffice.documentation'?: ModulePermissions;
  'backoffice.ui_texts'?: ModulePermissions;
  'backoffice.configuration'?: ModulePermissions;
  'backoffice.pipeline_operations'?: ModulePermissions;
  'backoffice.logs'?: ModulePermissions;
  'modules.headcount'?: ModulePermissions;
  'modules.equipment'?: ModulePermissions;
  'modules.professional_travel'?: ModulePermissions;
  'modules.buildings'?: ModulePermissions;
  'modules.purchase'?: ModulePermissions;
  'modules.research_facilities'?: ModulePermissions;
  'modules.external_cloud_and_ai'?: ModulePermissions;
  'modules.process_emissions'?: ModulePermissions;
  [key: string]: ModulePermissions | undefined;
}

/**
 * Custom affordance permission gating the module-status validate button.
 * Emitted as `module.status/<cf>` (cost center) to unit-breadth users only;
 * standard (own) users never receive it, so the button is hidden for them.
 */
export const MODULE_STATUS_PERMISSION = 'module.status';

/**
 * Check if a user has a specific permission.
 *
 * This function checks if an action is allowed for the given permission
 * path. Returns `false` for any edge cases (null permissions, missing
 * paths, invalid actions, etc.).
 *
 * @param permissions - The permissions object (from user.permissions), can be null/undefined
 * @param path - The permission path (e.g., 'modules.headcount')
 * @param action - The action to check (defaults to 'view')
 * @returns `true` if the permission exists and is `true`, `false` otherwise
 */
export function hasPermission(
  permissions: FlatUserPermissions | null | undefined,
  path: string,
  action: PermissionAction = PermissionAction.VIEW,
): boolean {
  // Null safety: return false if permissions is null/undefined
  if (!permissions) {
    return false;
  }

  // Edge case: permissions is not an object (could be array, primitive, etc.)
  if (typeof permissions !== 'object' || Array.isArray(permissions)) {
    return false;
  }

  // Edge case: path is null/undefined or not a string or empty/whitespace-only
  if (!path || typeof path !== 'string' || path.trim().length === 0) {
    return false;
  }

  // Edge case: action is null/undefined or not a string or empty/whitespace-only
  if (!action || typeof action !== 'string' || action.trim().length === 0) {
    return false;
  }

  try {
    // Edge case: path not in permissions
    if (!(path in permissions)) {
      return false;
    }

    const permSet = permissions[path];

    // Edge case: permission set is null/undefined or not an array (should be an array of allowed actions)
    if (permSet === null || permSet === undefined || !Array.isArray(permSet)) {
      return false;
    }

    // Check if the action exists in the permission set
    return permSet.includes(action);
  } catch (error) {
    // Edge case: any unexpected error (TypeError, etc.)
    // Log in development for debugging, but return false in production
    if (process.env.NODE_ENV === 'development') {
      console.warn('Error checking permission:', error, { path, action });
    }
    return false;
  }
}

/**
 * Check if the user has `action` on `path` under ANY scope.
 *
 * Matches the bare path (`backoffice.users`) AND any scoped variant
 * (`backoffice.users/ENAC-SG`, `backoffice.users/0184`). Mirrors the
 * backend's `has_permission(..., any_scope=True)` mode (see
 * `backend/app/utils/permissions.py`). Use for back-office routes/menu
 * items that should accept GlobalScope users, unit-scoped users, AND
 * affiliation-scoped users alike (#459).
 *
 * Do NOT use for unit-data routes — those need workspace-scoped checks
 * to enforce unit isolation. Use `hasPermission(...)` with a workspace
 * context instead.
 */
export function hasAnyScopePermission(
  permissions: FlatUserPermissions | null | undefined,
  path: string,
  action: PermissionAction = PermissionAction.VIEW,
): boolean {
  if (
    !permissions ||
    typeof permissions !== 'object' ||
    Array.isArray(permissions)
  ) {
    return false;
  }
  if (!path || typeof path !== 'string' || path.trim().length === 0) {
    return false;
  }
  const scopePrefix = `${path}/`;
  for (const [key, actions] of Object.entries(permissions)) {
    if (key !== path && !key.startsWith(scopePrefix)) continue;
    if (Array.isArray(actions) && actions.includes(action)) return true;
  }
  return false;
}

/**
 * Check if the user holds ANY back-office area permission granting `action`.
 *
 * The back-office area is the `backoffice.*` page family (reporting, users,
 * documentation, ui_texts, configuration, pipeline_operations, logs). Matches
 * bare keys (`backoffice.users`, emitted for GlobalScope / super admin) AND
 * affiliation-scoped keys (`backoffice.reporting/ENAC-SG`, emitted for ACCRED
 * sub-perimeter users). Used to gate UI entry points to the back-office area
 * as a whole (#459). The former `system.*` family was removed in #862.
 */
export function hasBackOfficeAreaPermission(
  permissions: FlatUserPermissions | null | undefined,
  action: PermissionAction = PermissionAction.VIEW,
): boolean {
  if (
    !permissions ||
    typeof permissions !== 'object' ||
    Array.isArray(permissions)
  ) {
    return false;
  }
  for (const [key, actions] of Object.entries(permissions)) {
    if (!key.startsWith('backoffice.')) continue;
    if (Array.isArray(actions) && actions.includes(action)) return true;
  }
  return false;
}

/**
 * Maps frontend module names to backend permission paths.
 * Only modules with defined permissions are included.
 *
 * @param module - The frontend module identifier (e.g., 'headcount', 'equipment')
 * @returns The permission path (e.g., 'modules.headcount', 'modules.equipment') or null if not protected
 */
export function getModulePermissionPath(module: Module): string | null {
  const modulePermissionMap: Record<Module, string | null> = {
    [MODULES.Headcount]: 'modules.headcount',
    [MODULES.Equipment]: 'modules.equipment',
    [MODULES.ProfessionalTravel]: 'modules.professional_travel',
    [MODULES.Buildings]: 'modules.buildings',
    [MODULES.Purchase]: 'modules.purchase',
    [MODULES.ResearchFacilities]: 'modules.research_facilities',
    [MODULES.ExternalCloudAndAI]: 'modules.external_cloud_and_ai',
    [MODULES.ProcessEmissions]: 'modules.process_emissions',
    [MODULES.Commuting]: null,
    [MODULES.Food]: null,
    [MODULES.Waste]: null,
    [MODULES.EmbodiedEnergy]: null,
  };
  return modulePermissionMap[module] || null;
}
