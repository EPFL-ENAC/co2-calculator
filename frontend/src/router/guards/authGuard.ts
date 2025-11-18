import { useAuthStore } from 'src/stores/auth';
import { RouteLocationNormalized } from 'vue-router';
import {
  ROUTES_WITHOUT_LANGUAGE,
  DEFAULT_ROUTE_NAME,
  LOGIN_ROUTE_NAME,
  UNAUTHORIZED_ROUTE_NAME,
} from 'src/router/routes';

// Authentication guard for protected routes

export async function authGuard(to: RouteLocationNormalized) {
  const auth = useAuthStore();

  if (ROUTES_WITHOUT_LANGUAGE.includes(to.name as string)) {
    // Initial load, no need to redirect
    return true;
  }
  // Load user if needed
  if (auth.loading) {
    try {
      await auth.getUser();
    } catch {
      /* ignore */
    }
  }
  const redirectTo = { params: to.params };

  // Requires auth?
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: LOGIN_ROUTE_NAME, ...redirectTo };
  }

  // Role-based authorization
  if (to.meta.roles && auth.isAuthenticated) {
    const roles = Array.from(to.meta.roles as string[]);
    const allowed = roles.some((r) => auth.user.roles.includes(r));
    if (!allowed) {
      return { name: UNAUTHORIZED_ROUTE_NAME, ...redirectTo };
    }
  }

  // Redirect authenticated users away from login
  if (to.name === LOGIN_ROUTE_NAME && auth.isAuthenticated) {
    return { name: DEFAULT_ROUTE_NAME, ...redirectTo };
  }

  return true;
}
