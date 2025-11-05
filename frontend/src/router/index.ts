import { route } from 'quasar/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';

import routes from './routes';
import { useAuthStore } from 'src/stores/auth';

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

    // Wait for auth to finish loading
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
  });

  return Router;
});
