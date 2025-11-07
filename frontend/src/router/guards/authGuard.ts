import { useAuthStore } from 'src/stores/auth';
import { RouteLocationNormalized, NavigationGuardNext } from 'vue-router';

export async function authGuard(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  // TODO: REWRITE COMPLETELY
  const authStore = useAuthStore();

  // Block navigation until loading is false
  if (authStore.loading) {
    return next(false);
  }

  // Centralize login paths
  const LOGIN_ROUTE_NAME = 'login';

  // Implement user sync on refresh only if not authenticated
  if (!authStore.isAuthenticated) {
    await authStore.fetchUser().catch(() => {
      // Handle fetch error (e.g., redirect to login or show error)
      return next({ name: LOGIN_ROUTE_NAME });
    });
  }

  // Get language param (consider deriving from user preference)
  const language = to.params.language || 'en';

  // Protected route without authentication
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({ name: LOGIN_ROUTE_NAME });
  }

  // Add role-based checks only if authenticated
  if (
    authStore.isAuthenticated &&
    to.meta.roles &&
    !to.meta.roles.includes(authStore.user.role)
  ) {
    return next({ name: 'unauthorized' });
  }

  // Already logged in, redirect from login page
  if (to.name === 'login' && authStore.user) {
    return next({ name: 'home', params: { language } }); // Consider dynamic params
  }

  // Proceed to the next route
  next();
}
