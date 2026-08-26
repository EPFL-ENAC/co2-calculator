/**
 * Regression test for #2369 — a global-scope role (e.g. superadmin) opening a
 * workspace URL for a unit outside their membership list was silently
 * redirected to the landing resolver.
 *
 * Root cause: ``validateUnit()`` in ``router/guards/validateUnitGuard.ts``
 * authorized client-side by only accepting units present in the
 * membership-scoped ``GET users/units`` response, violating the invariant
 * "frontend never checks roles — the backend decides".
 *
 * The fix routes the decision through ``resolveWorkspaceUnit``: the
 * membership list is a fast path, and any other unit id is fetched from the
 * backend (``GET units/{id}``, policy-authorized in ``UnitService.get_by_id``)
 * — a unit on 200 means proceed, null (403/404) keeps the redirect.
 *
 * Pure leaf helper + injected ``fetchUnit`` so this runs node-side under
 * Playwright without the Pinia/i18n boot chain (no Vitest in this repo).
 */

import { test, expect } from '@playwright/test';

import { resolveWorkspaceUnit } from '../../src/utils/resolveWorkspaceUnit';

const memberUnits = [
  { id: 101, name: '101-own-lab' },
  { id: 102, name: '102-other-member-lab' },
];

function backendStub(allowed: Record<number, { id: number; name: string }>) {
  const calls: number[] = [];
  return {
    calls,
    fetchUnit: async (id: number) => {
      calls.push(id);
      return allowed[id] ?? null;
    },
  };
}

test('member unit resolves from the list without asking the backend', async () => {
  const backend = backendStub({});
  const unit = await resolveWorkspaceUnit(
    '101-own-lab',
    memberUnits,
    backend.fetchUnit,
  );
  expect(unit).toEqual({ id: 101, name: '101-own-lab' });
  expect(backend.calls).toEqual([]);
});

test('non-member unit allowed by the backend resolves (the reported bug)', async () => {
  // Global-scope user: unit 455 is not in their membership list, but the
  // backend authorizes the read. Before the fix this resolved to null and
  // bounced the user to their own unit.
  const backend = backendStub({ 455: { id: 455, name: '455-durabilite' } });
  const unit = await resolveWorkspaceUnit(
    '455-durabilite',
    memberUnits,
    backend.fetchUnit,
  );
  expect(unit).toEqual({ id: 455, name: '455-durabilite' });
  expect(backend.calls).toEqual([455]);
});

test('non-member unit refused by the backend (403/404) still redirects', async () => {
  const backend = backendStub({});
  const unit = await resolveWorkspaceUnit(
    '455-durabilite',
    memberUnits,
    backend.fetchUnit,
  );
  expect(unit).toBeNull();
  expect(backend.calls).toEqual([455]);
});

test('unparsable unit param never reaches the backend', async () => {
  const backend = backendStub({});
  const unit = await resolveWorkspaceUnit(
    'not-a-unit-id',
    memberUnits,
    backend.fetchUnit,
  );
  expect(unit).toBeNull();
  expect(backend.calls).toEqual([]);
});

test('exact name match still resolves from the list (legacy route form)', async () => {
  const backend = backendStub({});
  const unit = await resolveWorkspaceUnit(
    '102-other-member-lab',
    memberUnits,
    backend.fetchUnit,
  );
  expect(unit).toEqual({ id: 102, name: '102-other-member-lab' });
  expect(backend.calls).toEqual([]);
});
