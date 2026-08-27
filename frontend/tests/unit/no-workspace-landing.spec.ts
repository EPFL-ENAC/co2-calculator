/**
 * Tests for the "no workspace" landing behaviour (no assigned unit, or no
 * globally-open reporting year).
 *
 * When the landing-route resolver can't resolve a workspace, users are sent to
 * /unauthorized tagged with the `reason` so the page can explain the situation
 * rather than showing a bare 403 — and, for back-office users, offer an escape
 * button to the back-office. These pin the pure decisions behind that
 * behaviour.
 */

import { test, expect } from '@playwright/test';

import { UNAUTHORIZED_ROUTE_NAME } from '../../src/router/routeNames';
import {
  resolveNoWorkspaceRoute,
  unauthorizedReasonMessageKey,
} from '../../src/utils/unauthorized';

test('no-workspace states resolve to the unauthorized page tagged with the reason', () => {
  // /unauthorized is a top-level route, so no language param is needed. The
  // reason distinction matters downstream: `no-unit` means this account has no
  // unit (e.g. a student), `no-open-year` means an admin must open a year.
  expect(resolveNoWorkspaceRoute('no-unit')).toEqual({
    name: UNAUTHORIZED_ROUTE_NAME,
    query: { reason: 'no-unit' },
  });
  expect(resolveNoWorkspaceRoute('no-open-year')).toEqual({
    name: UNAUTHORIZED_ROUTE_NAME,
    query: { reason: 'no-open-year' },
  });
});

test('known reasons map to their message keys', () => {
  expect(unauthorizedReasonMessageKey('no-unit')).toBe(
    'unauthorized_no_unit_message',
  );
  expect(unauthorizedReasonMessageKey('no-open-year')).toBe(
    'unauthorized_no_open_year_message',
  );
});

test('absent or unknown reason yields no highlighted message', () => {
  expect(unauthorizedReasonMessageKey(null)).toBeNull();
  expect(unauthorizedReasonMessageKey('something-else')).toBeNull();
});
