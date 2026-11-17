// What every signed-in screen draws but the login page does not. Kept out of
// the entry bundle so the first screen downloads less JavaScript.
export const loadCo2Header = () => import('@/components/layout/Co2Header.vue');
export const loadCo2Sidebar = () =>
  import('@/components/layout/Co2Sidebar.vue');
export const loadCo2ModuleSidebar = () =>
  import('@/components/organisms/layout/Co2ModuleSidebar.vue');
export const loadHomePage = () => import('@/pages/app/HomePage.vue');

let shell: Promise<unknown> = Promise.resolve();

// Called as soon as the session is known, so the chunks download while the
// workspace guards wait for the API instead of after them.
export function preloadAuthenticatedShell(): void {
  shell = Promise.all([
    loadCo2Header(),
    loadCo2Sidebar(),
    loadCo2ModuleSidebar(),
    loadHomePage(),
  ]);
}

// Awaited before a navigation is confirmed, so the header and sidebars never
// pop in late. Handed out once: a failed download fails one navigation only.
export function authenticatedShellReady(): Promise<unknown> {
  const pending = shell;
  shell = Promise.resolve();
  return pending;
}
