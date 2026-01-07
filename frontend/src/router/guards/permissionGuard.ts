import { useAuthStore } from 'src/stores/auth';
import type {
  RouteLocationNormalized,
  NavigationGuardReturn,
} from 'vue-router';
import {
  getPermissionValue,
  hasPermission,
  getModulePermissionPath,
} from 'src/utils/permission';
import { PermissionAction } from 'src/constant/permissions';
import { MODULES } from 'src/constant/modules';
import type { Module } from 'src/constant/modules';

/**
 * Create a route guard that requires a specific permission.
 *
 * This function returns a Vue Router navigation guard that checks if the user
 * has the required permission. If the permission is granted, navigation proceeds.
 * If not, the user is redirected to the unauthorized page.
 *
 * @param path - The permission path (e.g., 'modules.headcount')
 * @param action - The action to check (defaults to 'view')
 * @returns A navigation guard function compatible with Vue Router's `beforeEnter`
 *
 * @example
 * ```typescript
 * // Usage in routes
 * {
 *   path: '/headcount',
 *   component: HeadcountPage,
 *   beforeEnter: requirePermission('modules.headcount', 'view')
 * }
 *
 * // With edit permission
 * {
 *   path: '/equipment/edit',
 *   component: EditEquipmentPage,
 *   beforeEnter: requirePermission('modules.equipment', 'edit')
 * }
 * ```
 */
export function requirePermission(
  path: string,
  action: string = PermissionAction.VIEW,
) {
  return (): NavigationGuardReturn => {
    const authStore = useAuthStore();
    const hasRequiredPermission = getPermissionValue(
      authStore.user?.permissions,
      `${path}.${action}`,
    );
    if (hasRequiredPermission === true) {
      return true;
    } else {
      return { name: 'unauthorized' };
    }
  };
}

/**
 * Route guard that requires edit permission for the module in the route.
 * Standard users without view permission will be blocked entirely.
 * Standard users with view but not edit permission will be redirected to unauthorized.
 *
 * Exception: professional-travel module allows view permission (read-only access for API data).
 *
 * This guard checks the module parameter from the route and verifies:
 * 1. That the user has view permission (if module is protected)
 * 2. That the user has edit permission (required for data entry, except professional-travel)
 */
export function requireModuleEditPermission() {
  return (to: RouteLocationNormalized): NavigationGuardReturn => {
    const authStore = useAuthStore();
    const module = to.params.module as Module;

    // Get the permission path for this module
    const permissionPath = getModulePermissionPath(module);

    // If module doesn't have a permission path, allow access (not yet protected)
    if (!permissionPath) {
      return true;
    }

    // First check if user has view permission (standard users without view should be blocked)
    const hasViewPermission = hasPermission(
      authStore.user?.permissions,
      permissionPath,
      PermissionAction.VIEW,
    );

    if (!hasViewPermission) {
      // User doesn't have view permission - block access entirely
      return { name: 'unauthorized' };
    }

    // Professional-travel module allows view permission (read-only access for API data)
    if (module === MODULES.ProfessionalTravel) {
      return true;
    }

    // Check if user has edit permission (required for data entry for other modules)
    const hasEditPermission = hasPermission(
      authStore.user?.permissions,
      permissionPath,
      PermissionAction.EDIT,
    );

    if (hasEditPermission) {
      return true;
    } else {
      // User has view but not edit - redirect to unauthorized
      return { name: 'unauthorized' };
    }
  };
}
