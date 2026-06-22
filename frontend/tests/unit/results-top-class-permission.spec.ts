/**
 * Regression test for #1596 — standard users get a 403 "Unauthorized Access"
 * redirect on the Results page.
 *
 * Root cause: when a category is expanded on Results, ``ModuleCharts`` eagerly
 * fetches the per-module ``top-class-breakdown`` for the three top-class modules
 * (Equipment, Purchase, Research facilities). That endpoint is permission-gated
 * (``modules.<type>.view``); a standard user lacks ``view`` on those modules, so
 * the call 403s and the global HTTP hook bounces the whole page to
 * ``/unauthorized``.
 *
 * The fix guards the call with ``authStore.hasUserModulePermission(type, VIEW)``
 * (``stores/auth.ts``), which resolves the workspace-scoped permission. This
 * test pins that decision: standard users must resolve to "no view" on the
 * top-class modules (→ call skipped), while principals resolve to "view"
 * (→ call proceeds). It also pins that own-scoped modules a standard user *can*
 * view are never fetched anyway because they are not top-class.
 */

import { test, expect } from '@playwright/test';

import { MODULES, type Module } from '../../src/constant/modules';
import {
  getModulePermissionPath,
  hasPermission,
  PermissionAction,
  type FlatUserPermissions,
} from '../../src/utils/permission';

/** Mirrors ``TOP_CLASS_MODULES`` in ``ModuleCharts.vue``. */
const TOP_CLASS_MODULES: Module[] = [
  MODULES.Equipment,
  MODULES.Purchase,
  MODULES.ResearchFacilities,
];

/**
 * Mirrors ``hasUserPermission`` in ``stores/auth.ts``: a bare/global grant, OR
 * the unit-scoped key (principal), OR the own-scoped key (standard user).
 */
function canViewModuleForUnit(
  perms: FlatUserPermissions,
  module: Module,
  institutionalId: string,
): boolean {
  const path = getModulePermissionPath(module);
  if (!path) return false;
  const unitPath = `${path}/${institutionalId}`;
  return (
    hasPermission(perms, path, PermissionAction.VIEW) ||
    hasPermission(perms, unitPath, PermissionAction.VIEW) ||
    hasPermission(perms, `${unitPath}/own`, PermissionAction.VIEW)
  );
}

/** The guard added to ``fetchTopClassBreakdownIfNeeded`` in ``ModuleCharts.vue``. */
function shouldFetchTopClassBreakdown(
  perms: FlatUserPermissions,
  module: Module,
  institutionalId: string,
): boolean {
  return (
    TOP_CLASS_MODULES.includes(module) &&
    canViewModuleForUnit(perms, module, institutionalId)
  );
}

const INST = '0184';

// A standard user: own-scoped grants on travel + external cloud/AI only.
// Critically, NO purchase/equipment/research_facilities keys of any scope.
const STANDARD_USER: FlatUserPermissions = {
  'modules.professional_travel/0184/own': ['view', 'edit'],
  'modules.external_cloud_and_ai/0184/own': ['view', 'edit'],
} as never;

// A principal (unit manager): unit-scoped view on every module.
const PRINCIPAL: FlatUserPermissions = {
  'modules.equipment/0184': ['view', 'edit'],
  'modules.purchase/0184': ['view', 'edit'],
  'modules.research_facilities/0184': ['view', 'edit'],
  'modules.external_cloud_and_ai/0184': ['view', 'edit'],
} as never;

for (const module of TOP_CLASS_MODULES) {
  test(`#1596: standard user does NOT fetch top-class breakdown for ${module}`, () => {
    expect(shouldFetchTopClassBreakdown(STANDARD_USER, module, INST)).toBe(
      false,
    );
  });

  test(`principal DOES fetch top-class breakdown for ${module}`, () => {
    expect(shouldFetchTopClassBreakdown(PRINCIPAL, module, INST)).toBe(true);
  });
}

test('own-scoped module a standard user can view is still not fetched (not top-class)', () => {
  // The standard user holds `external_cloud_and_ai/own` view, so the scope
  // check passes — but the module is not top-class, so no gated call is made.
  expect(
    canViewModuleForUnit(STANDARD_USER, MODULES.ExternalCloudAndAI, INST),
  ).toBe(true);
  expect(
    shouldFetchTopClassBreakdown(
      STANDARD_USER,
      MODULES.ExternalCloudAndAI,
      INST,
    ),
  ).toBe(false);
});

test('non-top-class module never triggers a fetch even for a principal', () => {
  expect(shouldFetchTopClassBreakdown(PRINCIPAL, MODULES.Headcount, INST)).toBe(
    false,
  );
});
