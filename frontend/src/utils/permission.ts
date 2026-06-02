/**
 * Permission utility functions for checking user permissions.
 *
 * These utilities work with the flat permission structure returned by the backend.
 * They provide type-safe, null-safe ways to check user permissions.
 *
 * @see {@link ../constant/permissions | Permission types}
 */

import type { FlatUserPermissions } from 'src/constant/permissions';
import { PermissionAction } from 'src/constant/permissions';
import { MODULES, type Module } from 'src/constant/modules';

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
 * Check if the user has UNIT-level (or global) breadth on `path`.
 *
 * Matches a bare `path` key (global / super admin) or a unit-scoped
 * `path/<unit>` key (principal), but NOT the own-scoped `path/<unit>/own`
 * key (standard user). Mirrors the backend `resolve_module_scope` returning
 * `"unit"`/`"global"` (see `backend/app/utils/permissions.py`). Use this to
 * gate unit-level controls — e.g. validating a module's status — which a
 * standard user must not see even though they can edit their own records.
 */
export function hasUnitScopePermission(
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
    const isGlobal = key === path;
    const isUnit = key.startsWith(scopePrefix) && !key.endsWith('/own');
    if (!isGlobal && !isUnit) continue;
    if (Array.isArray(actions) && actions.includes(action)) return true;
  }
  return false;
}

/**
 * Maps frontend module names to backend permission paths.
 * Only modules with defined permissions are included.
 *
 * @param module - The frontend module identifier (e.g., 'headcount', 'equipment-electric-consumption')
 * @returns The permission path (e.g., 'modules.headcount', 'modules.equipment') or null if not protected
 */
export function getModulePermissionPath(module: Module): string | null {
  const modulePermissionMap: Record<Module, string | null> = {
    [MODULES.Headcount]: 'modules.headcount',
    [MODULES.EquipmentElectricConsumption]: 'modules.equipment',
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
