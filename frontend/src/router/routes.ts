import { RouteRecordRaw } from 'vue-router';
import { MODULES_PATTERN } from 'src/constant/modules';
import { i18n } from 'src/boot/i18n';
import redirectToWorkspaceIfSelectedGuard from './guards/redirectToWorkspaceIfSelectedGuard';

// Route parameter validation patterns
// Note: Vue Router's :param(pattern) syntax automatically wraps the pattern in parentheses
const LANGUAGE_PATTERN = 'en|fr';
const YEAR_PATTERN = '\\d{4}'; // Exactly 4 digits
const UNIT_PATTERN = '[^/]+'; // Any non-slash characters (unit ID)
const SIMULATION_ID_PATTERN = '[^/]+'; // Any non-slash characters (simulation ID)

// Centralize login paths
export const LOGIN_ROUTE_NAME = 'login';
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
            path: 'workspace-setup',
            name: WORKSPACE_SETUP_ROUTE_NAME,
            component: () => import('pages/app/WorkspaceSetupPage.vue'),
            beforeEnter: redirectToWorkspaceIfSelectedGuard,
            meta: {
              requiresAuth: true,
              note: 'Workspace configuration - Year and lab selection',
              breadcrumb: false,
            },
          },
          {
            path: `:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})`,
            name: WORKSPACE_ROUTE_NAME,
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
            path: 'back-office/user-management',
            name: 'backoffice-user-management',
            component: () => import('pages/back-office/UserManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - User roles and permissions (view only)',
              breadcrumb: false,
            },
          },
          {
            path: 'back-office/module-management',
            name: 'backoffice-module-management',
            component: () =>
              import('pages/back-office/ModuleManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Module completion tracking across labs',
              breadcrumb: false,
            },
          },
          {
            path: 'back-office/documentation-editing',
            name: 'backoffice-documentation-editing',
            component: () =>
              import('pages/back-office/DocumentationEditingPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Documentation and translation management via GitHub',
              breadcrumb: true,
            },
          },
          {
            path: 'back-office/reporting',
            name: 'backoffice-reporting',
            component: () => import('pages/back-office/ReportingPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Report generation workflow',
              breadcrumb: false,
            },
          },
          {
            path: 'back-office/documentation',
            name: 'backoffice-documentation',
            component: () => import('pages/back-office/DocumentationPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Documentation - Back Office documentation',
            },
          },
          // System Admin routes
          {
            path: 'system/user-management',
            name: 'system-user-management',
            component: () => import('pages/system/UserManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - User and role administration',
              breadcrumb: false,
            },
          },
          {
            path: 'system/module-management',
            name: 'system-module-management',
            component: () => import('pages/system/ModuleManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - Global module enable/disable',
              breadcrumb: false,
            },
          },
          {
            path: 'system/logs',
            name: 'system-logs',
            component: () => import('pages/system/LogsPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - System logs viewer',
              breadcrumb: false,
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
