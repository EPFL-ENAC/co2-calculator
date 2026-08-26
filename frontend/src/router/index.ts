import { defineRouter } from '#q-app';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';

import routes from './routes';
import { authGuard } from './guards/authGuard';
import workspaceGuard from './guards/workspaceGuard';
import {
  defaultLanguageGuard,
  setLanguageCookieGuard,
} from './guards/defaultLanguageGuard';
/*
 * If not building with SSR mode, you can
 * directly export the Router instantiation;
 *
 * The function below can be async too; either use
 * async/await or return a Promise which resolves
 * with the Router instance.
 */

export default defineRouter(function (/* { store, ssrContext } */) {
  const createHistory = import.meta.env.QUASAR_SERVER
    ? createMemoryHistory
    : import.meta.env.QUASAR_VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory;

  const Router = createRouter({
    // scrollBehavior: () => ({ left: 0, top: 0 }),
    scrollBehavior: (to, from, savedPosition) => {
      // If user clicked back/forward, restore position
      if (savedPosition) {
        return savedPosition;
      }
      // Only scroll to top if path actually changed
      if (to.path !== from.path) {
        return { left: 0, top: 0 };
      }
      // Don't scroll if only query params changed
      return false;
    },
    routes,

    // Leave this as is and make changes in quasar.conf.js instead!
    // quasar.conf.js -> build -> vueRouterMode
    // quasar.conf.js -> build -> publicPath
    history: createHistory(import.meta.env.QUASAR_VUE_ROUTER_BASE),
  });

  /*
 EXPECTED BEHAVIOR — the parameterless landing (/en) IS THE DEFAULT ROUTE.
 It renders nothing: its guard resolves a default unit/year and forwards to
 the unified home page (/en/:unit/:year/home), or to /unauthorized when the
 account has no units.

  ** LOGGED IN USERS **
  /              -> redirect to /:language with current locale
  /en            -> resolve default workspace -> /en/:unit/:year/home
  /en/login      -> redirect to /en (already authenticated)
  /unauthorized  -> show the access-denied page (ErrorUnauthorized.vue)
  any other path -> catch-all -> show 404 (ErrorNotFound.vue)

  ** NOT LOGGED IN **
  /              -> redirect to /:language/login with current locale
  /en            -> redirect to /en/login
  /en/login      -> show the login page
*/

  // Navigation guards
  Router.beforeEach(defaultLanguageGuard);
  Router.beforeEach(setLanguageCookieGuard);
  Router.beforeEach(authGuard);
  Router.beforeEach(workspaceGuard);

  return Router;
});
