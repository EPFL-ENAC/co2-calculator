// Runtime config placeholder.
//
// In production: overwritten by /docker-entrypoint.d/40-inject-env.sh at
// container startup with APP_*-prefixed environment variables (Sentry DSN,
// environment label, etc.).
//
// In `quasar dev`: served as-is (empty object); src/config/runtime.ts falls
// back to import.meta.env.
window.injectedEnvVariable = {};
