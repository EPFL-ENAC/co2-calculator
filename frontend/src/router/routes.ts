import { RouteLocationNormalized, RouteRecordRaw } from 'vue-router';
import { MODULES_PATTERN } from 'src/constant/modules';
import { i18n } from 'src/boot/i18n';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import redirectToWorkspaceIfSelectedGuard from './guards/redirectToWorkspaceIfSelectedGuard';
import validateUnitGuard from './guards/validateUnitGuard';
import { permissionGuard } from './guards/permissionGuard';
import { moduleEnabledGuard } from './guards/moduleEnabledGuard';
import { PermissionAction } from 'src/stores/auth';

// Route parameter validation patterns
const LANGUAGE_PATTERN = 'en|fr';
const YEAR_PATTERN = '\\d{4}';
const UNIT_PATTERN = '[^/]+';
const SIMULATION_ID_PATTERN = '[^/]+';

// Route name constants live in routeNames.ts so guards + tests can
// depend on them without pulling in the i18n module (which uses
// import.meta.glob and breaks bare-Node test runners).
export {
  LOGIN_ROUTE_NAME,
  LOGIN_TEST_ROUTE_NAME,
  LOGIN_ROUTES,
  HOME_ROUTE_NAME,
  WORKSPACE_SETUP_ROUTE_NAME,
  WORKSPACE_ROUTE_NAME,
  UNAUTHORIZED_ROUTE_NAME,
  NOT_FOUND_ROUTE_NAME,
  DEFAULT_ROUTE_NAME,
  ROUTES_WITHOUT_LANGUAGE,
} from './routeNames';
import {
  LOGIN_ROUTE_NAME,
  LOGIN_TEST_ROUTE_NAME,
  HOME_ROUTE_NAME,
  WORKSPACE_SETUP_ROUTE_NAME,
  WORKSPACE_ROUTE_NAME,
  UNAUTHORIZED_ROUTE_NAME,
  NOT_FOUND_ROUTE_NAME,
  DEFAULT_ROUTE_NAME,
} from './routeNames';

export function isBackOfficeRoute(route: RouteLocationNormalized): boolean {
  return route.meta?.isBackOffice === true;
}

const routes: RouteRecordRaw[] = [
  // Print preview — own layout so no header/sidebar appears
  {
    path: `/:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/results/print`,
    component: () => import('layouts/PrintLayout.vue'),
    children: [
      {
        path: '',
        name: 'results-print',
        component: () => import('pages/app/ResultsPrintPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Results – Print/PDF preview (no chrome)',
          breadcrumb: false,
        },
      },
    ],
  },
  // Simulation explore print preview — own layout, no header/sidebar
  {
    path: `/:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/simulation/explore/print`,
    component: () => import('layouts/PrintLayout.vue'),
    children: [
      {
        path: '',
        name: 'simulation-explore-print',
        component: () => import('pages/app/SimulationExplorePrintPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Simulation Explore – Print/PDF preview (no chrome)',
          breadcrumb: false,
        },
      },
    ],
  },
  // Backoffice reporting print previews — own layout, no header/sidebar
  {
    path: `/:language(${LANGUAGE_PATTERN})/back-office/reporting/print`,
    component: () => import('layouts/PrintLayout.vue'),
    children: [
      {
        path: '',
        name: 'backoffice-reporting-print',
        component: () => import('pages/back-office/ReportingPrintPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Backoffice Reporting – Combined PDF print preview (no chrome)',
          breadcrumb: false,
          isBackOffice: true,
        },
      },
    ],
  },
  {
    path: `/:language(${LANGUAGE_PATTERN})/back-office/reporting/results-print`,
    component: () => import('layouts/PrintLayout.vue'),
    children: [
      {
        path: '',
        name: 'backoffice-results-print',
        component: () =>
          import('pages/back-office/BackofficeResultsPrintPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Backoffice Reporting – Results PDF print preview (no chrome)',
          breadcrumb: false,
          isBackOffice: true,
        },
      },
    ],
  },
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
                beforeEnter: [permissionGuard, moduleEnabledGuard()],
                meta: {
                  requiresAuth: true,
                  moduleEdit: true,
                  note: 'Module - data entry (edit permission required)',
                  breadcrumb: false,
                },
              },
              {
                path: 'results',
                name: 'results',
                component: () => import('pages/app/ResultsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Results - Consolidated overview across all modules',
                  breadcrumb: false,
                },
              },
              {
                path: 'simulation',
                name: 'simulation',
                component: () => import('pages/app/SimulationsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Selection and management page',
                  breadcrumb: true,
                },
              },
              {
                path: `simulation/explore/:explore(${SIMULATION_ID_PATTERN})`,
                name: 'simulation-explore',
                component: () => import('pages/app/SimulationExplorePage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulation - Explore a simulation',
                  breadcrumb: true,
                },
              },
              {
                path: `simulation/plan/:plan(${SIMULATION_ID_PATTERN})`,
                name: 'simulation-plan',
                component: () => import('pages/app/SimulationPlanPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulation - Plan a simulation',
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
                  breadcrumb: false,
                },
              },
            ],
          },
          // Back Office routes.
          // ``meta.requiredPermission`` (+ ``requiredAction``) is the single
          // source of truth for each page's gate: ``permissionGuard``
          // enforces it and ``Co2Sidebar`` reads the same meta to decide
          // reachability, so router and nav can never drift.
          {
            path: 'back-office',
            name: 'back-office',
            redirect: {
              name: BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName,
            },
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.reporting',
              requiredAction: PermissionAction.VIEW,
            },
          },
          {
            path: 'back-office/user-management',
            name: BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName,
            component: () => import('pages/back-office/UserManagementPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.users',
              requiredAction: PermissionAction.EDIT,
              requiresAuth: true,
              note: 'Back Office - User roles and permissions (admin only)',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/data-management',
            name: BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName,
            component: () => import('pages/back-office/DataManagementPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.configuration',
              requiredAction: PermissionAction.EDIT,
              requiresAuth: true,
              note: 'Back Office - Data management (admin only)',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/pipeline-operations',
            name: BACKOFFICE_NAV.BACKOFFICE_PIPELINE_OPERATIONS.routeName,
            component: () =>
              import('pages/back-office/PipelineOperationsConsolePage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.pipeline_operations',
              requiredAction: PermissionAction.VIEW,
              requiresAuth: true,
              note: 'Back Office - Pipeline operations console (admin only)',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/documentation-editing',
            name: BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName,
            component: () =>
              import('pages/back-office/DocumentationEditingPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.documentation',
              requiredAction: PermissionAction.VIEW,
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
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.reporting',
              requiredAction: PermissionAction.VIEW,
              requiresAuth: true,
              note: 'Back Office - Report generation workflow',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/ui-texts-editing',
            name: BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.routeName,
            component: () => import('pages/back-office/UITextsEditingPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.ui_texts',
              requiredAction: PermissionAction.VIEW,
              requiresAuth: true,
              note: 'Back Office - UI translation text management via GitHub',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/logs',
            name: BACKOFFICE_NAV.BACKOFFICE_LOGS.routeName,
            component: () => import('pages/system/LogsPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.logs',
              requiredAction: PermissionAction.VIEW,
              requiresAuth: true,
              note: 'Back Office - Audit logs (superadmin only)',
              breadcrumb: false,
              isBackOffice: true,
            },
          },
          {
            path: 'back-office/documentation',
            name: 'back-office-documentation',
            component: () => import('pages/back-office/DocumentationPage.vue'),
            beforeEnter: permissionGuard,
            meta: {
              requiredPermission: 'backoffice.documentation',
              requiredAction: PermissionAction.VIEW,
              requiresAuth: true,
              note: 'Documentation - Back Office documentation',
              isBackOffice: true,
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
