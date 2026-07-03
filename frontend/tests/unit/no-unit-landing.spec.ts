/**
 * Tests for the "no assigned unit" landing behaviour.
 *
 * When the landing-route resolver finds the account has no units, users who can
 * reach the back-office configuration (data-management) page are forwarded
 * there, while everyone else — including back-office users WITHOUT configuration
 * access — is sent to /unauthorized tagged with `reason=no-unit` so the page can
 * explain the account is simply not assigned to a unit rather than showing a
 * bare 403. These pin the two pure decisions behind that behaviour.
 */

import { test, expect } from '@playwright/test';

import { UNAUTHORIZED_ROUTE_NAME } from '../../src/router/routeNames';
import { BACKOFFICE_NAV } from '../../src/constant/navigation';
import {
  resolveNoUnitRoute,
  unauthorizedReasonMessageKey,
} from '../../src/utils/unauthorized';

test('users who can access back-office config land there (with language param)', () => {
  // The back-office page is nested under `:language`, so the redirect must
  // carry the language param — otherwise vue-router throws "Missing required
  // param" and renders a blank screen.
  expect(resolveNoUnitRoute(true, 'en')).toEqual({
    name: BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName,
    params: { language: 'en' },
  });
});

test('users without config access get the no-unit unauthorized page', () => {
  // Covers plain users AND back-office users lacking `backoffice.configuration`
  // — both must see the "not assigned to a unit" page, not the config redirect
  // (which permissionGuard would bounce to a generic 403).
  // /unauthorized is a top-level route, so no language param is needed.
  expect(resolveNoUnitRoute(false, 'en')).toEqual({
    name: UNAUTHORIZED_ROUTE_NAME,
    query: { reason: 'no-unit' },
  });
});

test('no-unit reason maps to the not-assigned message key', () => {
  expect(unauthorizedReasonMessageKey('no-unit')).toBe(
    'unauthorized_no_unit_message',
  );
});

test('absent or unknown reason yields no highlighted message', () => {
  expect(unauthorizedReasonMessageKey(null)).toBeNull();
  expect(unauthorizedReasonMessageKey('something-else')).toBeNull();
});
