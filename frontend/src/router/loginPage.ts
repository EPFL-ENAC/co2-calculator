import { retryableImport } from './retryableImport';

// Preloaded on the first navigation to the login URL, so the page downloads
// while authGuard waits for the session call instead of after it.
export const loginPage = retryableImport(
  () => import('@/pages/app/LoginPage.vue'),
);
