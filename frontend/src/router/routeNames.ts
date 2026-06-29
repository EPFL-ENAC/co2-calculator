/**
 * Route name constants and routing allowlists.
 *
 * Extracted from `routes.ts` so consumers (guards, tests) can depend on
 * the symbolic identifiers without transitively importing the full
 * route configuration — which pulls in i18n's `import.meta.glob` and
 * breaks bare-Node test runners (Playwright unit tests, etc.).
 *
 * Anything in this file MUST stay free of Vite-specific imports and
 * runtime side effects.
 */

export const LOGIN_ROUTE_NAME = 'login';
export const LOGIN_TEST_ROUTE_NAME = 'login-test';
export const LOGIN_ROUTES = [LOGIN_ROUTE_NAME, LOGIN_TEST_ROUTE_NAME];
export const HOME_ROUTE_NAME = 'home';
export const WORKSPACE_SETUP_ROUTE_NAME = 'workspace-setup';
export const WORKSPACE_ROUTE_NAME = 'workspace-dashboard';
export const UNAUTHORIZED_ROUTE_NAME = 'unauthorized';
export const NOT_FOUND_ROUTE_NAME = 'not-found';
export const DEFAULT_ROUTE_NAME = WORKSPACE_SETUP_ROUTE_NAME;

export const ROUTES_WITHOUT_LANGUAGE = [
  NOT_FOUND_ROUTE_NAME,
  UNAUTHORIZED_ROUTE_NAME,
];
