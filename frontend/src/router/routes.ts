import { RouteLocationNormalized, RouteRecordRaw } from 'vue-router';
import { MODULES_PATTERN } from 'src/constant/modules';
import { i18n } from 'src/boot/i18n';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/navigation';
import redirectToWorkspaceIfSelectedGuard from './guards/redirectToWorkspaceIfSelectedGuard';
import validateUnitGuard from './guards/validateUnitGuard';

// Route parameter validation patterns
const LANGUAGE_PATTERN = 'en|fr';
const YEAR_PATTERN = '\\d{4}';
const UNIT_PATTERN = '[^/]+';
const SIMULATION_ID_PATTERN = '[^/]+';

// Route name constants
export const LOGIN_ROUTE_NAME = 'login';
export const LOGIN_TEST_ROUTE_NAME = 'login-test';
export const LOGIN_ROUTES = [LOGIN_ROUTE_NAME, LOGIN_TEST_ROUTE_NAME];
export const HOME_ROUTE_NAME = 'home';
export const WORKSPACE_SETUP_ROUTE_NAME = 'workspace-setup';
export const WORKSPACE_ROUTE_NAME = 'workspace';
export const UNAUTHORIZED_ROUTE_NAME = 'unauthorized';
export const NOT_FOUND_ROUTE_NAME = 'not-found';
export const DEFAULT_ROUTE_NAME = WORKSPACE_SETUP_ROUTE_NAME;

export const ROUTES_WITHOUT_LANGUAGE = [
  NOT_FOUND_ROUTE_NAME,
  UNAUTHORIZED_ROUTE_NAME,
];

export function isBackOfficeRoute(route: RouteLocationNormalized): boolean {
  return route.meta?.isBackOffice === true;
}

export function isSystemRoute(route: RouteLocationNormalized): boolean {
  return route.meta?.isSystem === true;
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    name: 'root',
    children: [
      {
        path: '',
        name: 'root-redirect',
        redirect: {
          name: DEFAULT_ROUTE_NAME,
          params: { language: i18n.global.locale.value.split('-')[0] },
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})`,
        name: 'language',
        redirect: { name: DEFAULT_ROUTE_NAME },
        children: [
          {
            path: 'login',
            name: LOGIN_ROUTE_NAME,
            component: () => import('pages/app/LoginPage.vue'),
            meta: {
              note: 'User authentication - Login page',
              breadcrumb: false,
            },
          },
          {
            path: 'login-test',
            name: LOGIN_TEST_ROUTE_NAME,
            component: () => import('pages/app/LoginTestPage.vue'),
            meta: {
              note: 'Test User authentication - Login page',
              breadcrumb: false,
            },
          },
          {
            path: 'workspace-setup',
            name: WORKSPACE_SETUP_ROUTE_NAME,
            beforeEnter: redirectToWorkspaceIfSelectedGuard,
            component: () => import('pages/app/WorkspaceSetupPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Workspace configuration - Year and lab selection',
              breadcrumb: false,
            },
          },
          {
            path: `:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})`,
            name: WORKSPACE_ROUTE_NAME,
            beforeEnter: validateUnitGuard,
            component: () => import('pages/app/WorkspacePage.vue'),
            children: [
              {
                name: 'home-redirect',
                path: '',
                redirect: { name: HOME_ROUTE_NAME },
              },
              {
                path: 'home',
                name: HOME_ROUTE_NAME,
                component: () => import('pages/app/HomePage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Home - Main overview and navigation',
                  breadcrumb: false,
                },
              },
              {
                path: `:module(${MODULES_PATTERN})`,
                name: 'module',
                component: () => import('pages/app/ModulePage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Module - data entry',
                  breadcrumb: true,
                },
              },
              {
                path: `:module(${MODULES_PATTERN})-results`,
                name: 'module-results',
                component: () => import('pages/app/ModuleResultsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Results - Module-specific results and analysis',
                  breadcrumb: true,
                },
              },
              {
                path: 'results',
                name: 'results',
                component: () => import('pages/app/ResultsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Results - Consolidated overview across all modules',
                  breadcrumb: true,
                },
              },
              {
                path: 'simulations',
                name: 'simulations',
                component: () => import('pages/app/SimulationsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Selection and management page',
                  breadcrumb: true,
                },
              },
              {
                path: 'simulations/add',
                name: 'simulation-add',
                component: () => import('pages/app/AddSimulationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Create new simulation',
                  breadcrumb: true,
                },
              },
              {
                path: `simulations/edit/:simulationId(${SIMULATION_ID_PATTERN})`,
                name: 'simulation-edit',
                component: () => import('pages/app/EditSimulationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Edit existing simulation',
                  breadcrumb: true,
                },
              },
              {
                path: 'documentation',
                name: 'documentation',
                component: () => import('pages/app/DocumentationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Documentation - Main application guide',
                  breadcrumb: true,
                },
              },
            ],
          },
          // Back Office routes
          {
            path: 'back-office',
            name: 'back-office',
            redirect: {
              name: BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName,
            },
          },
          {
            path: 'back-office/user-management',
            name: BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName,
            component: () => import('pages/back-office/UserManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - User roles and permissions (view only)',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/data-management',
            name: BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName,
            component: () => import('pages/back-office/DataManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Data management',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/documentation-editing',
            name: BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName,
            component: () =>
              import('pages/back-office/DocumentationEditingPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Documentation and translation management via GitHub',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/reporting',
            name: BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName,
            component: () => import('pages/back-office/ReportingPage.vue'),
            meta: {
              requiresAuth: true,

              note: 'Back Office - Report generation workflow',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/documentation',
            name: 'back-office-documentation',
            component: () => import('pages/back-office/DocumentationPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Documentation - Back Office documentation',
              isBackOffice: true,
            },
          },
          // System Admin routes
          {
            path: 'system',
            redirect: {
              name: SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName,
            },
          },
          {
            path: 'system/user-management',
            name: SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName,
            component: () => import('pages/system/UserManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - User and role administration',
              breadcrumb: false,
              isSystem: true,
            },
          },
          {
            path: 'system/module-management',
            name: SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName,
            component: () => import('pages/system/ModuleManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - Global module enable/disable',
              breadcrumb: false,
              isSystem: true,
            },
          },
          {
            path: 'system/logs',
            name: SYSTEM_NAV.SYSTEM_LOGS.routeName,
            component: () => import('pages/system/LogsPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - System logs viewer',
              breadcrumb: false,
              isSystem: true,
            },
          },
          {
            path: 'system/documentation',
            name: 'system-documentation',
            component: () => import('pages/system/DocumentationPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Documentation - System Admin documentation',
              breadcrumb: true,
              isSystem: true,
            },
          },
        ],
      },
    ],
  },
  {
    path: '/unauthorized',
    name: UNAUTHORIZED_ROUTE_NAME,
    component: () => import('pages/ErrorUnauthorized.vue'),
  },
  // Catch-all: show 404
  {
    path: '/:catchAll(.*)*',
    name: NOT_FOUND_ROUTE_NAME,
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
