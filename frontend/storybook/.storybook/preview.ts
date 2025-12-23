import type { Preview } from '@storybook/vue3';
import { setup } from '@storybook/vue3';
import { createPinia } from 'pinia';
import { createI18n } from 'vue-i18n';
import { createMemoryHistory, createRouter } from 'vue-router';
import { Quasar, Dialog, Loading, Notify } from 'quasar';
import messages from '../../src/i18n';
import { icons } from '../../src/plugin/module-icon';

// Import Quasar styles
import '@quasar/extras/material-icons/material-icons.css';
import '@quasar/extras/material-icons-outlined/material-icons-outlined.css';

// Import app styles with CSS Cascade Layers
import '../../src/css/app.scss';

// Setup Vue app with Quasar, Pinia, i18n, and Router
setup((app) => {
  // Create fresh Pinia instance
  const pinia = createPinia();

  app.use(pinia);

  // Create i18n instance
  const i18n = createI18n({
    locale: 'en-US',
    legacy: false,
    messages,
  });
  app.use(i18n);

  // Create memory router with basic routes including language param
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>Home</div>' } },
      {
        path: '/:language',
        name: 'language-home',
        component: { template: '<div>Home</div>' },
      },
      { path: '/en', name: 'en', component: { template: '<div>EN</div>' } },
      { path: '/fr', name: 'fr', component: { template: '<div>FR</div>' } },
    ],
  });
  app.use(router);

  // Install Quasar
  app.use(Quasar, {
    plugins: {
      Dialog,
      Loading,
      Notify,
    },
  });

  // Register custom SVG icons
  app.config.globalProperties.$moduleIcons = icons;
});

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#ffffff' },
        { name: 'dark', value: '#1d1d1d' },
      ],
    },
    viewport: {
      viewports: {
        mobile: {
          name: 'Mobile',
          styles: { width: '375px', height: '667px' },
        },
        tablet: {
          name: 'Tablet',
          styles: { width: '768px', height: '1024px' },
        },
        desktop: {
          name: 'Desktop',
          styles: { width: '1440px', height: '900px' },
        },
      },
    },
  },
  globalTypes: {
    locale: {
      name: 'Locale',
      description: 'Internationalization locale',
      defaultValue: 'en-US',
      toolbar: {
        icon: 'globe',
        items: [
          { value: 'en-US', title: 'English' },
          { value: 'fr-CH', title: 'Français' },
        ],
        showName: true,
      },
    },
  },
  decorators: [
    (story) => {
      return {
        components: { story },
        setup() {
          return {};
        },
        template: '<story />',
      };
    },
  ],
};

export default preview;
