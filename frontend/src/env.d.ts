interface ImportMetaEnv {
  // Bundle identity, baked at build time (quasar.config.js defineEnv). Every
  // other APP_* value is read at runtime from /injectEnv.js.
  readonly APP_VERSION: string;
  readonly APP_BUILD_TIME: string;
}

interface Window {
  // Set at runtime by Lighthouse CI (injected into index.html) to bypass auth guards.
  __LIGHTHOUSE_BYPASS__?: boolean;
}
