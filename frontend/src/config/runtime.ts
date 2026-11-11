// Runtime configuration values.
//
// Same Vite bundle ships to dev/stage/prod; per-environment values come from
// window.injectedEnvVariable, populated at container startup by
// docker/entrypoint.sh writing public/injectEnv.js.
//
// In `quasar dev` the placeholder is empty, so we fall back to build-time
// values from quasar.config.js `build.defineEnv` (Quasar/Vite replaces
// literal `import.meta.env.APP_X` text in the bundle via Vite's `define`).
//
// IMPORTANT: import.meta.env access here must be a *literal* property name —
// dynamic access like `import.meta.env[key]` is NOT replaced (it's a textual
// transform, not a runtime object) and will be undefined at runtime.
//
// APP_VERSION and APP_BUILD_TIME identify the bundle itself, so they don't
// have a runtime fallback — every container running this image sees the same
// value.
//
// `hasViteEnv &&` guards every access below: Playwright's component-test
// collection phase loads this module directly in Node, without Vite's
// transform, where `import.meta.env` is plain `undefined` (not even an empty
// object) — an unguarded `import.meta.env.APP_X` throws there. Under Quasar's
// actual build/dev the guard is free: `import.meta.env.APP_X` is statically
// replaced with its literal value (or with `""`, which `||` treats the same
// as absent) and the bare `import.meta.env` is always a truthy object.

import { isDemoMode } from '@/utils/demoMode';

declare global {
  interface Window {
    injectedEnvVariable?: Record<string, string | undefined>;
  }
}

const injected: Record<string, string | undefined> =
  (typeof window !== 'undefined' && window.injectedEnvVariable) || {};

const hasViteEnv = typeof import.meta.env !== 'undefined';

// `||` not `??`: empty string from an unset pod env should fall through to the
// next layer, not be treated as a real value. (e.g. APP_SENTRY_DSN="" should
// disable Sentry, not set the DSN to an empty string and crash init.)
export const runtimeConfig = {
  sentryDsn:
    injected.APP_SENTRY_DSN ||
    (hasViteEnv && import.meta.env.APP_SENTRY_DSN) ||
    undefined,
  environment:
    injected.APP_ENVIRONMENT ||
    (hasViteEnv && import.meta.env.APP_ENVIRONMENT) ||
    'development',
  release: (hasViteEnv && import.meta.env.APP_VERSION) || undefined,
  buildTime: (hasViteEnv && import.meta.env.APP_BUILD_TIME) || undefined,
  // Raster-tile URL template for the MapLibre maps in the Professional
  // Travel module. Defaults to OSM raster tiles; can be overridden per-pod
  // via APP_MAP_TILE_STYLE_URL on /injectEnv.js to switch to an internal
  // mirror or a paid provider without code changes.
  mapTileStyleUrl:
    injected.APP_MAP_TILE_STYLE_URL ||
    (hasViteEnv && import.meta.env.APP_MAP_TILE_STYLE_URL) ||
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  // Access-management provider (display label + portal URL) shown in the
  // calculator's access popover for role delegation. Free text — unrelated to
  // the backend PROVIDER_PLUGIN role provider. No default: when unset the
  // popover CTA/label is hidden. Set per-pod to rebrand for another institution.
  accessManagementProviderName:
    injected.APP_INSTITUTION_ACCESS_PROVIDER_NAME ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_ACCESS_PROVIDER_NAME) ||
    '',
  accessManagementProviderUrl:
    injected.APP_INSTITUTION_ACCESS_PROVIDER_URL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_ACCESS_PROVIDER_URL) ||
    '',
  accessManagementProviderAboutUrl:
    injected.APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL) ||
    '',
  // Documentation page explaining the calculator's roles, linked from the same
  // popover. Per-pod so another institution can point at its own doc site.
  rolesDocUrl:
    injected.APP_INSTITUTION_ROLES_DOC_URL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_ROLES_DOC_URL) ||
    '',
  // Recipient for the Equipment "power feedback" mailto (issue #266). The address
  // can depend on the institution, so it is configurable per-pod via
  // APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL on /injectEnv.js rather than hardcoded.
  equipmentPowerFeedbackEmail:
    injected.APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL) ||
    '',
  // Matomo web analytics. The site id is the on/off switch: empty means
  // src/boot/matomo.ts loads no tracker. A site id without a URL stops the
  // startup (src/config/requiredConfig.ts). One Matomo site per instance.
  matomoUrl:
    injected.APP_INSTITUTION_MATOMO_URL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_MATOMO_URL) ||
    '',
  matomoSiteId:
    injected.APP_INSTITUTION_MATOMO_SITE_ID ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_MATOMO_SITE_ID) ||
    '',
  // Project-planner horizon: bounds for the start/end year selects. No code
  // default: values come from APP_PLANNER_MIN_YEAR / APP_PLANNER_MAX_YEAR
  // (/injectEnv.js per-pod, .env.local in dev). Unset resolves to NaN and
  // the year selects render empty.
  plannerMinYear: Number(
    injected.APP_PLANNER_MIN_YEAR ||
      (hasViteEnv && import.meta.env.APP_PLANNER_MIN_YEAR) ||
      NaN,
  ),
  plannerMaxYear: Number(
    injected.APP_PLANNER_MAX_YEAR ||
      (hasViteEnv && import.meta.env.APP_PLANNER_MAX_YEAR) ||
      NaN,
  ),
  // Demo instance: APP_DEMO_MODE=true makes App.vue render only a notice
  // pointing to the production app, so the demo can't be used by mistake.
  // Only the literal "true" enables it (see utils/demoMode.ts). Demo mode
  // without a production URL stops the startup (src/config/requiredConfig.ts).
  demoMode: isDemoMode(
    injected.APP_DEMO_MODE || (hasViteEnv && import.meta.env.APP_DEMO_MODE),
  ),
  productionUrl:
    injected.APP_INSTITUTION_PRODUCTION_URL ||
    (hasViteEnv && import.meta.env.APP_INSTITUTION_PRODUCTION_URL) ||
    '',
  // Institution identity (#500): everything that names or brands the
  // institution that runs this instance. No value has a code default: the
  // startup stops when a required one is missing (src/config/requiredConfig.ts).
  // Each pod sets the APP_INSTITUTION_* block (see .env.example).
  institution: {
    // Short name, used as-is in English and in French ("EPFL").
    name:
      injected.APP_INSTITUTION_NAME ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_NAME) ||
      '',
    // French forms with the preposition and the article. The article depends
    // on the name ("de l'EPFL", "du CERN"), so French needs its own values.
    nameFrDe:
      injected.APP_INSTITUTION_NAME_FR_DE ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_NAME_FR_DE) ||
      '',
    nameFrA:
      injected.APP_INSTITUTION_NAME_FR_A ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_NAME_FR_A) ||
      '',
    // Label of the personal identifier the institution gives its members.
    idLabel:
      injected.APP_INSTITUTION_ID_LABEL ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_ID_LABEL) ||
      '',
    contactEmail:
      injected.APP_INSTITUTION_CONTACT_EMAIL ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_CONTACT_EMAIL) ||
      '',
    // Page that presents the sustainability strategy, one URL per language.
    strategyUrl:
      injected.APP_INSTITUTION_STRATEGY_URL ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_STRATEGY_URL) ||
      '',
    strategyUrlFr:
      injected.APP_INSTITUTION_STRATEGY_URL_FR ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_STRATEGY_URL_FR) ||
      '',
    // Documentation site roots, without a trailing slash. The translations
    // append the page path ("/fr/building/").
    userDocUrl:
      injected.APP_INSTITUTION_USER_DOC_URL ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_USER_DOC_URL) ||
      '',
    backofficeDocUrl:
      injected.APP_INSTITUTION_BACKOFFICE_DOC_URL ||
      (hasViteEnv && import.meta.env.APP_INSTITUTION_BACKOFFICE_DOC_URL) ||
      '',
  },
} as const;
