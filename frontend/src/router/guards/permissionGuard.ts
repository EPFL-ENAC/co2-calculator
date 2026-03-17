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
 * Route guard that requires view permission for the module in the route.
 * Standard users without view permission will be redirected to unauthorized.
 *
 * This guard checks the module parameter from the route and verifies
 * that the user has view permission (if module is protected).
 *
 * Edit permissions are handled in the module page.
 */
export function requireModulePermission() {
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

    return true;
  };
}
