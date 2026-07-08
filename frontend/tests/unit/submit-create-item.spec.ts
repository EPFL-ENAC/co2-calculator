/**
 * Regression test for #1463 — Buildings room-add disclaimer firing
 * inconsistently.
 *
 * `moduleStore.postItem` does the create POST, then chains unrelated
 * follow-up refreshes (totals, submodule data, breakdown, module states).
 * If the create POST succeeded but a trailing refresh rejected, the whole
 * call rejected too, and `SubModuleSection.vue`'s `submitForm` swallowed
 * that into a form-field error on `user_institutional_id` — a field that
 * doesn't even exist on the rooms form — so neither the disclaimer nor any
 * visible error appeared, even though the room had been created.
 *
 * `submitCreateItem` isolates the create-vs-refresh distinction so it can
 * be exercised without a browser/store: `onCreated` must fire whenever the
 * create call itself succeeds, regardless of what happens afterwards, and
 * `onCreateFailed` (the form-field-error path) must fire only when the
 * create call itself never succeeded.
 */

import { test, expect } from '@playwright/test';

import {
  submitCreateItem,
  type SubmitCreateItemActions,
} from '../../src/utils/submitCreateItem';

function trackedActions(): SubmitCreateItemActions & {
  calls: string[];
} {
  const calls: string[] = [];
  return {
    calls,
    onCreated: () => calls.push('created'),
    onRefreshFailed: () => calls.push('refreshFailed'),
    onCreateFailed: () => calls.push('createFailed'),
  };
}

test('fires onCreated and nothing else when create and refresh both succeed', async () => {
  const actions = trackedActions();

  await submitCreateItem(async (onCreated) => {
    onCreated();
    // trailing refresh chain succeeds
  }, actions);

  expect(actions.calls).toEqual(['created']);
});

test('still fires onCreated when a trailing refresh fails after a successful create (#1463)', async () => {
  const actions = trackedActions();

  await submitCreateItem(async (onCreated) => {
    onCreated();
    // trailing refresh chain (totals/breakdown/states) rejects, mirroring
    // postItem's single try/catch around the create + refresh chain.
    throw new Error('getModuleTotals failed');
  }, actions);

  // The disclaimer must have fired even though the overall call rejected,
  // and the failure must be reported as a refresh failure, not misdirected
  // to the create-error (form-field-error) path.
  expect(actions.calls).toEqual(['created', 'refreshFailed']);
});

test('does not fire onCreated when the create call itself fails', async () => {
  const actions = trackedActions();

  await submitCreateItem(async () => {
    // create POST itself rejects — onCreated is never invoked.
    throw new Error('DUPLICATE_INSTITUTIONAL_ID');
  }, actions);

  expect(actions.calls).toEqual(['createFailed']);
});
