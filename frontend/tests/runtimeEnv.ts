// Runtime variables of the test instance (#500). The app has no institution
// defaults, so the component tests (playwright/testEnv.ts) and the browser
// tests (tests/integration/setup/test.ts) inject these values the same way
// docker/entrypoint.sh does in a container. They are the EPFL values, so the
// text assertions of the suites stay readable.
export const TEST_RUNTIME_ENV: Record<string, string> = {
  APP_INSTITUTION_NAME: 'EPFL',
  APP_INSTITUTION_NAME_FR_DE: "de l'EPFL",
  APP_INSTITUTION_NAME_FR_A: "à l'EPFL",
  APP_INSTITUTION_ID_LABEL: 'SCIPER',
  APP_INSTITUTION_ACCESS_PROVIDER_NAME: 'Accred',
  APP_INSTITUTION_CONTACT_EMAIL: 'co2calculator@epfl.ch',
  APP_INSTITUTION_STRATEGY_URL:
    'https://www.epfl.ch/about/sustainability/strategy/',
  APP_INSTITUTION_STRATEGY_URL_FR:
    'https://www.epfl.ch/about/sustainability/fr/strategie/',
  APP_INSTITUTION_USER_DOC_URL:
    'https://epfl-enac.github.io/co2-calculator-user-doc',
  APP_INSTITUTION_BACKOFFICE_DOC_URL:
    'https://epfl-enac.github.io/co2-calculator-back-office-doc',
  APP_PLANNER_MIN_YEAR: '2016',
  APP_PLANNER_MAX_YEAR: '2050',
};

// Body of /injectEnv.js for a test page, with optional overrides.
export function injectEnvScript(
  overrides: Record<string, string> = {},
): string {
  const env = { ...TEST_RUNTIME_ENV, ...overrides };
  return `window.injectedEnvVariable = ${JSON.stringify(env)};`;
}
