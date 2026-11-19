import { shallowRef, type Component } from 'vue';
import { retryableImport } from './retryableImport';

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

// Preloaded as soon as the session is known, so the chunks download while
// the workspace guards wait for the API. Awaited before a signed-in page is
// confirmed (router/index.ts), so the header and sidebars never pop in late.
export const authenticatedShell = retryableImport(() => {
  // The home page is the usual first screen: start its download too, but do
  // not wait for it. A deep link must not fail on a chunk it never draws;
  // the home route awaits its own import.
  loadHomePage().catch(() => undefined);
  return Promise.all([
    import('@/components/layout/Co2Header.vue'),
    import('@/components/layout/Co2Sidebar.vue'),
    import('@/components/organisms/layout/Co2ModuleSidebar.vue'),
  ]).then(([header, sidebar, moduleSidebar]) => {
    parts.value = {
      Co2Header: header.default,
      Co2Sidebar: sidebar.default,
      Co2ModuleSidebar: moduleSidebar.default,
    };
  });
});

// Only signed-in screens call this, and the router loaded the parts before
// confirming them: a miss is a router bug, so it throws instead of hiding.
export function shellParts(): ShellParts {
  if (!parts.value) {
    throw new Error('Signed-in layout rendered before its parts were loaded');
  }
  return parts.value;
}
