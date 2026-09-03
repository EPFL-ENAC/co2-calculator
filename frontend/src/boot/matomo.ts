import { defineBoot } from '#q-app';
import { runtimeConfig } from '@/config/runtime';
import { initMatomo, trackPageView } from '@/utils/matomo';

export default defineBoot(({ router }) => {
  // Lighthouse CI drives the app with this flag set; its runs would otherwise
  // land in the usage numbers.
  if (window.__LIGHTHOUSE_BYPASS__) return;

  initMatomo({
    siteId: runtimeConfig.matomoSiteId,
    environment: runtimeConfig.environment,
  });

  // afterEach fires for the initial navigation too, so the landing page is
  // tracked without a separate first-view call.
  router.afterEach((to) => trackPageView(to));
});
