import { route } from 'quasar/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';

import routes from './routes';
import { authGuard } from './guards/authGuard';
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

  /*
 EXPECTED BEHAVIOR workspace-setup IS THE DEFAULT ROUTE
  ** LOGGED IN USERS **
  / -> redirect to /:language(workspace-setup) with current locale
  /en -> redirect to /en/workspace-setup
  /en/login -> redirect to /en/workspace-setup
  /en/403 -> show 404\
  /404 -> show 404
  /unauthorized -> show 403

  // not logged in
  /en/workspace-setup when not authenticated -> redirect to /en/login
  /en/login -> show login page
  / -> redirect to /:language/login with current locale
  /en -> redirect to /en/login
*/

  // Navigation guards
  Router.beforeEach(defaultLanguageGuard);
  Router.beforeEach(setLanguageCookieGuard);
  Router.beforeEach(authGuard);

  return Router;
});
