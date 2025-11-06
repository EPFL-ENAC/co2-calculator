import { route } from 'quasar/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';

import routes from './routes';
import { useAuthStore } from 'src/stores/auth';
import { getCurrentLanguage, routeLanguageToLocale } from 'src/utils/language';
import { i18n } from 'src/boot/i18n';
import { Language } from 'src/types';

/*
 * If not building with SSR mode, you can
 * directly export the Router instantiation;
 *
 * The function below can be async too; either use
 * async/await or return a Promise which resolves
 * with the Router instance.
 */

export default route(function (/* { store, ssrContext } */) {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : process.env.VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory;

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,

    // Leave this as is and make changes in quasar.conf.js instead!
    // quasar.conf.js -> build -> vueRouterMode
    // quasar.conf.js -> build -> publicPath
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  // Navigation guards
  Router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();

    // Don't intercept API routes
    if (to.path.startsWith('/api/')) {
      return next();
    }

    // Sync language parameter with i18n locale
    if (to.params.language) {
      const routeLang = getCurrentLanguage({
        language: to.params.language as Language,
      });
      const i18nLocale = routeLanguageToLocale(routeLang);
      if (i18n.global.locale.value !== i18nLocale) {
        i18n.global.locale.value =
          i18nLocale as typeof i18n.global.locale.value;
      }
    }

    // Wait for auth to finish loading
    if (authStore.loading) {
      return next();
    }

    // Protected route without authentication
    if (to.meta.requiresAuth && !authStore.user) {
      const loginPath = to.params.language
        ? `/${to.params.language}/login`
        : '/en/login';
      if (!to.path.includes('/login')) {
        return next(loginPath);
      }
      return next();
    }

    // Already logged in, redirect from login page
    if (to.path.includes('/login') && authStore.user) {
      const setupPath = to.params.language
        ? `/${to.params.language}/workspace-setup`
        : '/en/workspace-setup';
      if (!from.path.includes('/workspace-setup')) {
        return next(setupPath);
      }
      return next();
    }

    // All other case
    next();
  });

  return Router;
});
