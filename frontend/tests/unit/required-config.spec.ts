/**
 * Startup check of the runtime configuration (#500). The app has no
 * institution defaults, so a missing variable must stop the startup with
 * the variable name.
 */
import { test, expect } from 'playwright/test';

import { runtimeConfig } from '../../src/config/runtime';
import {
  missingConfigVariables,
  requiredConfigError,
} from '../../src/config/requiredConfig';

const COMPLETE = {
  ...runtimeConfig,
  matomoUrl: '',
  matomoSiteId: '',
  demoMode: false,
  productionUrl: '',
  institution: {
    ...runtimeConfig.institution,
    name: 'Test University',
    nameFrDe: "de l'Université Test",
    nameFrA: "à l'Université Test",
    idLabel: 'Member number',
    contactEmail: 'support@university.example',
    strategyUrl: 'https://university.example/strategy',
    strategyUrlFr: 'https://university.example/fr/strategie',
    userDocUrl: 'https://docs.university.example',
    backofficeDocUrl: 'https://backoffice-docs.university.example',
  },
};

test('a complete configuration starts', () => {
  expect(requiredConfigError(COMPLETE)).toBeNull();
});

test('a missing institution variable stops the startup with its name', () => {
  const config = {
    ...COMPLETE,
    institution: { ...COMPLETE.institution, name: '', contactEmail: '' },
  };
  expect(missingConfigVariables(config)).toEqual([
    'APP_INSTITUTION_NAME',
    'APP_INSTITUTION_CONTACT_EMAIL',
  ]);
  expect(requiredConfigError(config)).toContain(
    'APP_INSTITUTION_NAME, APP_INSTITUTION_CONTACT_EMAIL',
  );
});

test('a Matomo site id needs the Matomo URL', () => {
  expect(missingConfigVariables({ ...COMPLETE, matomoSiteId: '7' })).toEqual([
    'APP_INSTITUTION_MATOMO_URL',
  ]);
});

test('demo mode needs the production URL', () => {
  expect(missingConfigVariables({ ...COMPLETE, demoMode: true })).toEqual([
    'APP_INSTITUTION_PRODUCTION_URL',
  ]);
});
