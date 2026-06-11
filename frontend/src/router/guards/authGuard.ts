import { useAuthStore } from 'src/stores/auth';
import { RouteLocationNormalized } from 'vue-router';
import { LOGIN_ROUTES } from '../routeNames';
// Authentication guard for protected routes

export async function authGuard(to: RouteLocationNormalized) {
  // Lighthouse CI injects window.__LIGHTHOUSE_BYPASS__ at runtime to audit
  // protected pages without a backend. All auth checks are skipped.
  if (window.__LIGHTHOUSE_BYPASS__) return true;

  // Skip the auto-getUser() probe on routes that handle their own auth
  // bootstrap. Otherwise the BFF cookie-exchange landing (/auth/complete)
  // races: the guard probes /session, gets 401 (cookies don't exist yet),
  // triggers the 401-interceptor refresh which also 401s — and only THEN
  // does the page's onMounted POST /session/exchange. Two noisy 401s
  // every login. Routes opt out via `meta.skipAuthCheck: true`. Placed
  // BEFORE useAuthStore() so the short-circuit works without Pinia
  // (lets the guard be unit-tested without a store fixture, too).
  if (to.meta.skipAuthCheck) return true;

  const auth = useAuthStore();

  // Load user if needed
  if (!auth.hasChecked && !auth.loading) {
    try {
      await auth.getUser();
    } catch (e) {
      console.error('Failed to load user:', e);
      // No need to do anything else: the guard logic below will redirect if needed
    }
  }
  const redirectTo = { params: to.params };

  // Requires auth?
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', ...redirectTo };
  }

  // Role-based authorization
  if (to.meta.roles && auth.isAuthenticated) {
    const roles = Array.from(to.meta.roles as string[]);
    const allowed = roles.some((r) =>
      auth.user.roles_raw.map((x) => x.role).includes(r),
    );
    if (!allowed) {
      return { name: 'unauthorized', ...redirectTo };
    }
  }

  // Redirect authenticated users away from login
  if (LOGIN_ROUTES.includes(to.name as string) && auth.isAuthenticated) {
    return { name: 'workspace-setup', ...redirectTo };
  }

  return true;
}
