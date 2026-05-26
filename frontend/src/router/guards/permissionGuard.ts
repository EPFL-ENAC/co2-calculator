import { useAuthStore } from 'src/stores/auth';
import type {
  RouteLocationNormalized,
  NavigationGuardReturn,
} from 'vue-router';
import { PermissionAction } from 'src/constant/permissions';
import type { Module } from 'src/constant/modules';

/**
 * Create a route guard that requires a specific permission under ANY scope.
 *
 * Accepts the bare path (`backoffice.users`) OR any scoped variant
 * (`backoffice.users/ENAC-SG`, `backoffice.users/0184`). This is the
 * right shape for back-office and system routes — affiliation-scoped
 * users and unit-scoped users both pass. Module routes use
 * `requireModuleEditPermission` instead (workspace-scoped).
 *
 * @param path - The permission path (e.g., 'backoffice.users')
 * @param action - The action to check (defaults to 'view')
 * @returns A navigation guard function compatible with Vue Router's `beforeEnter`
 */
export function requirePermission(
  path: string,
  action: PermissionAction = PermissionAction.VIEW,
) {
  return (): NavigationGuardReturn => {
    // Lighthouse CI bypass: allow all routes regardless of permissions.
    if (window.__LIGHTHOUSE_BYPASS__) return true;

    const authStore = useAuthStore();
    if (authStore.hasUserAnyScopePermission(path, action)) {
      return true;
    }
    console.warn(
      `[permissionGuard] denied: '${path}' (${action}); redirecting to unauthorized`,
    );
    return { name: 'unauthorized' };
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
    // Lighthouse CI bypass: allow all module routes regardless of permissions.
    if (window.__LIGHTHOUSE_BYPASS__) return true;

    const authStore = useAuthStore();
    const module = to.params.module as Module;

    // First check if user has view permission (standard users without view should be blocked)
    const hasViewPermission = authStore.hasUserModulePermission(
      module,
      PermissionAction.VIEW,
    );

    if (!hasViewPermission) {
      // User doesn't have view permission - block access entirely
      return { name: 'unauthorized' };
    }

    // Check if user has edit permission (required for data entry for other modules)
    const hasEditPermission = authStore.hasUserModulePermission(
      module,
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
