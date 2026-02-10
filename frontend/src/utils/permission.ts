/**
 * Permission utility functions for checking user permissions.
 *
 * These utilities work with the flat permission structure returned by the backend.
 * They provide type-safe, null-safe ways to check user permissions.
 *
 * @see {@link ../constant/permissions | Permission types}
 */

import type {
  FlatUserPermissions,
  PermissionPath,
} from 'src/constant/permissions';
import { PermissionAction } from 'src/constant/permissions';
import { MODULES, type Module } from 'src/constant/modules';

/**
 * Check if a user has a specific permission.
 *
 * This function checks if a permission exists and is set to `true` for the given
 * path and action. Returns `false` for any edge cases (null permissions, missing
 * paths, invalid actions, etc.).
 *
 * @param permissions - The permissions object (from user.permissions), can be null/undefined
 * @param path - The permission path (e.g., 'modules.headcount')
 * @param action - The action to check (defaults to 'view')
 * @returns `true` if the permission exists and is `true`, `false` otherwise
 *
 * @example
 * ```typescript
 * // Check if user can view headcount module
 * const canView = hasPermission(user.permissions, 'modules.headcount', 'view');
 * if (canView) {
 *   // Show headcount module
 * }
 *
 * // Check if user can edit equipment (using enum)
 * const canEdit = hasPermission(
 *   user.permissions,
 *   'modules.equipment',
 *   PermissionAction.EDIT
 * );
 * ```
 */
export function hasPermission(
  permissions: FlatUserPermissions | null | undefined,
  path: PermissionPath | string,
  action: PermissionAction | string = PermissionAction.VIEW,
): boolean {
  // Null safety: return false if permissions is null/undefined
  if (!permissions) {
    return false;
  }

  // Edge case: permissions is not an object (could be array, primitive, etc.)
  if (typeof permissions !== 'object' || Array.isArray(permissions)) {
    return false;
  }

  // Edge case: path is null/undefined or not a string
  if (!path || typeof path !== 'string') {
    return false;
  }

  // Edge case: path is empty or whitespace-only
  if (path.trim().length === 0) {
    return false;
  }

  // Edge case: action is null/undefined or not a string
  if (!action || typeof action !== 'string') {
    return false;
  }

  // Edge case: action is empty or whitespace-only
  if (action.trim().length === 0) {
    return false;
  }

  try {
    // Edge case: path not in permissions
    if (!(path in permissions)) {
      return false;
    }

    const permSet = permissions[path];

    // Edge case: permission set is null/undefined
    if (permSet === null || permSet === undefined) {
      return false;
    }

    // Edge case: permission set is not an object (could be array, primitive, etc.)
    if (typeof permSet !== 'object' || Array.isArray(permSet)) {
      return false;
    }

    // Edge case: action not in permission set
    if (!(action in permSet)) {
      return false;
    }

    const value = permSet[action];

    // Edge case: value is null/undefined (explicitly check for null)
    if (value === null || value === undefined) {
      return false;
    }

    // Return the boolean value (coerce to boolean for safety)
    return Boolean(value);
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
 * Get the value of a specific permission using a full dot-notation path.
 *
 * This function parses a full path like "modules.headcount.view" and returns
 * the permission value. Returns `undefined` if the path is invalid or the
 * permission doesn't exist.
 *
 * @param permissions - The permissions object (from user.permissions), can be null/undefined
 * @param fullPath - Full dot-notation path including action (e.g., 'backoffice.users.edit')
 * @returns The permission value (`true`/`false`), or `undefined` if not found
 *
 * @example
 * ```typescript
 * // Get edit permission for backoffice users
 * const canEditUsers = getPermissionValue(
 *   user.permissions,
 *   'backoffice.users.edit'
 * );
 * if (canEditUsers === true) {
 *   // User can edit backoffice users
 * }
 *
 * // Check if permission exists (undefined means it doesn't exist)
 * const viewPerm = getPermissionValue(
 *   user.permissions,
 *   'modules.headcount.view'
 * );
 * if (viewPerm === undefined) {
 *   // Permission path is invalid or doesn't exist
 * }
 * ```
 */
export function getPermissionValue(
  permissions: FlatUserPermissions | null | undefined,
  fullPath: string,
): boolean | undefined {
  // Null safety: return undefined if permissions is null/undefined
  if (!permissions) {
    return undefined;
  }

  // Edge case: permissions is not an object (could be array, primitive, etc.)
  if (typeof permissions !== 'object' || Array.isArray(permissions)) {
    return undefined;
  }

  // Edge case: fullPath is null/undefined or not a string
  if (!fullPath || typeof fullPath !== 'string') {
    return undefined;
  }

  // Edge case: fullPath is empty or whitespace-only
  const trimmedPath = fullPath.trim();
  if (trimmedPath.length === 0) {
    return undefined;
  }

  try {
    // Split into resource path and action from the right (like Python's rsplit)
    // e.g., "modules.headcount.view" -> ["modules.headcount", "view"]
    const lastDotIndex = trimmedPath.lastIndexOf('.');
    if (lastDotIndex === -1) {
      // Edge case: no dot found, invalid path format (needs at least "resource.action")
      return undefined;
    }

    // Edge case: dot is at the start or end (e.g., ".action" or "resource.")
    if (lastDotIndex === 0 || lastDotIndex === trimmedPath.length - 1) {
      return undefined;
    }

    const resourcePath = trimmedPath.substring(0, lastDotIndex);
    const action = trimmedPath.substring(lastDotIndex + 1);

    // Edge case: empty resource path or action after split
    if (!resourcePath || !action) {
      return undefined;
    }

    // Edge case: resource path or action is whitespace-only after trimming
    if (resourcePath.trim().length === 0 || action.trim().length === 0) {
      return undefined;
    }

    return getPermissionValueByParts(
      permissions,
      resourcePath.trim(),
      action.trim(),
    );
  } catch (error) {
    // Edge case: any unexpected error (TypeError, etc.)
    // Log in development for debugging, but return undefined in production
    if (process.env.NODE_ENV === 'development') {
      console.warn('Error getting permission value:', error, { fullPath });
    }
    return undefined;
  }
}

/**
 * Internal helper function to get permission value by resource path and action.
 *
 * @param permissions - The permissions object
 * @param resourcePath - The resource path (e.g., 'modules.headcount')
 * @param action - The action (e.g., 'view')
 * @returns The permission value or undefined
 */
function getPermissionValueByParts(
  permissions: FlatUserPermissions,
  resourcePath: string,
  action: string,
): boolean | undefined {
  // Edge case: resourcePath is null/undefined or not a string
  if (!resourcePath || typeof resourcePath !== 'string') {
    return undefined;
  }

  // Edge case: action is null/undefined or not a string
  if (!action || typeof action !== 'string') {
    return undefined;
  }

  // Edge case: resourcePath or action is empty or whitespace-only
  if (resourcePath.trim().length === 0 || action.trim().length === 0) {
    return undefined;
  }

  try {
    // Edge case: resource path not in permissions
    if (!(resourcePath in permissions)) {
      return undefined;
    }

    const permSet = permissions[resourcePath];

    // Edge case: permission set is null/undefined
    if (permSet === null || permSet === undefined) {
      return undefined;
    }

    // Edge case: permission set is not an object (could be array, primitive, etc.)
    if (typeof permSet !== 'object' || Array.isArray(permSet)) {
      return undefined;
    }

    // Edge case: action not in permission set
    if (!(action in permSet)) {
      return undefined;
    }

    // Return the boolean value
    const value = permSet[action];

    // Edge case: value is null/undefined (explicitly check for null)
    if (value === null || value === undefined) {
      return undefined;
    }

    // Return boolean value (coerce to boolean for consistency)
    return Boolean(value);
  } catch (error) {
    // Edge case: any unexpected error
    if (process.env.NODE_ENV === 'development') {
      console.warn('Error in getPermissionValueByParts:', error, {
        resourcePath,
        action,
      });
    }
    return undefined;
  }
}

/**
 * Maps frontend module names to backend permission paths.
 * Only modules with defined permissions are included.
 *
 * @param module - The frontend module identifier (e.g., 'headcount', 'equipment-electric-consumption')
 * @returns The permission path (e.g., 'modules.headcount', 'modules.equipment') or null if not protected
 *
 * @example
 * ```typescript
 * const path = getModulePermissionPath('headcount');
 * // Returns: 'modules.headcount'
 *
 * const path = getModulePermissionPath('equipment-electric-consumption');
 * // Returns: 'modules.equipment'
 *
 * const path = getModulePermissionPath('professional-travel');
 * // Returns: null (not yet protected)
 * ```
 */
export function getModulePermissionPath(module: Module): string | null {
  const modulePermissionMap: Record<Module, string | null> = {
    [MODULES.Headcount]: 'modules.headcount',
    [MODULES.EquipmentElectricConsumption]: 'modules.equipment',
    [MODULES.ProfessionalTravel]: 'modules.professional_travel',
    [MODULES.Infrastructure]: 'modules.infrastructure',
    [MODULES.Purchase]: 'modules.purchase',
    [MODULES.InternalServices]: 'modules.internal_services',
    [MODULES.ExternalCloudAndAI]: 'modules.external_cloud_and_ai',
  };
  return modulePermissionMap[module] || null;
}
