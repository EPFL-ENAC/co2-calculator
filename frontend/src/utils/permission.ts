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
