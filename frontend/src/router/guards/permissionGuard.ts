import { useAuthStore } from 'src/stores/auth';
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router';
import { getPermissionValue } from 'src/utils/permission';
import { PermissionAction } from 'src/constant/permissions';

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
  return (
    to: RouteLocationNormalized,
    from: RouteLocationNormalized,
    next: NavigationGuardNext,
  ) => {
    const authStore = useAuthStore();
    const hasPermission = getPermissionValue(
      authStore.user?.permissions,
      `${path}.${action}`,
    );

    if (hasPermission === true) {
      next();
    } else {
      next({ name: 'unauthorized' });
    }
  };
}
