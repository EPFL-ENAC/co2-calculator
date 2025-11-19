import { useAuthStore } from 'src/stores/auth';
import { RouteLocationNormalized } from 'vue-router';

// Authentication guard for protected routes

export async function authGuard(to: RouteLocationNormalized) {
  const auth = useAuthStore();

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
    return { name: 'login', ...redirectTo };
  }

  // Role-based authorization
  if (to.meta.roles && auth.isAuthenticated) {
    const roles = Array.from(to.meta.roles as string[]);
    const allowed = roles.some((r) => auth.user.roles.includes(r));
    if (!allowed) {
      return { name: 'unauthorized', ...redirectTo };
    }
  }

  // Redirect authenticated users away from login
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'workspace-setup', ...redirectTo };
  }

  return true;
}
