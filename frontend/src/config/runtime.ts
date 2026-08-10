// Runtime configuration values.
//
// Same Vite bundle ships to dev/stage/prod; per-environment values come from
// window.injectedEnvVariable, populated at container startup by
// docker/entrypoint.sh writing public/injectEnv.js.
//
// In `quasar dev` the placeholder is empty, so we fall back to build-time
// values from quasar.config.js `build.defineEnv` (Quasar/Vite replaces literal
// `import.meta.env.APP_X` text in the bundle via Vite's `define`).
//
// IMPORTANT: import.meta.env access here must be a *literal* property name —
// dynamic access like `import.meta.env[key]` is NOT replaced (it's a textual
// transform, not a runtime object) and will be undefined at runtime.
//
// APP_VERSION and APP_BUILD_TIME identify the bundle itself, so they don't
// have a runtime fallback — every container running this image sees the same
// value.

declare global {
  interface Window {
    injectedEnvVariable?: Record<string, string | undefined>;
  }
}

const injected: Record<string, string | undefined> =
  (typeof window !== 'undefined' && window.injectedEnvVariable) || {};

// `||` not `??`: empty string from an unset pod env should fall through to the
// next layer, not be treated as a real value. (e.g. APP_SENTRY_DSN="" should
// disable Sentry, not set the DSN to an empty string and crash init.)
export const runtimeConfig = {
  sentryDsn: injected.APP_SENTRY_DSN || import.meta.env.APP_SENTRY_DSN || undefined,
  environment:
    injected.APP_ENVIRONMENT || import.meta.env.APP_ENVIRONMENT || 'development',
  release: import.meta.env.APP_VERSION,
  buildTime: import.meta.env.APP_BUILD_TIME,
  // Raster-tile URL template for the MapLibre maps in the Professional
  // Travel module. Defaults to OSM raster tiles; can be overridden per-pod
  // via APP_MAP_TILE_STYLE_URL on /injectEnv.js to switch to an internal
  // mirror or a paid provider without code changes.
  mapTileStyleUrl:
    injected.APP_MAP_TILE_STYLE_URL ||
    import.meta.env.APP_MAP_TILE_STYLE_URL ||
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  // Access-management provider (display label + portal URL) shown in the
  // calculator's access popover for role delegation. Free text — unrelated to
  // the backend PROVIDER_PLUGIN role provider. No default: when unset the
  // popover CTA/label is hidden. Set per-pod to rebrand for another institution.
  accessManagementProviderName:
    injected.APP_ACCESS_MANAGEMENT_PROVIDER_NAME ||
    import.meta.env.APP_ACCESS_MANAGEMENT_PROVIDER_NAME ||
    '',
  accessManagementProviderUrl:
    injected.APP_ACCESS_MANAGEMENT_PROVIDER_URL ||
    import.meta.env.APP_ACCESS_MANAGEMENT_PROVIDER_URL ||
    '',
  // Recipient for the Equipment "power feedback" mailto (issue #266). The address
  // can depend on the institution, so it is configurable per-pod via
  // APP_EQUIPMENT_POWER_FEEDBACK_EMAIL on /injectEnv.js rather than hardcoded.
  equipmentPowerFeedbackEmail:
    injected.APP_EQUIPMENT_POWER_FEEDBACK_EMAIL ||
    import.meta.env.APP_EQUIPMENT_POWER_FEEDBACK_EMAIL ||
    '',
} as const;
