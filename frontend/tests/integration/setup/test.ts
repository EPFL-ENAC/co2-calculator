// Playwright `test` for the browser suites (#500). The preview server serves
// the placeholder /injectEnv.js, and the app refuses to start without its
// institution variables, so every page gets the test instance values. A spec
// can still route /injectEnv.js itself: page routes win over context routes.
import { test as base } from 'playwright/test';
import { injectEnvScript } from '../../runtimeEnv';

export const test = base.extend({
  context: async ({ context }, use) => {
    await context.route('**/injectEnv.js', (route) =>
      route.fulfill({
        contentType: 'application/javascript',
        body: injectEnvScript(),
      }),
    );
    await use(context);
  },
});

export { expect } from 'playwright/test';
