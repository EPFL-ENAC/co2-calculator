/**
 * Regression test for W3C traceparent propagation (issue #2372).
 *
 * GlitchTip events carry a per-navigation trace_id, but until #2372 that id
 * never left the browser — backend OTel started unrelated root traces, so a
 * GlitchTip trace_id was un-searchable in Tempo. `traceparent()` is the value
 * the ky beforeRequest hook in api/http.ts stamps on every /api call; these
 * tests pin its W3C shape and the trace/span id lifecycle it relies on.
 */

import { test, expect } from '@playwright/test';

import { traceparent, startNavigationTrace } from '../../src/utils/glitchtip';

const TRACEPARENT = /^00-([0-9a-f]{32})-([0-9a-f]{16})-01$/;

function parse(value: string): { traceId: string; spanId: string } {
  const m = value.match(TRACEPARENT);
  if (!m) throw new Error(`not a valid W3C traceparent: ${value}`);
  return { traceId: m[1], spanId: m[2] };
}

test('matches the W3C traceparent format', () => {
  expect(traceparent()).toMatch(TRACEPARENT);
});

test('trace id is stable across calls, span id fresh per call', () => {
  const a = parse(traceparent());
  const b = parse(traceparent());
  expect(b.traceId).toBe(a.traceId);
  expect(b.spanId).not.toBe(a.spanId);
});

test('startNavigationTrace rotates the trace id', () => {
  const before = parse(traceparent()).traceId;
  startNavigationTrace();
  expect(parse(traceparent()).traceId).not.toBe(before);
});
