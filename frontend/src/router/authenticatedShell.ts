import { shallowRef, type Component } from 'vue';

// What every signed-in screen draws but the login page does not. Kept out of
// the entry bundle so the first screen downloads less JavaScript.
export const loadHomePage = () => import('@/pages/app/HomePage.vue');

interface ShellParts {
  Co2Header: Component;
  Co2Sidebar: Component;
  Co2ModuleSidebar: Component;
}

// Set before the navigation is confirmed, so MainLayout renders the parts as
// plain components in the same frame as the page (an async component would
// paint one frame later and shift the content).
const parts = shallowRef<ShellParts | null>(null);

let shell: Promise<unknown> = Promise.resolve();

// Called as soon as the session is known, so the chunks download while the
// workspace guards wait for the API instead of after them.
export function preloadAuthenticatedShell(): void {
  shell = Promise.all([
    import('@/components/layout/Co2Header.vue'),
    import('@/components/layout/Co2Sidebar.vue'),
    import('@/components/organisms/layout/Co2ModuleSidebar.vue'),
    loadHomePage(),
  ]).then(([header, sidebar, moduleSidebar]) => {
    parts.value = {
      Co2Header: header.default,
      Co2Sidebar: sidebar.default,
      Co2ModuleSidebar: moduleSidebar.default,
    };
  });
}

// Awaited before a navigation is confirmed, so the header and sidebars never
// pop in late. Handed out once: a failed download fails one navigation only.
export function authenticatedShellReady(): Promise<unknown> {
  const pending = shell;
  shell = Promise.resolve();
  return pending;
}

// Only signed-in screens call this, and the router loaded the parts before
// confirming them: a miss is a router bug, so it throws instead of hiding.
export function shellParts(): ShellParts {
  if (!parts.value) {
    throw new Error('Signed-in layout rendered before its parts were loaded');
  }
  return parts.value;
}
