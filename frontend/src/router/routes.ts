import { RouteRecordRaw } from 'vue-router';

// Route parameter validation patterns
// Note: Vue Router's :param(pattern) syntax automatically wraps the pattern in parentheses
const LANGUAGE_PATTERN = 'en|fr';
const YEAR_PATTERN = '\\d{4}'; // Exactly 4 digits
const MODULE_PATTERN =
  'my-lab|professional-travel|infrastructure|equipement-electric-consumption|purchases|internal-services|external-cloud';
const UNIT_PATTERN = '[^/]+'; // Any non-slash characters (unit ID)
const SIMULATION_ID_PATTERN = '[^/]+'; // Any non-slash characters (simulation ID)

// Helper function to redirect paths without language prefix to /en/ version
const redirectToDefaultLanguage = (to: { path: string }) => {
  // Don't redirect API routes
  if (to.path.startsWith('/api/')) {
    return false;
  }
  // Don't redirect if already has language prefix
  if (to.path.startsWith('/en/') || to.path.startsWith('/fr/')) {
    return false;
  }
  // Special case: root path redirects to login
  if (to.path === '/') {
    return '/en/login';
  }
  // Redirect to /en/ + path
  return `/en${to.path}`;
};

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/en/login',
      },
      {
        path: `:language(${LANGUAGE_PATTERN})`,
        name: 'language',
        children: [
          {
            path: 'login',
            name: 'login',
            component: () => import('pages/app/LoginPage.vue'),
            meta: {
              note: 'User authentication - Login page',
            },
          },
          {
            path: 'workspace-setup',
            name: 'workspace-setup',
            component: () => import('pages/app/WorkspaceSetupPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Workspace configuration - Year and lab selection',
            },
          },
          {
            path: `:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})`,
            name: 'workspace',
            children: [
              {
                path: '',
                redirect: 'home',
              },
              {
                path: 'home',
                name: 'home',
                component: () => import('pages/app/HomePage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Home - Main overview and navigation',
                },
              },
              {
                path: `:module(${MODULE_PATTERN})`,
                name: 'module',
                component: () => import('pages/app/ModulePage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Module - data entry',
                },
              },
              {
                path: `:module(${MODULE_PATTERN})-results`,
                name: 'module-results',
                component: () => import('pages/app/ModuleResultsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Results - Module-specific results and analysis',
                },
              },
              {
                path: 'results',
                name: 'results',
                component: () => import('pages/app/ResultsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Results - Consolidated overview across all modules',
                },
              },
              {
                path: 'simulations',
                name: 'simulations',
                component: () => import('pages/app/SimulationsPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Selection and management page',
                },
              },
              {
                path: 'simulations/add',
                name: 'simulation-add',
                component: () => import('pages/app/AddSimulationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Create new simulation',
                },
              },
              {
                path: `simulations/edit/:simulationId(${SIMULATION_ID_PATTERN})`,
                name: 'simulation-edit',
                component: () => import('pages/app/EditSimulationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Simulations - Edit existing simulation',
                },
              },
              {
                path: 'documentation',
                name: 'documentation',
                component: () => import('pages/app/DocumentationPage.vue'),
                meta: {
                  requiresAuth: true,
                  note: 'Documentation - Main application guide',
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
            },
          },
          {
            path: 'back-office/reporting',
            name: 'backoffice-reporting',
            component: () => import('pages/back-office/ReportingPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Back Office - Report generation workflow',
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
            },
          },
          {
            path: 'system/module-management',
            name: 'system-module-management',
            component: () => import('pages/system/ModuleManagementPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - Global module enable/disable',
            },
          },
          {
            path: 'system/logs',
            name: 'system-logs',
            component: () => import('pages/system/LogsPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'System Admin - System logs viewer',
            },
          },
          {
            path: 'system/documentation',
            name: 'system-documentation',
            component: () => import('pages/system/DocumentationPage.vue'),
            meta: {
              requiresAuth: true,
              note: 'Documentation - System Admin documentation',
            },
          },
        ],
      },
    ],
  },

  // Catch-all: redirect routes without language parameter, otherwise show 404
  {
    path: '/:catchAll(.*)*',
    beforeEnter: (to, _from, next) => {
      const redirect = redirectToDefaultLanguage(to);
      if (redirect) {
        next(redirect);
      } else {
        // Path already has language prefix but doesn't match any route - show 404
        next();
      }
    },
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
