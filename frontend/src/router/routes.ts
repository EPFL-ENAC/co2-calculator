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
        path: `:language(${LANGUAGE_PATTERN})/login`,
        component: () => import('pages/app/LoginPage.vue'),
        meta: {
          note: 'User authentication - Login page',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/workspace-setup`,
        component: () => import('pages/app/WorkspaceSetupPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Workspace configuration - Year and lab selection',
        },
      },
      // Workspace routes with unit and year
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/home`,
        component: () => import('pages/app/HomePage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Dashboard - Main overview and navigation',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/:module(${MODULE_PATTERN})/`,
        component: () => import('pages/app/ModulePage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Module - data entry',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/:module(${MODULE_PATTERN})/results/`,
        component: () => import('pages/app/ModuleResultsPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Results - Module-specific results and analysis',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/results`,
        component: () => import('pages/app/ResultsPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Results - Consolidated overview across all modules',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/simulations`,
        component: () => import('pages/app/SimulationsPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Simulations - Selection and management page',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/simulations/add`,
        component: () => import('pages/app/AddSimulationPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Simulations - Create new simulation',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/simulations/edit/:simulationId(${SIMULATION_ID_PATTERN})`,
        component: () => import('pages/app/EditSimulationPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Simulations - Edit existing simulation',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/:unit(${UNIT_PATTERN})/:year(${YEAR_PATTERN})/documentation`,
        component: () => import('pages/app/DocumentationPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Documentation - Main application guide',
        },
      },
      // Back Office routes
      {
        path: `:language(${LANGUAGE_PATTERN})/back-office/user-management`,
        component: () => import('pages/back-office/UserManagementPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Back Office - User roles and permissions (view only)',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/back-office/module-management`,
        component: () => import('pages/back-office/ModuleManagementPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Back Office - Module completion tracking across labs',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/back-office/documentation-editing`,
        component: () =>
          import('pages/back-office/DocumentationEditingPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Back Office - Documentation and translation management via GitHub',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/back-office/reporting`,
        component: () => import('pages/back-office/ReportingPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Back Office - Report generation workflow',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/back-office/documentation`,
        component: () => import('pages/back-office/DocumentationPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Documentation - Back Office documentation',
        },
      },
      // System Admin routes
      {
        path: `:language(${LANGUAGE_PATTERN})/system/user-management`,
        component: () => import('pages/system/UserManagementPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'System Admin - User and role administration',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/system/module-management`,
        component: () => import('pages/system/ModuleManagementPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'System Admin - Global module enable/disable',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/system/logs`,
        component: () => import('pages/system/LogsPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'System Admin - System logs viewer',
        },
      },
      {
        path: `:language(${LANGUAGE_PATTERN})/system/documentation`,
        component: () => import('pages/system/DocumentationPage.vue'),
        meta: {
          requiresAuth: true,
          note: 'Documentation - System Admin documentation',
        },
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
