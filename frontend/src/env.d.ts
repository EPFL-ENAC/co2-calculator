interface ImportMetaEnv {
  readonly APP_VERSION: string;
  readonly APP_BUILD_TIME: string;
  readonly APP_SENTRY_DSN: string;
  readonly APP_ENVIRONMENT: string;
  readonly APP_MAP_TILE_STYLE_URL: string;
  readonly APP_INSTITUTION_ACCESS_PROVIDER_NAME: string;
  readonly APP_INSTITUTION_ACCESS_PROVIDER_URL: string;
  readonly APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL: string;
  readonly APP_INSTITUTION_ROLES_DOC_URL: string;
  readonly APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL: string;
  readonly APP_INSTITUTION_MATOMO_URL: string;
  readonly APP_INSTITUTION_MATOMO_SITE_ID: string;
  readonly APP_PLANNER_MIN_YEAR: string;
  readonly APP_PLANNER_MAX_YEAR: string;
  readonly APP_DEMO_MODE: string;
  readonly APP_INSTITUTION_PRODUCTION_URL: string;
  readonly APP_INSTITUTION_NAME: string;
  readonly APP_INSTITUTION_NAME_FR_DE: string;
  readonly APP_INSTITUTION_NAME_FR_A: string;
  readonly APP_INSTITUTION_ID_LABEL: string;
  readonly APP_INSTITUTION_LOGO_URL: string;
  readonly APP_INSTITUTION_FAVICON_URL: string;
  readonly APP_INSTITUTION_ACCENT_COLOR: string;
  readonly APP_INSTITUTION_CONTACT_EMAIL: string;
  readonly APP_INSTITUTION_STRATEGY_URL: string;
  readonly APP_INSTITUTION_STRATEGY_URL_FR: string;
  readonly APP_INSTITUTION_USER_DOC_URL: string;
  readonly APP_INSTITUTION_BACKOFFICE_DOC_URL: string;
}

interface Window {
  // Set at runtime by Lighthouse CI (injected into index.html) to bypass auth guards.
  __LIGHTHOUSE_BYPASS__?: boolean;
}
