/**
 * Regression test for `pollUntilPrefilled` — the wait behind a deferred
 * plan prefill (backend plan #2050 Track F4).
 *
 * Why this is the load-bearing test: the plan PATCHes now return before the
 * reference year has been copied into the plan years. If this poll returns
 * early, the page refetches empty year sections and renders them as a
 * legitimate zero footprint — a wrong number that looks complete, which is
 * the worst failure this project has. If it never backs off, a multi-minute
 * prefill hammers the API twice a second.
 *
 * Injected `sleep` keeps it a pure function test: no timers, no HTTP.
 */

import { test, expect } from '@playwright/test';

import { pollUntilPrefilled } from '../../src/composables/pollUntilPrefilled';

type Status = { finished: boolean; tag?: string };

/** Returns each status in turn; records the delays it was asked to sleep. */
function harness(statuses: Status[]) {
  const delays: number[] = [];
  let calls = 0;
  return {
    delays,
    get calls() {
      return calls;
    },
    fetchStatus: () => {
      const next = statuses[Math.min(calls, statuses.length - 1)];
      calls += 1;
      return Promise.resolve(next as Status);
    },
    sleep: (ms: number) => {
      delays.push(ms);
      return Promise.resolve();
    },
  };
}

test('returns immediately when the job is already finished', async () => {
  const h = harness([{ finished: true, tag: 'done' }]);

  const result = await pollUntilPrefilled(h.fetchStatus, h.sleep);

  expect(result.tag).toBe('done');
  expect(h.calls).toBe(1);
  expect(h.delays).toEqual([]);
});

test('keeps polling until the job reports finished', async () => {
  const h = harness([
    { finished: false },
    { finished: false },
    { finished: true, tag: 'done' },
  ]);

  const result = await pollUntilPrefilled(h.fetchStatus, h.sleep);

  expect(result.tag).toBe('done');
  expect(h.calls).toBe(3);
  // Slept once after each unfinished poll, never after the last.
  expect(h.delays).toHaveLength(2);
});

test('backs off from 500ms and caps at 3s', async () => {
  const unfinished = Array.from({ length: 12 }, () => ({ finished: false }));
  const h = harness([...unfinished, { finished: true }]);

  await pollUntilPrefilled(h.fetchStatus, h.sleep);

  expect(h.delays[0]).toBe(500);
  expect(h.delays[1]).toBe(750);
  expect(h.delays[2]).toBe(1125);
  // Monotonic, and never above the ceiling — a long prefill must not
  // settle into polling twice a second.
  for (let i = 1; i < h.delays.length; i += 1) {
    expect(h.delays[i]).toBeGreaterThanOrEqual(h.delays[i - 1]!);
  }
  expect(Math.max(...h.delays)).toBe(3000);
});
