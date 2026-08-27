interface ImportMetaEnv {
  readonly APP_VERSION: string;
  readonly APP_BUILD_TIME: string;
  readonly APP_SENTRY_DSN: string;
  readonly APP_ENVIRONMENT: string;
  readonly APP_MAP_TILE_STYLE_URL: string;
  readonly APP_ACCESS_MANAGEMENT_PROVIDER_NAME: string;
  readonly APP_ACCESS_MANAGEMENT_PROVIDER_URL: string;
  readonly APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL: string;
  readonly APP_ROLES_DOC_URL: string;
  readonly APP_EQUIPMENT_POWER_FEEDBACK_EMAIL: string;
  readonly APP_PLANNER_MIN_YEAR: string;
  readonly APP_PLANNER_MAX_YEAR: string;
}

interface Window {
  // Set at runtime by Lighthouse CI (injected into index.html) to bypass auth guards.
  __LIGHTHOUSE_BYPASS__?: boolean;
}
