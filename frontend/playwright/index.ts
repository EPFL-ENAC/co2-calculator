// Component-test app context. Pinia backs store-driven components; Quasar
// with Notify keeps the ky error hooks (src/api/http.ts) from crashing on
// non-ok responses, so tests see real HTTPErrors instead of harness noise.
import { beforeMount } from '@playwright/experimental-ct-vue/hooks';
import { createPinia } from 'pinia';
import { Notify, Quasar } from 'quasar';

beforeMount(async ({ app }) => {
  app.use(Quasar, { plugins: { Notify } });
  app.use(createPinia());
});
