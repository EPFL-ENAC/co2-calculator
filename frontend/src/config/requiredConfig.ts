// Startup check of the runtime configuration (#500). No institution value has
// a code default, so a missing variable must stop the app with its name
// instead of rendering empty texts or tracking to nowhere.
import type { runtimeConfig as RuntimeConfigValue } from '@/config/runtime';

type RuntimeConfig = typeof RuntimeConfigValue;

const REQUIRED_INSTITUTION_VARIABLES: [
  keyof RuntimeConfig['institution'],
  string,
][] = [
  ['name', 'APP_INSTITUTION_NAME'],
  ['nameFrDe', 'APP_INSTITUTION_NAME_FR_DE'],
  ['nameFrA', 'APP_INSTITUTION_NAME_FR_A'],
  ['idLabel', 'APP_INSTITUTION_ID_LABEL'],
  ['contactEmail', 'APP_INSTITUTION_CONTACT_EMAIL'],
  ['strategyUrl', 'APP_INSTITUTION_STRATEGY_URL'],
  ['strategyUrlFr', 'APP_INSTITUTION_STRATEGY_URL_FR'],
  ['userDocUrl', 'APP_INSTITUTION_USER_DOC_URL'],
  ['backofficeDocUrl', 'APP_INSTITUTION_BACKOFFICE_DOC_URL'],
];

// Texts name the access management portal (%access_provider%).
const REQUIRED_TOP_LEVEL_VARIABLES: [keyof RuntimeConfig, string][] = [
  ['accessManagementProviderName', 'APP_INSTITUTION_ACCESS_PROVIDER_NAME'],
];

export function missingConfigVariables(config: RuntimeConfig): string[] {
  const missing = REQUIRED_INSTITUTION_VARIABLES.filter(
    ([key]) => config.institution[key] === '',
  ).map(([, variable]) => variable);
  for (const [key, variable] of REQUIRED_TOP_LEVEL_VARIABLES) {
    if (config[key] === '') missing.push(variable);
  }
  if (config.matomoSiteId !== '' && config.matomoUrl === '') {
    missing.push('APP_INSTITUTION_MATOMO_URL');
  }
  if (config.demoMode && config.productionUrl === '') {
    missing.push('APP_INSTITUTION_PRODUCTION_URL');
  }
  return missing;
}

// The startup error, or null when the configuration is complete.
export function requiredConfigError(config: RuntimeConfig): string | null {
  const missing = missingConfigVariables(config);
  if (missing.length === 0) return null;
  return (
    `Missing frontend configuration: ${missing.join(', ')}. ` +
    'Set these variables on the frontend container (see frontend/.env.example).'
  );
}
