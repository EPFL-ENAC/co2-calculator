// Matomo (web analytics) page-view tracking.
//
// Loads Matomo's own tracker rather than hand-rolling a beacon: it is versioned
// with the server we point at, and opt-out, DoNotTrack and link tracking come
// with it. No npm dependency.
//
// Both the script and the hits go through our own backend (#2649): content
// blockers drop `matomo.js` and `matomo.php` by filename whatever host serves
// them, so a direct call to Matomo is blocked in a large share of browsers.
// The backend holds the upstream URL — see backend/app/api/v1/analytics.py.
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
  siteId: string;
  environment: string;
}

// Same-origin proxy paths. Neutral names on purpose — `/analytics/matomo.js`
// would be blocked exactly like the upstream URL. Mirrors API_BASE_URL in
// src/api/http.ts; not imported from there because that module pulls in the ky
// client and i18n, which the tracker has no business loading.
const PROXY_BASE = '/api/v1/analytics/';

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

export function trackerScriptSrc(): string {
  return `${PROXY_BASE}js`;
}

// The queue seeded before matomo.js loads. Empty when tracking is disabled —
// callers use that to skip injecting the script at all.
export function matomoInitCommands(config: MatomoConfig): MatomoCommand[] {
  if (!isTrackingEnabled(config)) return [];
  return [
    // Cookieless: no consent banner and no new i18n strings. Unique-visitor
    // counts become approximate; the page-view trends #2649 asks for don't.
    ['disableCookies'],
    ['enableLinkTracking'],
    ['setCustomDimension', ENVIRONMENT_DIMENSION_ID, config.environment],
    ['setTrackerUrl', `${PROXY_BASE}track`],
    ['setSiteId', config.siteId],
  ];
}

// Split a route pattern on its real segment boundaries. A plain `split('/')`
// would cut inside an inline regex — `:unit([^/]+)` contains a slash — and
// shift every segment after it out of alignment with the path.
function splitPattern(pattern: string): string[] {
  const segments: string[] = [];
  let current = '';
  let depth = 0;
  for (let i = 0; i < pattern.length; i += 1) {
    const char = pattern[i];
    if (char === '\\') {
      current += char + (pattern[i + 1] ?? '');
      i += 1;
      continue;
    }
    if (char === '(') depth += 1;
    if (char === ')') depth -= 1;
    if (char === '/' && depth === 0) {
      segments.push(current);
      current = '';
      continue;
    }
    current += char;
  }
  segments.push(current);
  return segments;
}

// The param a pattern segment declares, e.g. `:unit([^/]+)` → `unit`, or
// undefined for a literal segment. The name ends at the inline regex or a
// repeat/optional modifier.
function paramName(patternSegment: string): string | undefined {
  if (!patternSegment.startsWith(':')) return undefined;
  const end = patternSegment.search(/[(?+*]/);
  return end === -1 ? patternSegment.slice(1) : patternSegment.slice(1, end);
}

// Path with every non-allow-listed param segment replaced by `_`.
//
// Masking is positional — each path segment is judged by the matched route
// pattern above it, never by comparing it to param values. Comparing values
// would both over-mask (a plan id of 2024 would blank the year segment) and
// under-mask (`route.path` keeps percent-encoding while `route.params` is
// decoded, so a unit needing encoding would sail through unmasked).
//
// Reads `path` only, so query strings — which can carry tokens or filter
// values — are dropped wholesale rather than allow-listed. A segment with no
// pattern above it (the not-found catch-all, or an unmatched route) is masked:
// the failure direction is losing a dimension, never leaking an identifier.
export function buildTrackedUrl(route: RouteLocationNormalized): string {
  const pattern = route.matched.at(-1)?.path ?? '';
  const patternSegments = splitPattern(pattern);
  return route.path
    .split('/')
    .map((segment, index) => {
      const patternSegment = patternSegments[index];
      if (patternSegment === undefined) return MASK;
      const name = paramName(patternSegment);
      if (name === undefined) return segment;
      return TRACKED_PARAMS.has(name) ? segment : MASK;
    })
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
  // Same-origin now, but the tracker has no use for a Referer either way, and
  // the default policy would hand it the unmasked SPA path.
  script.referrerPolicy = 'no-referrer';
  script.src = trackerScriptSrc();
  document.head.appendChild(script);
  enabled = true;
}

export function trackPageView(route: RouteLocationNormalized): void {
  if (!enabled) return;
  // Absolute URLs: Matomo groups pages by host and resolves a relative URL —
  // custom or referrer — against the tracker's own host, which would attribute
  // every intra-SPA navigation to the analytics server.
  const url = `${window.location.origin}${buildTrackedUrl(route)}`;
  if (previousUrl) push(['setReferrerUrl', previousUrl]);
  push(['setCustomUrl', url]);
  push(['setDocumentTitle', buildTrackedTitle(route)]);
  push(['trackPageView']);
  // Re-scan the freshly rendered view for outbound/download links.
  push(['enableLinkTracking']);
  previousUrl = url;
}
