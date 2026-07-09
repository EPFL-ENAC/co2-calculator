import { useAuthStore, PermissionAction } from 'src/stores/auth';
import type {
  RouteLocationNormalized,
  NavigationGuardReturn,
} from 'vue-router';
import type { Module } from 'src/constant/modules';

/**
 * Single permission guard for route `beforeEnter`.
 *
 * - Module routes (`meta.moduleEdit`) are gated by `canUserAccessModule` on the
 *   route's `:module` param: workspace-scoped view AND edit (data entry needs
 *   edit breadth). The sidebar, the prev/next arrows and the home "start"
 *   button filter on that same predicate, so a rendered affordance can never
 *   land the user on `/unauthorized` (#1382).
 * - Back-office routes declare `meta.requiredPermission` (+ optional
 *   `meta.requiredAction`, default view), checked any-scope so affiliation- and
 *   unit-suffixed keys match. `meta.requiredPermission` is the single source of
 *   truth: `Co2Sidebar` reads the same meta for reachability, so router and nav
 *   can never drift. Routes with neither flag are not gated here.
 */
export function permissionGuard(
  to: RouteLocationNormalized,
): NavigationGuardReturn {
  // Lighthouse CI bypass: allow all routes regardless of permissions.
  if (window.__LIGHTHOUSE_BYPASS__) return true;

  const authStore = useAuthStore();

  if (to.meta.moduleEdit) {
    const module = to.params.module as Module;
    if (!authStore.canUserAccessModule(module)) {
      return { name: 'unauthorized' };
    }
    return true;
  }

  const path = to.meta.requiredPermission as string | undefined;
  if (!path) return true;
  const action =
    (to.meta.requiredAction as PermissionAction | undefined) ??
    PermissionAction.VIEW;
  if (authStore.hasUserAnyScopePermission(path, action)) return true;

  console.warn(
    `[permissionGuard] denied: '${path}' (${action}); redirecting to unauthorized`,
  );
  return { name: 'unauthorized' };
}
