/**
 * #2649 — tracked URLs must never carry an org unit or a record id.
 *
 * Our paths are `/en/ENAC-IT4R/2024/results`: a small unit plus a timestamp is
 * close to identifying, so `buildTrackedUrl` masks every route param outside
 * the language/year/module allow-list, and reads `path` only so query strings
 * (tokens, filters) can't leak.
 */

import { test, expect } from '@playwright/test';
import type { RouteLocationNormalized } from 'vue-router';

import { buildTrackedUrl, buildTrackedTitle } from '../../src/utils/matomo';

function route(
  path: string,
  params: Record<string, string | string[]>,
  name?: string,
): RouteLocationNormalized {
  return { path, params, name } as unknown as RouteLocationNormalized;
}

test('masks the unit, keeps language, year and module', () => {
  expect(
    buildTrackedUrl(
      route('/en/ENAC-IT4R/2024/equipment', {
        language: 'en',
        unit: 'ENAC-IT4R',
        year: '2024',
        module: 'equipment',
      }),
    ),
  ).toBe('/en/_/2024/equipment');
});

test('masks record ids — plan and simulation addresses', () => {
  expect(
    buildTrackedUrl(
      route('/fr/ENAC-IT4R/2024/simulation/plan/42', {
        language: 'fr',
        unit: 'ENAC-IT4R',
        year: '2024',
        planId: '42',
      }),
    ),
  ).toBe('/fr/_/2024/simulation/plan/_');
});

test('masks a param added later (allow-list, not deny-list)', () => {
  expect(
    buildTrackedUrl(
      route('/en/2024/whatever/secret-value', {
        language: 'en',
        year: '2024',
        futureParam: 'secret-value',
      }),
    ),
  ).toBe('/en/2024/whatever/_');
});

test('drops query strings by reading the path only', () => {
  // `route.fullPath` would carry `?token=...`; buildTrackedUrl never sees it.
  expect(
    buildTrackedUrl(route('/en/back-office/reporting', { language: 'en' })),
  ).toBe('/en/back-office/reporting');
});

test('keeps print routes distinguishable while still masking the unit', () => {
  expect(
    buildTrackedUrl(
      route('/en/ENAC-IT4R/2024/results/print', {
        language: 'en',
        unit: 'ENAC-IT4R',
        year: '2024',
      }),
    ),
  ).toBe('/en/_/2024/results/print');
});

test('title is the route name, and falls back to the masked url', () => {
  const params = { language: 'en', unit: 'ENAC-IT4R', year: '2024' };
  expect(
    buildTrackedTitle(route('/en/ENAC-IT4R/2024/home', params, 'home')),
  ).toBe('home');
  expect(buildTrackedTitle(route('/en/ENAC-IT4R/2024/home', params))).toBe(
    '/en/_/2024/home',
  );
});
