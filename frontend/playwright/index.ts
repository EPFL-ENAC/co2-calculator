// Import styles, initialize component theme here.
// import '../src/common.css';
import '../src/App.vue'; // Example import of a component to be used in the component tests.

import { beforeMount } from '@playwright/experimental-ct-vue/hooks';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

// Pinia stores in this app (e.g. useModuleStore) call useRoute() at setup
// time, so any CT mount that instantiates a store needs both plugins
// installed globally, the same way main.ts wires them for the real app.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
});

beforeMount(async ({ app }) => {
  app.use(createPinia());
  app.use(router);
});
