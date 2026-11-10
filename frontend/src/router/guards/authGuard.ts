import { useAuthStore } from '@/stores/auth';
import { RouteLocationNormalized } from 'vue-router';
import { LOGIN_ROUTES, DEFAULT_ROUTE_NAME } from '../routeNames';
// Authentication guard for protected routes

export async function authGuard(to: RouteLocationNormalized) {
  // Lighthouse CI injects window.__LIGHTHOUSE_BYPASS__ at runtime to audit
  // protected pages without a backend. All auth checks are skipped.
  if (window.__LIGHTHOUSE_BYPASS__) return true;

  const auth = useAuthStore();

  // Load user (+ units + configured years) in one call, and again once the
  // last check is old: that call is also what renews the cookie (#2983).
  if (auth.sessionCheckDue() && !auth.loading) {
    try {
      await auth.bootstrap();
    } catch (e: unknown) {
      console.error('Failed to load session:', e);
    }
  }
  // Not "logged out": App.vue shows the retry notice (#2983).
  if (auth.sessionUnavailable) return false;
  const redirectTo = { params: to.params };

  // Requires auth?
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', ...redirectTo };
  }

  // Redirect authenticated users away from login
  if (LOGIN_ROUTES.includes(to.name as string) && auth.isAuthenticated) {
    return { name: DEFAULT_ROUTE_NAME, ...redirectTo };
  }

  return true;
}
