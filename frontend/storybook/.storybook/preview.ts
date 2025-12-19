import type { Preview } from '@storybook/vue3';
import { setup } from '@storybook/vue3';
import { createPinia } from 'pinia';
import { createI18n } from 'vue-i18n';
import { createRouter, createMemoryHistory } from 'vue-router';
import { Quasar, Dialog, Loading, Notify } from 'quasar';
import { icons } from '../../src/plugin/module-icon';
import { defineComponent, h, getCurrentInstance } from 'vue';

// Import CSS Cascade Layers
import '../../src/css/app.scss';

// Import Quasar Material Icons
import '@quasar/extras/material-icons/material-icons.css';

// Import i18n messages
import messages from '../../src/i18n';

// Create i18n instance
const i18n = createI18n({
  locale: 'en-US',
  legacy: false,
  messages,
  fallbackLocale: 'en-US',
});

// Create router with memory history (shared instance)
// Use simplified routes for Storybook to avoid complex guards and dependencies
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: { template: '<div>Home</div>' },
    },
    {
      path: '/:language(en|fr)',
      name: 'language',
      children: [
        {
          path: 'login',
          name: 'login',
          component: { template: '<div>Login</div>' },
        },
      ],
    },
  ],
});

// Setup global app configuration (runs once, Pinia is handled per-story)
setup((app) => {
  // Register i18n (shared instance, locale updated per-story)
  app.use(i18n);

  // Register Vue Router (shared instance)
  app.use(router);

  // Install Quasar with plugins
  app.use(Quasar, {
    plugins: {
      Dialog,
      Loading,
      Notify,
    },
  });

  // Register custom SVG icons (matching app pattern)
  app.config.globalProperties.$moduleIcons = icons;
});

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'light',
      values: [
        {
          name: 'light',
          value: '#ffffff',
        },
        {
          name: 'dark',
          value: '#1d1d1d',
        },
        {
          name: 'gray',
          value: '#f5f5f5',
        },
      ],
    },
    viewport: {
      viewports: {
        mobile: {
          name: 'Mobile',
          styles: {
            width: '375px',
            height: '667px',
          },
        },
        tablet: {
          name: 'Tablet',
          styles: {
            width: '768px',
            height: '1024px',
          },
        },
        desktop: {
          name: 'Desktop',
          styles: {
            width: '1920px',
            height: '1080px',
          },
        },
      },
    },
  },
  globalTypes: {
    locale: {
      description: 'Internationalization locale',
      defaultValue: 'en-US',
      toolbar: {
        icon: 'globe',
        items: [
          { value: 'en-US', title: 'English' },
          { value: 'fr-CH', title: 'Français' },
        ],
        showName: true,
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (storyFn, context) => {
      // Create fresh Pinia instance for each story
      const storyPinia = createPinia();

      // Inject router into Pinia (matching app pattern)
      storyPinia.use(() => ({ router }));

      // Update i18n locale based on toolbar selection
      const locale = (context.globals.locale as string) || 'en-US';
      i18n.global.locale.value = locale;

      // Create a wrapper component that registers Pinia and renders the story
      const WrapperComponent = defineComponent({
        setup() {
          // Register Pinia on the current app instance
          const instance = getCurrentInstance();
          if (instance?.appContext?.app) {
            instance.appContext.app.use(storyPinia);
          }
          // Render the story component
          const story = storyFn();
          return () => story;
        },
      });

      return () => h(WrapperComponent);
    },
  ],
};

export default preview;
