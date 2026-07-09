/**
 * Regression test for #1382 — a standard user lands on "403 Unauthorized
 * Access" by clicking the home "start" button, or the prev/next module arrows
 * at the bottom of a module page (Equipment from External Cloud & AI, Purchase
 * from Professional travel).
 *
 * Root cause: the nav surfaces filtered on ``canUserAccessModule``, which used
 * ``hasAnyScopePermission`` — it matches a grant held in ANY unit and accepts
 * view OR edit. ``permissionGuard`` meanwhile required workspace-scoped view
 * AND edit. A user who is standard (own-scoped) in the selected unit but holds
 * a grant on, say, Equipment in some other unit therefore saw the Equipment
 * arrow, and the guard bounced them to ``/unauthorized`` on click.
 *
 * The fix makes ``canAccessModule`` the single predicate behind both the guard
 * and the nav surfaces. These tests pin it against the backend's actual grants
 * (``calculate_user_permissions`` in ``backend/app/models/user.py``): a
 * standard user receives only ``modules.professional_travel/<unit>/own`` and
 * ``modules.external_cloud_and_ai/<unit>/own``.
 */

import { test, expect } from '@playwright/test';

import { MODULES } from '../../src/constant/modules';
import {
  canAccessModule,
  type FlatUserPermissions,
} from '../../src/utils/permission';

const UNIT = '0184';
const OTHER_UNIT = '9999';

/** What `CO2_USER_STD` actually receives for `UNIT`. */
const STANDARD_USER = {
  [`modules.professional_travel/${UNIT}/own`]: ['view', 'edit'],
  [`modules.external_cloud_and_ai/${UNIT}/own`]: ['view', 'edit'],
} as unknown as FlatUserPermissions;

/** What `CO2_USER_PRINCIPAL` receives for `UNIT`. */
const PRINCIPAL_USER = {
  [`modules.headcount/${UNIT}`]: ['view', 'edit', 'sync'],
  [`modules.equipment/${UNIT}`]: ['view', 'edit', 'sync'],
  [`modules.professional_travel/${UNIT}`]: ['view', 'edit', 'sync'],
  [`modules.external_cloud_and_ai/${UNIT}`]: ['view', 'edit', 'sync'],
  [`module.status/${UNIT}`]: ['edit'],
} as unknown as FlatUserPermissions;

test('standard user reaches exactly the two own-scoped modules', () => {
  expect(canAccessModule(STANDARD_USER, MODULES.ExternalCloudAndAI, UNIT)).toBe(
    true,
  );
  expect(canAccessModule(STANDARD_USER, MODULES.ProfessionalTravel, UNIT)).toBe(
    true,
  );
});

test('standard user cannot reach the modules the arrows used to point at', () => {
  // Equipment sits just before External Cloud & AI in `MODULES_ORDER`, and
  // Purchase just after Professional travel — the two arrows from the issue.
  expect(canAccessModule(STANDARD_USER, MODULES.Equipment, UNIT)).toBe(false);
  expect(canAccessModule(STANDARD_USER, MODULES.Purchase, UNIT)).toBe(false);
  // Headcount is first in `MODULES_ORDER`: where the "start" button pointed.
  expect(canAccessModule(STANDARD_USER, MODULES.Headcount, UNIT)).toBe(false);
});

test('a grant in another unit does not unlock the module in this one', () => {
  // The assertion the old `hasAnyScopePermission` implementation failed.
  const crossUnit = {
    ...STANDARD_USER,
    [`modules.equipment/${OTHER_UNIT}`]: ['view', 'edit', 'sync'],
  } as unknown as FlatUserPermissions;

  expect(canAccessModule(crossUnit, MODULES.Equipment, UNIT)).toBe(false);
  expect(canAccessModule(crossUnit, MODULES.Equipment, OTHER_UNIT)).toBe(true);
});

test('principal reaches every module granted on the selected unit', () => {
  expect(canAccessModule(PRINCIPAL_USER, MODULES.Headcount, UNIT)).toBe(true);
  expect(canAccessModule(PRINCIPAL_USER, MODULES.Equipment, UNIT)).toBe(true);
  expect(
    canAccessModule(PRINCIPAL_USER, MODULES.ProfessionalTravel, UNIT),
  ).toBe(true);
  // Not granted at all — no `modules.purchase` key in this fixture.
  expect(canAccessModule(PRINCIPAL_USER, MODULES.Purchase, UNIT)).toBe(false);
});

test('view without edit is not enough — module pages are data entry', () => {
  const viewOnly = {
    [`modules.equipment/${UNIT}`]: ['view'],
  } as unknown as FlatUserPermissions;
  expect(canAccessModule(viewOnly, MODULES.Equipment, UNIT)).toBe(false);
});

test('a global (bare) grant reaches the module in any unit', () => {
  const global = {
    'modules.equipment': ['view', 'edit'],
  } as unknown as FlatUserPermissions;
  expect(canAccessModule(global, MODULES.Equipment, UNIT)).toBe(true);
  expect(canAccessModule(global, MODULES.Equipment, undefined)).toBe(true);
});

test('no selected unit means no unit-scoped access', () => {
  expect(
    canAccessModule(STANDARD_USER, MODULES.ProfessionalTravel, undefined),
  ).toBe(false);
});

test('modules with no permission path are unreachable, not public', () => {
  // `Commuting` maps to `null` in `getModulePermissionPath`; the guard denies
  // it, so the nav must not offer it either.
  expect(canAccessModule(PRINCIPAL_USER, MODULES.Commuting, UNIT)).toBe(false);
});

test('null/undefined permissions deny everything', () => {
  expect(canAccessModule(null, MODULES.ProfessionalTravel, UNIT)).toBe(false);
  expect(canAccessModule(undefined, MODULES.ProfessionalTravel, UNIT)).toBe(
    false,
  );
});
