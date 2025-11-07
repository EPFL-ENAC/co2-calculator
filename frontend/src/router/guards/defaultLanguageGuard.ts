import { RouteLocationNormalized, NavigationGuardNext } from 'vue-router';

export async function defaultLanguageGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  if (to.params.language) {
    return next();
  }

  const redirect =
    to.path === '/'
      ? { name: 'login', params: { language: 'en' } }
      : { name: to.name || 'home', params: { language: 'en', ...to.params } };

  next(redirect);
}
