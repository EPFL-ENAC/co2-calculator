/**
 * src/router/retryableImport.ts: one download for every caller, and a failed
 * download is tried again by the next caller (a stale rejection used to fail
 * the logout navigation, #3244).
 */
import { test, expect } from 'playwright/test';

import { retryableImport } from '../../src/router/retryableImport';

test('shares one download between callers', async () => {
  let calls = 0;
  const lazy = retryableImport(async () => ++calls);
  lazy.preload();
  expect(await lazy.get()).toBe(1);
  expect(await lazy.get()).toBe(1);
  expect(calls).toBe(1);
});

test('downloads again after a failure', async () => {
  let calls = 0;
  const lazy = retryableImport(async () => {
    calls += 1;
    if (calls === 1) throw new Error('chunk failed');
    return calls;
  });
  lazy.preload();
  await expect(lazy.get()).rejects.toThrow('chunk failed');
  expect(await lazy.get()).toBe(2);
});

test('a failed preload alone raises no unhandled rejection', async () => {
  const lazy = retryableImport(() => Promise.reject(new Error('offline')));
  const unhandled: unknown[] = [];
  const listener = (reason: unknown) => unhandled.push(reason);
  process.on('unhandledRejection', listener);
  lazy.preload();
  await new Promise((resolve) => setTimeout(resolve, 10));
  process.off('unhandledRejection', listener);
  expect(unhandled).toEqual([]);
});
