// Runtime configuration values.
//
// The same bundle ships to every deployment and every institution. The values
// come from window.injectedEnvVariable, which /injectEnv.js sets. In the
// container docker/entrypoint.sh writes that file from the APP_* environment
// variables at startup. `quasar dev`, `vite preview` and the component tests
// get it from the same script through build/institution-plugin.js, so every
// run reads its values the same way (#3244).
//
// APP_VERSION and APP_BUILD_TIME identify the bundle itself, so they stay
// build-time values. `hasViteEnv &&` guards them because Playwright's
// component-test collection loads this module in Node, where
// `import.meta.env` is undefined.
//
// No value has an institution default: an empty required value shows the
// missing-values page (see `missingConfig` and App.vue).

import { isDemoMode } from '@/utils/demoMode';

declare global {
  interface Window {
    injectedEnvVariable?: Record<string, string | undefined>;
  }
}

const injected: Record<string, string | undefined> =
  (typeof window !== 'undefined' && window.injectedEnvVariable) || {};

const hasViteEnv = typeof import.meta.env !== 'undefined';

// An unset pod variable and an empty one mean the same thing: no value.
const read = (key: string): string => injected[key] ?? '';

// The institution values every deployment sets. The texts and the links of
// the app use them, so the app does not start without them.
export const REQUIRED_KEYS = [
  'APP_INSTITUTION_NAME',
  'APP_INSTITUTION_NAME_FR_DE',
  'APP_INSTITUTION_NAME_FR_A',
  'APP_INSTITUTIONAL_ID_LABEL',
  'APP_CONTACT_EMAIL',
  'APP_USER_DOC_URL',
  'APP_BACKOFFICE_DOC_URL',
  'APP_STRATEGY_URL_EN',
  'APP_STRATEGY_URL_FR',
] as const;

const demoMode = isDemoMode(read('APP_DEMO_MODE'));

// A value that a switch makes required: the switch is on, the value is empty.
const conditionalMissing = [
  read('APP_MATOMO_SITE_ID') && !read('APP_MATOMO_URL') ? 'APP_MATOMO_URL' : '',
  demoMode && !read('APP_PRODUCTION_URL') ? 'APP_PRODUCTION_URL' : '',
].filter(Boolean);

export const missingConfig: readonly string[] = [
  ...REQUIRED_KEYS.filter((key) => !read(key)),
  ...conditionalMissing,
];

// The texts add a page path after these URLs, for example
// `%user_doc_url%fr/headcount/`, so a URL without a final "/" gives broken
// links. The missing-values page lists it.
const SLASH_KEYS = ['APP_USER_DOC_URL', 'APP_BACKOFFICE_DOC_URL'] as const;
export const invalidConfig: readonly string[] = SLASH_KEYS.filter(
  (key) => read(key) !== '' && !read(key).endsWith('/'),
);

export const runtimeConfig = {
  // Sentry/GlitchTip DSN. Empty disables Sentry (src/boot/sentry.ts).
  sentryDsn: read('APP_SENTRY_DSN') || undefined,
  environment: read('APP_ENVIRONMENT') || 'development',
  release: (hasViteEnv && import.meta.env.APP_VERSION) || undefined,
  buildTime: (hasViteEnv && import.meta.env.APP_BUILD_TIME) || undefined,
  // Raster-tile URL template for the MapLibre maps of Professional Travel.
  // OpenStreetMap is a public service, not an institution value.
  mapTileStyleUrl:
    read('APP_MAP_TILE_STYLE_URL') ||
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',

  institution: {
    name: read('APP_INSTITUTION_NAME'),
    nameFrDe: read('APP_INSTITUTION_NAME_FR_DE'),
    nameFrA: read('APP_INSTITUTION_NAME_FR_A'),
    institutionalIdLabel: read('APP_INSTITUTIONAL_ID_LABEL'),
    contactEmail: read('APP_CONTACT_EMAIL'),
    userDocUrl: read('APP_USER_DOC_URL'),
    backofficeDocUrl: read('APP_BACKOFFICE_DOC_URL'),
    strategyUrlEn: read('APP_STRATEGY_URL_EN'),
    strategyUrlFr: read('APP_STRATEGY_URL_FR'),
  },

  // Optional links. An empty value hides the link that uses it.
  links: {
    accessManagementUrl: read('APP_ACCESS_MANAGEMENT_URL'),
    accessManagementAboutUrl: read('APP_ACCESS_MANAGEMENT_ABOUT_URL'),
    rolesDocUrl: read('APP_ROLES_DOC_URL'),
    sourceCodeUrl: read('APP_SOURCE_CODE_URL'),
    userDocSourceUrl: read('APP_USER_DOC_SOURCE_URL'),
    backofficeDocSourceUrl: read('APP_BACKOFFICE_DOC_SOURCE_URL'),
    developerDocUrl: read('APP_DEVELOPER_DOC_URL'),
  },

  // Operations links of the system logs page, for this deployment only.
  opsLinks: {
    argocd: read('APP_OPS_ARGOCD_URL'),
    grafanaDashboard: read('APP_OPS_GRAFANA_DASHBOARD_URL'),
    grafanaGraphs: read('APP_OPS_GRAFANA_GRAPHS_URL'),
    logs: read('APP_OPS_LOGS_URL'),
    openshift: read('APP_OPS_OPENSHIFT_URL'),
  },

  // Recipient of the Equipment "power feedback" mailto (#266). Empty hides it.
  equipmentPowerFeedbackEmail: read('APP_EQUIPMENT_POWER_FEEDBACK_EMAIL'),
  // Matomo web analytics. The site id is the on/off switch: empty means
  // src/boot/matomo.ts loads no tracker. With a site id the URL is required.
  matomoUrl: read('APP_MATOMO_URL'),
  matomoSiteId: read('APP_MATOMO_SITE_ID'),
  // Project-planner horizon. Unset resolves to NaN and the selects stay empty.
  plannerMinYear: Number(read('APP_PLANNER_MIN_YEAR') || NaN),
  plannerMaxYear: Number(read('APP_PLANNER_MAX_YEAR') || NaN),
  // Demo instance: APP_DEMO_MODE=true makes App.vue render only a notice
  // that links to APP_PRODUCTION_URL, so the demo is not used by mistake.
  demoMode,
  productionUrl: read('APP_PRODUCTION_URL'),
} as const;
