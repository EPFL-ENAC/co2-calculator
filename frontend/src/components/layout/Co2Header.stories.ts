import type { Meta, StoryObj } from '@storybook/vue3';
import type { Decorator } from '@storybook/vue3';
import { useRouter } from 'vue-router';
import { nextTick, ref } from 'vue';
import { useAuthStore } from 'src/stores/auth';
import { useTimelineStore } from 'src/stores/modules';
import { ROLES } from 'src/constant/roles';
import Co2Header from './Co2Header.vue';
import { MODULE_STATES, ModuleState } from 'src/constant/moduleStates';

/**
 * Co2Header is the main application header component that displays:
 * - Logo and application title
 * - Language selector
 * - Documentation link
 * - Back office access button (for authorized users)
 * - Workspace information and change button
 * - User dropdown menu with logout
 * - Breadcrumbs (when applicable)
 * - Module validation toggle button (on module pages)
 *
 * ## Features
 * - Responsive header layout
 * - Conditional rendering based on user roles and current route
 * - Workspace display (unit and year)
 * - Breadcrumb navigation
 * - Module state management
 */
const meta = {
  title: 'Layout/Co2Header',
  component: Co2Header,
  tags: ['autodocs'],
  decorators: [
    (story) => ({
      components: { story },
      template: `
        <div style="width: 100%;  overflow: auto;">
          <story />
        </div>
      `,
    }),
  ],
} satisfies Meta<typeof Co2Header>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Decorator that sets up the router and stores with specific configurations.
 */
const withRouterAndStores = (config: {
  route: {
    name: string;
    params?: Record<string, string>;
    query?: Record<string, string>;
    meta?: Record<string, unknown>;
  };
  user?: {
    id: string;
    email: string;
    display_name?: string;
    roles_raw?: Array<{
      role: string;
      on: { unit?: string; affiliation?: string } | 'global';
    }>;
  } | null;
  moduleState?: ModuleState;
}): Decorator => {
  return (story) => {
    return {
      components: { story },
      setup() {
        const router = useRouter();
        const authStore = useAuthStore();
        const timelineStore = useTimelineStore();
        const isReady = ref(false);

        // Set up auth store first
        if (config.user) {
          authStore.user = config.user as typeof authStore.user;
        } else {
          authStore.user = null;
        }

        // Set up timeline store module state
        if (config.moduleState && config.route.params?.module) {
          timelineStore.itemStates[
            config.route.params.module as keyof typeof timelineStore.itemStates
          ] = config.moduleState;
        }

        // Ensure language param is always present
        const routeParams = {
          language: config.route.params?.language || 'en',
          ...config.route.params,
        };

        // Set up route immediately - use replace to avoid adding to history
        router
          .replace({
            name: config.route.name,
            params: routeParams,
            query: config.route.query || {},
          })
          .then(() => {
            // Update route meta after navigation
            nextTick().then(() => {
              if (config.route.meta) {
                Object.assign(
                  router.currentRoute.value.meta,
                  config.route.meta || {},
                );
              }
              isReady.value = true;
            });
          })
          .catch(() => {
            // If replace fails, still mark as ready
            isReady.value = true;
          });

        // Also set route params directly on current route as fallback
        if (
          router.currentRoute.value.name === config.route.name ||
          !router.currentRoute.value.name
        ) {
          Object.assign(router.currentRoute.value.params, routeParams);
          if (config.route.meta) {
            Object.assign(router.currentRoute.value.meta, config.route.meta);
          }
        }

        return { isReady };
      },
      template: '<story />',
    };
  };
};

/**
 * Default header on the workspace setup page.
 */
export const Default: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndStores({
      route: {
        name: 'workspace-setup',
        params: { language: 'en' },
      },
      user: {
        id: '1',
        email: 'user@example.com',
        display_name: 'John Doe',
        roles_raw: [],
      },
    }),
  ],
  render: () => ({
    components: { Co2Header },
    template: `
      <q-layout style="min-height: 100px;">
        <Co2Header />
      </q-layout>
    `,
  }),
};

/**
 * Header with workspace information (unit and year).
 */
export const WithWorkspace: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndStores({
      route: {
        name: 'results',
        params: {
          language: 'en',
          unit: 'My%20Lab',
          year: '2024',
        },
      },
      user: {
        id: '1',
        email: 'user@example.com',
        display_name: 'Jane Smith',
        roles_raw: [],
      },
    }),
  ],
  render: () => ({
    components: { Co2Header },
    template: `
      <q-layout style="min-height: 100px;">
        <Co2Header />
    
      </q-layout>
    `,
  }),
};

/**
 * Header on a module page with breadcrumbs and validation toggle.
 */
export const OnModuleAndResultsPage: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndStores({
      route: {
        name: 'module',
        params: {
          language: 'en',
          unit: 'Research%20Unit',
          year: '2024',
          module: 'headcount',
        },
        meta: {
          breadcrumb: true,
        },
      },
      user: {
        id: '1',
        email: 'user@example.com',
        display_name: 'Alice Johnson',
        roles_raw: [],
      },
      moduleState: MODULE_STATES.InProgress,
    }),
  ],
  render: () => ({
    components: { Co2Header },
    template: `
      <q-layout style="min-height: 200px;">
        <Co2Header />
       
      </q-layout>
    `,
  }),
};

/**
 * Header with back office access button (for users with back office roles).
 */
export const WithBackOfficeAccess: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndStores({
      route: {
        name: 'results',
        params: {
          language: 'en',
          unit: 'My%20Lab',
          year: '2024',
        },
      },
      user: {
        id: '1',
        email: 'admin@example.com',
        display_name: 'Admin User',
        roles_raw: [
          {
            role: ROLES.BackOfficeMetier,
            on: 'global',
          },
        ],
      },
    }),
  ],
  render: () => ({
    components: { Co2Header },
    template: `
        <q-layout style="min-height: 100px;">
        <Co2Header />
      </q-layout>
    `,
  }),
};
