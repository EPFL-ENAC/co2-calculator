import type { Meta, StoryObj } from '@storybook/vue3';
import type { Decorator } from '@storybook/vue3';
import { useRouter } from 'vue-router';
import CO2LanguageSelector from './Co2LanguageSelector.vue';

/**
 * CO2LanguageSelector is a component that displays language selection links.
 * It uses router-link to navigate between different language versions of the current route.
 *
 * ## Features
 * - Displays all available languages as clickable links
 * - Maintains current route name and query parameters
 * - Updates only the language parameter in the route
 * - Shows active language with underline styling
 * - Separates languages with " / " divider
 */
const meta = {
  title: 'Atoms/CO2LanguageSelector',
  component: CO2LanguageSelector,
  tags: ['autodocs'],
} satisfies Meta<typeof CO2LanguageSelector>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Decorator that sets up the router with an initial route containing a language parameter.
 * This makes the language selector interactive by providing a proper route context.
 */
const withRouterSetup = (initialRoute: {
  name: string;
  params?: Record<string, string>;
  query?: Record<string, string>;
}): Decorator => {
  return (story) => {
    return {
      components: { story },
      setup() {
        const router = useRouter();
        // Set initial route
        router.push({
          name: initialRoute.name,
          params: initialRoute.params || {},
          query: initialRoute.query || {},
        });
        return {};
      },
      template: '<story />',
    };
  };
};

/**
 * Default CO2LanguageSelector showing all available languages.
 * Click on a language to see the route change. The active language is underlined.
 */
export const Default: Story = {
  decorators: [
    withRouterSetup({
      name: 'language-home',
      params: { language: 'en' },
    }),
  ],
  render: () => ({
    components: { CO2LanguageSelector },
    setup() {
      const router = useRouter();
      return { router };
    },
    template: `
      <div>
        <p class="text-body2 q-mb-md">
          Current route: <strong>{{ $route.path }}</strong><br>
          Current language: <strong>{{ $route.params.language || 'none' }}</strong>
        </p>
        <CO2LanguageSelector />
        <p class="text-caption q-mt-md text-grey-7">
          Click on a language to navigate. The active language is underlined.
        </p>
      </div>
    `,
  }),
};

/**
 * CO2LanguageSelector on a module page.
 * Demonstrates how the component maintains route context when switching languages.
 */
export const OnModulePage: Story = {
  decorators: [
    withRouterSetup({
      name: 'module',
      params: {
        language: 'en',
        unit: 'unit-1',
        year: '2024',
        module: 'headcount',
      },
    }),
  ],
  render: () => ({
    components: { CO2LanguageSelector },
    setup() {
      const router = useRouter();
      return { router };
    },
    template: `
      <div>
        <p class="text-body2 q-mb-md">
          Current route: <strong>{{ $route.path }}</strong><br>
          Route name: <strong>{{ $route.name }}</strong><br>
          Language: <strong>{{ $route.params.language }}</strong> | 
          Unit: <strong>{{ $route.params.unit }}</strong> | 
          Module: <strong>{{ $route.params.module }}</strong>
        </p>
        <CO2LanguageSelector />
        <p class="text-caption q-mt-md text-grey-7">
          Clicking a language will change the language parameter while keeping other route params.
        </p>
      </div>
    `,
  }),
};
