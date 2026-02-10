import type { Meta, StoryObj } from '@storybook/vue3';
import type { Decorator } from '@storybook/vue3';
import { useRouter } from 'vue-router';
import { nextTick, ref } from 'vue';
import { useTimelineStore } from 'src/stores/modules';
import { MODULES } from 'src/constant/modules';
import { MODULE_STATES } from 'src/constant/moduleStates';
import Co2Timeline from 'src/components/organisms/layout/Co2Timeline.vue';
import {
  allDefault,
  mixedStates,
} from '../../../storybook/.storybook/fixtures/timeline';

/**
 * Co2Timeline displays a horizontal timeline of all module items with:
 * - Module icons with state indicators
 * - Separators between items
 * - Arrow icon
 * - Results button at the end
 *
 * ## Features
 * - Shows all timeline items from constants
 * - State colors based on timeline store
 * - Selected state based on current route
 * - Navigation to modules and results page
 */
const meta = {
  title: 'Organisms/Co2Timeline',
  component: Co2Timeline,
  tags: ['autodocs'],
} satisfies Meta<typeof Co2Timeline>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Decorator that sets up the router and timeline store with specific configurations.
 */
const withRouterAndTimelineStore = (config: {
  route: {
    name: string;
    params?: Record<string, string>;
    module?: string; // Selected module name
  };
  timelineStates?: Partial<
    Record<
      (typeof MODULES)[keyof typeof MODULES],
      (typeof MODULE_STATES)[keyof typeof MODULE_STATES]
    >
  >;
}): Decorator => {
  return (story) => {
    return {
      components: { story },
      setup() {
        const router = useRouter();
        const timelineStore = useTimelineStore();
        const isReady = ref(false);

        // Set up timeline states
        if (config.timelineStates) {
          Object.entries(config.timelineStates).forEach(([module, state]) => {
            timelineStore.itemStates[
              module as keyof typeof timelineStore.itemStates
            ] = state;
          });
        }

        // Ensure language param is always present
        const routeParams = {
          language: config.route.params?.language || 'en',
          unit: config.route.params?.unit || 'My%20Lab',
          year: config.route.params?.year || '2024',
          ...(config.route.module && { module: config.route.module }),
          ...config.route.params,
        };

        // Set up route immediately
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
 * Default timeline with all modules in default state, no module selected.
 */
export const Default: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndTimelineStore({
      route: {
        name: 'results',
        params: {
          language: 'en',
          unit: 'My%20Lab',
          year: '2024',
        },
      },
      timelineStates: allDefault,
    }),
  ],
};

/**
 * Timeline with mixed states showing progression through modules.
 */
export const WithMixedStates: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndTimelineStore({
      route: {
        name: 'results',
        params: {
          language: 'en',
          unit: 'My%20Lab',
          year: '2024',
        },
      },
      timelineStates: mixedStates,
    }),
  ],
};

/**
 * Timeline with a module selected (Infrastructure).
 */
export const WithSelectedModule: Story = {
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
  decorators: [
    withRouterAndTimelineStore({
      route: {
        name: 'module',
        params: {
          language: 'en',
          unit: 'My%20Lab',
          year: '2024',
        },
        module: MODULES.Infrastructure,
      },
      timelineStates: mixedStates,
    }),
  ],
};
