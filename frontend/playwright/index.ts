// Component-test app context. Pinia backs store-driven components; Quasar
// with Notify keeps the ky error hooks (src/api/http.ts) from crashing on
// non-ok responses, so tests see real HTTPErrors instead of harness noise.
// Import styles, initialize component theme here.
// import '../src/common.css';
import '../src/App.vue'; // Example import of a component to be used in the component tests.

import { beforeMount } from '@playwright/experimental-ct-vue/hooks';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import {
  Notify,
  Quasar,
  QCard,
  QSeparator,
  QExpansionItem,
  QIcon,
  QTooltip,
} from 'quasar';
import { i18n } from '@/boot/i18n';
// Pinia stores in this app (e.g. useModuleStore) call useRoute() at setup
// time, so any CT mount that instantiates a store needs both plugins
// installed globally, the same way main.ts wires them for the real app.
// i18n is installed for the same reason (useI18n() at setup time).
//
// Quasar's app-vite build auto-registers every q-* tag used in a template;
// this bare Vite instance doesn't, so each component under test must
// register the q-* tags it renders (mirrors storybook/.storybook/preview.ts,
// which solves the same problem for Storybook).
const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
});

beforeMount(async ({ app }) => {
  app.use(Quasar, { plugins: { Notify } });
  app.use(createPinia());
  app.use(router);
  app.use(i18n);

  app.component('QCard', QCard);
  app.component('QSeparator', QSeparator);
  app.component('QExpansionItem', QExpansionItem);
  app.component('QIcon', QIcon);
  app.component('QTooltip', QTooltip);
});
