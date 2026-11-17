const importLoginPage = () => import('@/pages/app/LoginPage.vue');

let started: ReturnType<typeof importLoginPage> | null = null;

// Called on the first navigation to the login URL, so the page downloads
// while authGuard waits for the session call instead of after it.
export function preloadLoginPage(): void {
  started = importLoginPage();
  // Only marks the promise as observed: a signed-in visitor never uses it.
  // The route awaits `started` itself and reports a failure to the router.
  started.catch(() => undefined);
}

// Component loader of the login route. Reuses the started download, handed
// out once, so a failed download fails one navigation and the next retries.
export function loadLoginPage(): ReturnType<typeof importLoginPage> {
  const pending = started ?? importLoginPage();
  started = null;
  return pending;
}
