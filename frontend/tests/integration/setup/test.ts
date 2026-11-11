// Playwright `test` for the browser suites (#500). The preview server serves
// the placeholder /injectEnv.js and no institution assets folder, and the app
// refuses to start without its institution variables. So every page gets the
// test instance values and the EPFL assets folder, the same way a container
// gets them. A spec can still route these URLs itself: page routes win over
// context routes.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as base } from 'playwright/test';
import { injectEnvScript } from '../../runtimeEnv';

const ASSETS_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../institution/epfl',
);

export const test = base.extend({
  context: async ({ context }, use) => {
    await context.route('**/injectEnv.js', (route) =>
      route.fulfill({
        contentType: 'application/javascript',
        body: injectEnvScript(),
      }),
    );
    await context.route('**/institution/**', (route) =>
      route.fulfill({
        path: path.join(
          ASSETS_DIR,
          new URL(route.request().url()).pathname.replace(
            /^\/institution\//,
            '',
          ),
        ),
      }),
    );
    await use(context);
  },
});

export { expect } from 'playwright/test';
