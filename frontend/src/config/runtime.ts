// Runtime configuration values.
//
// Same Vite bundle ships to dev/stage/prod; per-environment values come from
// window.injectedEnvVariable, populated at container startup by
// docker/entrypoint.sh writing public/injectEnv.js.
//
// In `quasar dev` the placeholder is empty, so we fall back to build-time
// values from quasar.config.js `build.env` (Quasar/Vite replaces literal
// `process.env.APP_X` text in the bundle via Vite's `define`).
//
// IMPORTANT: process.env access here must be a *literal* property name —
// dynamic access like `process.env[key]` is NOT replaced (it's a textual
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
  sentryDsn: injected.APP_SENTRY_DSN || process.env.APP_SENTRY_DSN || undefined,
  environment:
    injected.APP_ENVIRONMENT || process.env.APP_ENVIRONMENT || 'development',
  release: process.env.APP_VERSION,
  buildTime: process.env.APP_BUILD_TIME,
} as const;
