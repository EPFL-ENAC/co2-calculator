import type { Meta, StoryObj } from '@storybook/vue3';
import type { Decorator } from '@storybook/vue3';
import { useRouter } from 'vue-router';
import { nextTick, ref } from 'vue';
import { useAuthStore } from 'src/stores/auth';
import { ROLES } from 'src/constant/roles';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/navigation';
import Co2Sidebar from './Co2Sidebar.vue';

/**
 * Co2Sidebar is a navigation sidebar component that displays:
 * - Navigation items for backoffice or system sections
 * - Icons and labels for each navigation item
 * - Active/selected state highlighting
 * - Role-based access control (disables limited access items for BackOfficeStandard users)
 *
 * ## Backoffice Sidebar Area
 * This component is used in the backoffice area of the application.
 * It provides navigation between different backoffice sections such as:
 * - Reporting
 * - User Management (limited access)
 * - Data Management (limited access)
 * - Documentation Editing
 *
 * ## System Sidebar Area
 * This component can also be used for system-level navigation:
 * - User Management
 * - Module Management
 * - System Logs
 *
 * ## Features
 * - Role-based item disabling (BackOfficeStandard users cannot access limited items)
 * - Active route highlighting
 * - Click navigation to different routes
 * - Responsive sidebar layout
 */
const meta = {
  title: 'Layout/Co2Sidebar',
  component: Co2Sidebar,
  tags: ['autodocs'],
  decorators: [
    (story) => ({
      components: { story },
      template: `
        <div style="width: 250px; padding: 16px; background: #f5f5f5;">
          <story />
        </div>
      `,
    }),
  ],
} satisfies Meta<typeof Co2Sidebar>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Decorator that sets up the router and auth store with specific configurations.
 */
const withRouterAndAuth = (config: {
  route: {
    name: string;
    params?: Record<string, string>;
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
}): Decorator => {
  return (story) => {
    return {
      components: { story },
      setup() {
        const router = useRouter();
        const authStore = useAuthStore();
        const isReady = ref(false);

        // Set up auth store
        if (config.user) {
          authStore.user = config.user as typeof authStore.user;
        } else {
          authStore.user = null;
        }

        // Ensure language param is always present
        const routeParams = {
          language: config.route.params?.language || 'en',
          ...config.route.params,
        };

        // Set up route
        router
          .replace({
            name: config.route.name,
            params: routeParams,
          })
          .then(() => {
            nextTick().then(() => {
              isReady.value = true;
            });
          })
          .catch(() => {
            isReady.value = true;
          });

        // Also set route params directly on current route as fallback
        if (
          router.currentRoute.value.name === config.route.name ||
          !router.currentRoute.value.name
        ) {
          Object.assign(router.currentRoute.value.params, routeParams);
        }

        return { isReady };
      },
      template: '<story />',
    };
  };
};

/**
 * Backoffice sidebar with BackOfficeAdmin user.
 * All navigation items are enabled and clickable.
 * This is the backoffice sidebar area.
 */
export const Backoffice: Story = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    withRouterAndAuth({
      route: {
        name: 'backoffice-reporting',
        params: { language: 'en' },
      },
      user: {
        id: '1',
        email: 'admin@example.com',
        display_name: 'Admin User',
        roles_raw: [
          {
            role: ROLES.BackOfficeAdmin,
            on: 'global',
          },
        ],
      },
    }),
  ],
  args: {
    items: BACKOFFICE_NAV,
  },
  render: (args) => ({
    components: { Co2Sidebar },
    setup() {
      return { args };
    },
    template: '<Co2Sidebar :items="args.items" />',
  }),
};

/**
 * Backoffice sidebar with BackOfficeStandard user (restricted access).
 * Limited access items (User Management and Data Management) are disabled.
 * This demonstrates the backoffice restricted sidebar area.
 */
export const BackofficeRestricted: Story = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    withRouterAndAuth({
      route: {
        name: 'backoffice-reporting',
        params: { language: 'en' },
      },
      user: {
        id: '2',
        email: 'standard@example.com',
        display_name: 'Standard User',
        roles_raw: [
          {
            role: ROLES.BackOfficeStandard,
            on: 'global',
          },
        ],
      },
    }),
  ],
  args: {
    items: BACKOFFICE_NAV,
  },
  render: (args) => ({
    components: { Co2Sidebar },
    setup() {
      return { args };
    },
    template: '<Co2Sidebar :items="args.items" />',
  }),
};

/**
 * System sidebar with System role user.
 * All system navigation items are enabled.
 * This is the system sidebar area.
 */
export const System: Story = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    withRouterAndAuth({
      route: {
        name: 'system-user-management',
        params: { language: 'en' },
      },
      user: {
        id: '3',
        email: 'system@example.com',
        display_name: 'System User',
        roles_raw: [
          {
            role: ROLES.System,
            on: 'global',
          },
        ],
      },
    }),
  ],
  args: {
    items: SYSTEM_NAV,
  },
  render: (args) => ({
    components: { Co2Sidebar },
    setup() {
      return { args };
    },
    template: '<Co2Sidebar :items="args.items" />',
  }),
};
