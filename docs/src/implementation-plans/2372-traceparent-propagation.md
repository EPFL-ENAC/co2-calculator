---
status: delivered
issue: 2372
last_updated: 2026-08-26
title: "Propagate W3C traceparent from frontend API calls"
summary: "Stamp a traceparent header on every ky /api request so backend OTel spans join the browser's per-navigation trace id, making GlitchTip trace_ids searchable in Tempo."
---

# Propagate W3C traceparent from frontend API calls

## Problem

Frontend error events in GlitchTip carry a `trace_id` (rotated per navigation
by `frontend/src/utils/glitchtip.ts`), but that id never left the browser —
API requests carried no `traceparent` header, so the backend OTel SDK started
unrelated root traces. A GlitchTip trace id was un-searchable in Tempo
(confirmed during the #2360 investigation: `Not Found`).

## Fix

Two touch points, no new dependency:

1. **`frontend/src/utils/glitchtip.ts`** — export `traceparent()`, returning
   `00-<traceId>-<freshSpanId>-01` from the existing per-navigation `traceId`
   and `randomHex()`. The trace id is stable until `startNavigationTrace()`
   rotates it; the span id is fresh per call, as W3C tracecontext requires.
2. **`frontend/src/api/http.ts`** — a ky `beforeRequest` hook sets the
   `traceparent` header on every request through the centralized client.

FastAPI's OTel instrumentation extracts W3C tracecontext by default, so
backend server spans join the browser's trace id — any GlitchTip event's
trace_id now returns the backend spans of that navigation in Tempo.

No import cycle: `http.ts` already imported `captureError` from
`glitchtip.ts`, and `glitchtip.ts` imports nothing from the api layer.

## Out of scope

Sentry-native `sentry-trace`/`baggage` headers and any OTel browser SDK
(full RUM) — deliberately parked as issue #2373.

## Test

`frontend/tests/unit/traceparent.spec.ts` (Playwright, `npm run test-ct`):

- `traceparent()` matches `/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/`;
- trace id stable across calls, span id fresh per call;
- `startNavigationTrace()` rotates the trace id.

Header presence on a live request is not asserted: `tests/unit` specs are
node-side function tests (no app mount, no route interception), and importing
`http.ts` drags in Quasar/i18n boot. Covered implicitly by any e2e run.
