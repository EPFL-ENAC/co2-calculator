import { useAuthStore } from '@/stores/auth';
import { RouteLocationNormalized } from 'vue-router';
import {
  LOGIN_ROUTES,
  LOGIN_ROUTE_NAME,
  DEFAULT_ROUTE_NAME,
} from '../routeNames';
import { authenticatedShell } from '../authenticatedShell';
import { loginPage } from '../loginPage';
import { clearFirstFrame } from '@/boot/first-frame';
// Authentication guard for protected routes

export async function authGuard(to: RouteLocationNormalized) {
  // Lighthouse CI injects window.__LIGHTHOUSE_BYPASS__ at runtime to audit
  // protected pages without a backend. All auth checks are skipped.
  if (window.__LIGHTHOUSE_BYPASS__) {
    if (to.meta.requiresAuth) authenticatedShell.preload();
    return true;
  }

  const auth = useAuthStore();

  // Load user (+ units + configured years) if needed, in a single bootstrap call.
  if (!auth.hasChecked && !auth.loading) {
    // The session is not known yet, so this is the first navigation.
    if (to.name === LOGIN_ROUTE_NAME) loginPage.preload();
    try {
      await auth.bootstrap();
    } catch (e) {
      console.error('Failed to load user:', e);
      // No need to do anything else: the guard logic below will redirect if needed
    }
  }
  if (auth.isAuthenticated) {
    // A signed-in visitor of the login URL goes home: no login title.
    clearFirstFrame();
    authenticatedShell.preload();
  }
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
