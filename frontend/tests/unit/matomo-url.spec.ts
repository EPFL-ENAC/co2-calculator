/**
 * #2649 — tracked URLs must never carry an org unit or a record id.
 *
 * Our paths are `/en/ENAC-IT4R/2024/results`: a small unit plus a timestamp is
 * close to identifying, so `buildTrackedUrl` keeps only the language/year/
 * module params and masks the rest.
 *
 * Masking is positional (each segment judged by the route pattern above it),
 * so these cases exercise a real router rather than a hand-built route object —
 * the mechanism depends on `matched[].path` being the *absolute* pattern for a
 * nested record, which is exactly the kind of assumption a fixture would fake.
 */

import { test, expect } from '@playwright/test';
import {
  createMemoryHistory,
  createRouter,
  type RouteLocationNormalized,
  type RouteRecordRaw,
} from 'vue-router';

import { buildTrackedUrl, buildTrackedTitle } from '../../src/utils/matomo';

// Mirrors the nesting and param patterns of src/router/routes.ts.
const routes: RouteRecordRaw[] = [
  {
    path: '/:language(en|fr)/:unit([^/]+)/:year(\\d{4})/results/print',
    name: 'results-print',
    component: {},
  },
  {
    path: '/',
    component: {},
    children: [
      {
        path: ':language(en|fr)',
        component: {},
        children: [
          {
            path: ':unit([^/]+)/:year(\\d{4})',
            component: {},
            children: [
              {
                path: ':module(equipment|travel)',
                name: 'module',
                component: {},
              },
              { path: 'results', name: 'results', component: {} },
              {
                path: 'simulation/plan/:planId(\\d+)',
                name: 'plan',
                component: {},
              },
            ],
          },
          { path: 'back-office/reporting', name: 'reporting', component: {} },
        ],
      },
    ],
  },
  { path: '/:catchAll(.*)*', name: 'not-found', component: {} },
];

const router = createRouter({ history: createMemoryHistory(), routes });

function resolve(url: string): RouteLocationNormalized {
  return router.resolve(url);
}

test('masks the unit, keeps language, year and module', () => {
  expect(buildTrackedUrl(resolve('/en/ENAC-IT4R/2024/equipment'))).toBe(
    '/en/_/2024/equipment',
  );
});

test('masks record ids — plan and simulation addresses', () => {
  expect(
    buildTrackedUrl(resolve('/fr/ENAC-IT4R/2024/simulation/plan/42')),
  ).toBe('/fr/_/2024/simulation/plan/_');
});

test('a record id equal to an allow-listed value does not mask the year', () => {
  // Positional masking, not value comparison: planId=2024 alongside year=2024
  // must blank the id and keep the year.
  expect(
    buildTrackedUrl(resolve('/en/ENAC-IT4R/2024/simulation/plan/2024')),
  ).toBe('/en/_/2024/simulation/plan/_');
});

test('masks a unit that needs percent-encoding', () => {
  // `route.path` stays encoded while `route.params` is decoded, so comparing
  // the two would leak this unit.
  const tracked = buildTrackedUrl(resolve('/en/ENAC IT4R/2024/results'));
  expect(tracked).toBe('/en/_/2024/results');
  expect(tracked).not.toContain('%20');
  expect(tracked).not.toContain('IT4R');
});

test('masks the tail of an unmatched path (fails safe)', () => {
  expect(buildTrackedUrl(resolve('/en/ENAC-IT4R/2024/typo/deep'))).toBe(
    '/_/_/_/_/_',
  );
});

test('drops query strings by reading the path only', () => {
  expect(
    buildTrackedUrl(resolve('/en/back-office/reporting?token=secret')),
  ).toBe('/en/back-office/reporting');
});

test('keeps print routes distinguishable while still masking the unit', () => {
  expect(buildTrackedUrl(resolve('/en/ENAC-IT4R/2024/results/print'))).toBe(
    '/en/_/2024/results/print',
  );
});

test('title is the route name, and falls back to the masked url', () => {
  expect(buildTrackedTitle(resolve('/en/ENAC-IT4R/2024/results'))).toBe(
    'results',
  );
  const unnamed = { ...resolve('/en/ENAC-IT4R/2024/results'), name: undefined };
  expect(buildTrackedTitle(unnamed)).toBe('/en/_/2024/results');
});
