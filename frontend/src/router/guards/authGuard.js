import { useAuthStore } from 'src/stores/auth';

export function authGuard(to, from, next) {
  const authStore = useAuthStore();

  // Don't intercept API routes
  if (to.path.startsWith('/api/')) {
    return next();
  }

  // Note: Loading state is not handled yet.
  // Currently, this just calls next() immediately, which may let users access protected routes before auth is loaded.
  if (authStore.loading) {
    return next();
  }

  // Protected route without authentication
  if (to.meta.requiresAuth && !authStore.user) {
    if (to.path !== '/login') {
      return next('/login');
    }
    return next();
  }

  // Already logged in, redirect from login page
  if (to.path === '/login' && authStore.user) {
    if (from.path !== '/workspace-setup') {
      return next('/workspace-setup');
    }
    return next();
  }

  // All other case
  next();
}
