// Matomo (web analytics) page-view tracking.
//
// Loads Matomo's own tracker from the configured host rather than hand-rolling
// a beacon: the tracker is versioned with the server we point at, and opt-out,
// DoNotTrack and link tracking come with it. No npm dependency.
//
// Tracking is off unless a site id is configured (one Matomo site per
// instance), so dev, CI and unconfigured pods stay silent.

import type { RouteLocationNormalized } from 'vue-router';

// Matomo's command queue. Pushing works before the tracker script has loaded —
// that is what the array is for; matomo.js replaces it with a real queue.
type MatomoCommand = (string | number)[];

declare global {
  interface Window {
    _paq?: MatomoCommand[];
  }
}

export interface MatomoConfig {
  url: string;
  siteId: string;
  environment: string;
}

// Carries the instance label (development/stage/production) so a pod pointed at
// the wrong site id shows up in the data instead of silently mixing in. Must
// exist as dimension 1 on the Matomo site to be recorded.
const ENVIRONMENT_DIMENSION_ID = 1;

// Route params kept verbatim in tracked URLs. Everything else is masked:
// `unit` is an org acronym (a small unit plus a timestamp is close to
// identifying) and the ids address one user's plan or simulation. Allow-list,
// so a param added later is masked until someone decides otherwise.
const TRACKED_PARAMS = new Set(['language', 'year', 'module']);

const MASK = '_';

export function isTrackingEnabled(config: MatomoConfig): boolean {
  return config.siteId !== '';
}

function trackerBaseUrl(url: string): string {
  return url.endsWith('/') ? url : `${url}/`;
}

export function trackerScriptSrc(url: string): string {
  return `${trackerBaseUrl(url)}matomo.js`;
}

// The queue seeded before matomo.js loads. Empty when tracking is disabled —
// callers use that to skip injecting the script at all.
export function matomoInitCommands(config: MatomoConfig): MatomoCommand[] {
  if (!isTrackingEnabled(config)) return [];
  const base = trackerBaseUrl(config.url);
  return [
    // Cookieless: no consent banner and no new i18n strings. Unique-visitor
    // counts become approximate; the page-view trends #2649 asks for don't.
    ['disableCookies'],
    ['enableLinkTracking'],
    ['setCustomDimension', ENVIRONMENT_DIMENSION_ID, config.environment],
    ['setTrackerUrl', `${base}matomo.php`],
    ['setSiteId', config.siteId],
  ];
}

// Path with every non-allow-listed param value replaced by `_`. Reads `path`
// only, so query strings — which can carry tokens or filter values — are
// dropped wholesale rather than allow-listed.
export function buildTrackedUrl(route: RouteLocationNormalized): string {
  const masked = new Set<string>();
  for (const [name, value] of Object.entries(route.params)) {
    if (TRACKED_PARAMS.has(name)) continue;
    for (const part of Array.isArray(value) ? value : [value]) {
      if (part) masked.add(part);
    }
  }
  return route.path
    .split('/')
    .map((segment) => (masked.has(segment) ? MASK : segment))
    .join('/');
}

// The route name, never the rendered document title: rendered titles carry
// unit names.
export function buildTrackedTitle(route: RouteLocationNormalized): string {
  return typeof route.name === 'string' ? route.name : buildTrackedUrl(route);
}

let enabled = false;
let previousUrl = '';

function push(command: MatomoCommand): void {
  window._paq = window._paq ?? [];
  window._paq.push(command);
}

export function initMatomo(config: MatomoConfig): void {
  const commands = matomoInitCommands(config);
  if (commands.length === 0) return;
  commands.forEach(push);

  const script = document.createElement('script');
  script.async = true;
  script.src = trackerScriptSrc(config.url);
  document.head.appendChild(script);
  enabled = true;
}

export function trackPageView(route: RouteLocationNormalized): void {
  if (!enabled) return;
  const url = buildTrackedUrl(route);
  if (previousUrl) push(['setReferrerUrl', previousUrl]);
  // Absolute URL: Matomo groups pages by host, and a relative custom URL is
  // resolved against the tracker's own host.
  push(['setCustomUrl', `${window.location.origin}${url}`]);
  push(['setDocumentTitle', buildTrackedTitle(route)]);
  push(['trackPageView']);
  // Re-scan the freshly rendered view for outbound/download links.
  push(['enableLinkTracking']);
  previousUrl = url;
}
