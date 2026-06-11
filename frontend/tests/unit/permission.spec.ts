/**
 * Regression test for ``hasBackOfficeAreaPermission`` — the helper that
 * gates the back-office entry button in ``Co2Header.vue``.
 *
 * The bug it pins (#459 follow-up): after the backend started emitting
 * affiliation-scoped keys (``backoffice.users/<aff>`` instead of bare
 * ``backoffice.users``), gating on ``hasUserPermission('backoffice.users',
 * 'view')`` hid the button for ACCRED sub-perimeter users — even though
 * they hold full backoffice grants on their affiliation. This helper
 * accepts bare keys (Super Admin / GlobalScope) and affiliation-scoped
 * ``backoffice.<page>/<aff>`` keys.
 */

import { test, expect } from '@playwright/test';

import {
  hasAnyScopePermission,
  hasBackOfficeAreaPermission,
  hasUnitScopePermission,
} from '../../src/utils/permission';
import { PermissionAction } from '../../src/constant/permissions';

test('affiliation-scoped backoffice key grants access', () => {
  const perms = {
    'backoffice.users/ENAC-SG': ['view', 'edit', 'export'],
    'backoffice.reporting/ENAC-SG': ['view', 'export'],
  } as never;
  expect(hasBackOfficeAreaPermission(perms, PermissionAction.VIEW)).toBe(true);
});

test('bare backoffice key grants access (GlobalScope users)', () => {
  const perms = {
    'backoffice.users': ['view', 'edit', 'export'],
  } as never;
  expect(hasBackOfficeAreaPermission(perms, PermissionAction.VIEW)).toBe(true);
});

test('reporting-only scoped user can still enter back-office', () => {
  const perms = {
    'backoffice.reporting/SV': ['view'],
  } as never;
  expect(hasBackOfficeAreaPermission(perms, PermissionAction.VIEW)).toBe(true);
});

test('action mismatch returns false (edit-only key, asking view)', () => {
  const perms = {
    'backoffice.users': ['edit'],
  } as never;
  expect(hasBackOfficeAreaPermission(perms, PermissionAction.VIEW)).toBe(false);
});

test('module-only user (principal/std) has no back-office access', () => {
  const perms = {
    'modules.headcount/0184': ['view', 'edit'],
    'modules.professional_travel/0184': ['view', 'edit'],
  } as never;
  expect(hasBackOfficeAreaPermission(perms, PermissionAction.VIEW)).toBe(false);
});

test('null/undefined permissions returns false', () => {
  expect(hasBackOfficeAreaPermission(null, PermissionAction.VIEW)).toBe(false);
  expect(hasBackOfficeAreaPermission(undefined, PermissionAction.VIEW)).toBe(
    false,
  );
});

// hasAnyScopePermission — path-specific scope fallback, used by router
// guards and the sidebar's edit-permission check. Pin both that scoped
// keys count AND that path isolation holds (don't match foreign paths).

test('hasAnyScopePermission: affiliation-scoped edit grants edit', () => {
  const perms = {
    'backoffice.users/ENAC-SG': ['view', 'edit', 'export'],
  } as never;
  expect(
    hasAnyScopePermission(perms, 'backoffice.users', PermissionAction.EDIT),
  ).toBe(true);
});

test('hasAnyScopePermission: bare path edit grants edit (GlobalScope)', () => {
  const perms = {
    'backoffice.users': ['view', 'edit'],
  } as never;
  expect(
    hasAnyScopePermission(perms, 'backoffice.users', PermissionAction.EDIT),
  ).toBe(true);
});

test('hasAnyScopePermission: path isolation — module key does NOT match backoffice path', () => {
  const perms = {
    'modules.headcount/0184': ['view', 'edit'],
  } as never;
  expect(
    hasAnyScopePermission(perms, 'backoffice.users', PermissionAction.EDIT),
  ).toBe(false);
});

test('hasAnyScopePermission: prefix isolation — backoffice.users does NOT match backoffice.users_other', () => {
  // Guards against an accidental `key.startsWith(path)` (without the `/`)
  // that would let a sibling path slip past.
  const perms = {
    'backoffice.users_other/ENAC-SG': ['edit'],
  } as never;
  expect(
    hasAnyScopePermission(perms, 'backoffice.users', PermissionAction.EDIT),
  ).toBe(false);
});

// hasUnitScopePermission — gates unit-level controls (e.g. validating a
// module's status). With an institutionalId it must match ONLY the selected
// workspace's unit key (or a global key), never a foreign unit and never the
// own-scoped (`/own`) variant.

test('hasUnitScopePermission: cross-unit leak — principal in 0184 has NO unit scope while viewing 9999', () => {
  // Regression for the bug where the bare path matched any `modules.X/<unit>`
  // key, leaking unit-level controls across workspaces.
  const perms = {
    'modules.headcount/0184': ['view', 'edit', 'sync'],
  } as never;
  expect(
    hasUnitScopePermission(
      perms,
      'modules.headcount',
      PermissionAction.EDIT,
      '9999',
    ),
  ).toBe(false);
});

test('hasUnitScopePermission: principal in selected unit has unit scope', () => {
  const perms = {
    'modules.headcount/0184': ['view', 'edit', 'sync'],
  } as never;
  expect(
    hasUnitScopePermission(
      perms,
      'modules.headcount',
      PermissionAction.EDIT,
      '0184',
    ),
  ).toBe(true);
});

test('hasUnitScopePermission: own-scoped key does NOT grant unit scope', () => {
  const perms = {
    'modules.professional_travel/0184/own': ['view', 'edit'],
  } as never;
  expect(
    hasUnitScopePermission(
      perms,
      'modules.professional_travel',
      PermissionAction.EDIT,
      '0184',
    ),
  ).toBe(false);
});

test('hasUnitScopePermission: global (bare) key grants unit scope for any unit', () => {
  const perms = {
    'modules.headcount': ['view', 'edit'],
  } as never;
  expect(
    hasUnitScopePermission(
      perms,
      'modules.headcount',
      PermissionAction.EDIT,
      '0184',
    ),
  ).toBe(true);
});
