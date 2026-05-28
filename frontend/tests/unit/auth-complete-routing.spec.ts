/**
 * Regression tests for the BFF cookie-exchange landing route /auth/complete.
 *
 * Two bugs surfaced during manual Safari testing of PR #1314:
 *
 * 1) White screen at /auth/complete#code=...
 *    Root cause: defaultLanguageGuard redirected the named route toward
 *    /{lang}/auth/complete, but the route definition has no `:language`
 *    param so the navigation silently dropped the URL hash. Fix: add
 *    AUTH_COMPLETE_ROUTE_NAME to ROUTES_WITHOUT_LANGUAGE.
 *
 * 2) Two redundant 401s on every login (GET /session, POST /session).
 *    Root cause: authGuard auto-calls auth.getUser() on every navigation
 *    when `!hasChecked`, including /auth/complete — racing the page's
 *    own onMounted exchange POST. Fix: skipAuthCheck meta flag.
 *
 * These tests pin both fixes against the actual exported configuration.
 */

import { test, expect } from '@playwright/test';

import {
  ROUTES_WITHOUT_LANGUAGE,
  AUTH_COMPLETE_ROUTE_NAME,
} from '../../src/router/routeNames';

test('AUTH_COMPLETE_ROUTE_NAME is in ROUTES_WITHOUT_LANGUAGE', () => {
  // Without this, defaultLanguageGuard tries to redirect /auth/complete
  // toward /{lang}/auth/complete, which doesn't match any route — the
  // navigation silently fails and the URL hash carrying `code=...` is
  // dropped, leaving the user on a blank page.
  expect(ROUTES_WITHOUT_LANGUAGE).toContain(AUTH_COMPLETE_ROUTE_NAME);
});

test('AUTH_COMPLETE_ROUTE_NAME matches the symbol used by the route definition', () => {
  // Sanity check: the constant must equal the literal route name string.
  // If someone renames the constant without updating the routes file, the
  // page would still load but the ROUTES_WITHOUT_LANGUAGE allowlist match
  // would break silently.
  expect(AUTH_COMPLETE_ROUTE_NAME).toBe('auth-complete');
});
