import { useAuthStore } from 'src/stores/auth';
import { Cookies } from 'quasar';

function hasWorkspaceCookies() {
  const unitName = Cookies.get('workspace_unit_name');
  const year = Cookies.get('workspace_year');
  return Boolean(unitName && year);
}

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

  // If logged in, enforce workspace selection via cookies
  if (authStore.user) {
    const hasWs = hasWorkspaceCookies();
    const unit = Cookies.get('workspace_unit_name') || 'unit';
    const year = Cookies.get('workspace_year') || '';

    // If on login and already logged in, redirect
    if (to.name === 'login') {
      return next(
        hasWs
          ? { name: 'home', params: { language, unit, year } }
          : { name: 'workspace-setup', params: { language } },
      );
    }

    // If trying to access anything other than workspace setup and no workspace chosen, redirect to setup
    if (to.name !== 'workspace-setup' && !hasWs) {
      return next({ name: 'workspace-setup', params: { language } });
    }

    // If already have workspace and trying to go to setup, redirect to home
    if (to.name === 'workspace-setup' && hasWs) {
      return next({ name: 'home', params: { language, unit, year } });
    }
  }

  // All other case
  next();
}
