import type { Preview } from '@storybook/vue3';
import { setup } from '@storybook/vue3';
import { createPinia, setActivePinia } from 'pinia';
import { createI18n } from 'vue-i18n';
import { createMemoryHistory, createRouter } from 'vue-router';
import { Quasar, Dialog, Loading, Notify } from 'quasar';
import {
  QHeader,
  QToolbar,
  QToolbarTitle,
  QImg,
  QSpace,
  QBtn,
  QBtnDropdown,
  QList,
  QItem,
  QItemSection,
  QItemLabel,
  QIcon,
  QSeparator,
  QBreadcrumbs,
  QBreadcrumbsEl,
  QLayout,
  QPageContainer,
  QPage,
  QCard,
  QCardSection,
  QCheckbox,
  QInput,
} from 'quasar';
import messages from '../../src/i18n';
import { icons } from '../../src/plugin/module-icon';
import { useColorblindStore } from '../../src/stores/colorblind';

// Import Quasar styles
import '@quasar/extras/material-icons/material-icons.css';
import '@quasar/extras/material-icons-outlined/material-icons-outlined.css';

// Import app styles with CSS Cascade Layers
import '../../src/css/app.scss';

// Setup Vue app with Quasar, Pinia, i18n, and Router
setup((app) => {
  // Create fresh Pinia instance
  const pinia = createPinia();
  setActivePinia(pinia);

  app.use(pinia);

  // Initialize stores that are used at module level
  // This ensures stores are available when modules are imported
  // The colorblind store is used in src/constant/charts.ts at module level
  useColorblindStore(pinia);

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
      {
        path: '/:language/workspace-setup',
        name: 'workspace-setup',
        component: { template: '<div>Workspace Setup</div>' },
      },
      {
        path: '/:language/back-office',
        name: 'back-office',
        component: { template: '<div>Back Office</div>' },
        meta: { isBackOffice: true },
      },
      {
        path: '/:language/back-office/reporting',
        name: 'backoffice-reporting',
        component: { template: '<div>Backoffice Reporting</div>' },
        meta: { isBackOffice: true },
      },
      {
        path: '/:language/back-office/user-management',
        name: 'backoffice-user-management',
        component: { template: '<div>Backoffice User Management</div>' },
        meta: { isBackOffice: true },
      },
      {
        path: '/:language/back-office/data-management',
        name: 'backoffice-data-management',
        component: { template: '<div>Backoffice Data Management</div>' },
        meta: { isBackOffice: true },
      },
      {
        path: '/:language/back-office/documentation-editing',
        name: 'backoffice-documentation-editing',
        component: { template: '<div>Backoffice Documentation Editing</div>' },
        meta: { isBackOffice: true },
      },
      {
        path: '/:language/system/user-management',
        name: 'system-user-management',
        component: { template: '<div>System User Management</div>' },
        meta: { isSystem: true },
      },
      {
        path: '/:language/system/module-management',
        name: 'system-module-management',
        component: { template: '<div>System Module Management</div>' },
        meta: { isSystem: true },
      },
      {
        path: '/:language/system/logs',
        name: 'system-logs',
        component: { template: '<div>System Logs</div>' },
        meta: { isSystem: true },
      },
      { path: '/en', name: 'en', component: { template: '<div>EN</div>' } },
      { path: '/fr', name: 'fr', component: { template: '<div>FR</div>' } },
      {
        path: '/:language/:unit/:year/module/:module',
        name: 'module',
        component: { template: '<div>Module</div>' },
        meta: { breadcrumb: true },
      },
      {
        path: '/:language/:unit/:year/results',
        name: 'results',
        component: { template: '<div>Results</div>' },
      },
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

  // Register Quasar components globally
  app.component('QHeader', QHeader);
  app.component('QToolbar', QToolbar);
  app.component('QToolbarTitle', QToolbarTitle);
  app.component('QImg', QImg);
  app.component('QSpace', QSpace);
  app.component('QBtn', QBtn);
  app.component('QBtnDropdown', QBtnDropdown);
  app.component('QList', QList);
  app.component('QItem', QItem);
  app.component('QItemSection', QItemSection);
  app.component('QItemLabel', QItemLabel);
  app.component('QIcon', QIcon);
  app.component('QSeparator', QSeparator);
  app.component('QBreadcrumbs', QBreadcrumbs);
  app.component('QBreadcrumbsEl', QBreadcrumbsEl);
  app.component('QLayout', QLayout);
  app.component('QPageContainer', QPageContainer);
  app.component('QPage', QPage);
  app.component('QCard', QCard);
  app.component('QCardSection', QCardSection);
  app.component('QCheckbox', QCheckbox);
  app.component('QInput', QInput);

  // Register custom SVG icons
  app.config.globalProperties.$moduleIcons = icons;
});

const preview: Preview = {
  parameters: {
    options: {
      storySort: {
        order: [
          'Documentation',
          'Atoms',
          'Molecules',
          'Charts',
          'Organisms',
          'Layout',
        ],
      },
    },
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
        'xl-desktop': {
          name: 'XL Desktop',
          styles: { width: '2560px', height: '1440px' },
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
