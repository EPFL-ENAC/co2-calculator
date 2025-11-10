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

  // Get language param (default to 'en')
  const language = to.params.language || 'en';

  // Protected route without authentication
  if (to.meta.requiresAuth && !authStore.user) {
    if (to.name !== 'login') {
      return next({ name: 'login', params: { language } });
    }
    return next();
  }

  // Already logged in, redirect from login page
  if (to.name === 'login' && authStore.user) {
    return next({
      name: 'home',
      params: { language, unit: 'defaultUnit', year: '2025' },
    });
  }

  // All other case
  next();
}
