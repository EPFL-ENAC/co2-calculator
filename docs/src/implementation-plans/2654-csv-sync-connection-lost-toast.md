---
status: delivered
issue: 2654
last_updated: 2026-09-03
title: "Stop reporting transient job-stream drops as 'connection lost'"
summary: "The per-job SSE subscriber tore the stream down and toasted 'Connection to sync job lost' on every EventSource error, including the transient drops the browser retries on its own. Only a fatal close or a sustained outage now counts as lost."
---

# Stop reporting transient job-stream drops as "connection lost"

## Problem

Uploading a scientific-equipment CSV in the Calculator purchase module showed
the red toast "Connection to sync job lost. Please refresh to check status."
although the import completed normally (#2654).

`subscribeToJobUpdates` in `frontend/src/stores/backofficeDataManagement.ts`
handled `EventSource.onerror` by closing the socket and calling the caller's
`onError` callback unconditionally. Per the WHATWG spec, `error` fires on every
transient drop (proxy cut, network blip, server closing the socket) with
`readyState === CONNECTING` while the browser reconnects by itself; only a
non-200 response or a bad content-type leaves the source `CLOSED`. Closing on
the first transient error killed the native retry, so the job's terminal
message never reached the client: the completion toast and table refresh did
not fire, and the user saw "connection lost" instead.

The backend endpoint (`job_stream_by_id` in `backend/app/api/v1/data_sync.py`)
already replays the current job state on every new connection, so native
retry is enough to recover. The sibling pipeline stream fixed the same bug
earlier; see the "Reconnect strategy" note in
`frontend/src/composables/usePipelineStream.ts`.

## Fix

- `onerror` now ignores errors while `readyState !== CLOSED`, up to
  `MAX_SSE_RECONNECT_ATTEMPTS` (5) consecutive failures; `onopen` resets the
  counter. A fatal close or a sustained outage still tears the stream down
  and calls `onError`, preserving the #1523 guarantee that a backend that is
  really gone surfaces a toast and resets spinners.
- Callers are unchanged: `onError` now means "the stream is really lost".

## Tests

- `frontend/tests/integration/setup/data-management-mocks.ts`:
  `emitError(id, { fatal })` sets `readyState` like the browser does
  (CONNECTING for transient, CLOSED for fatal); `emitOpen(id)` added.
- `frontend/tests/integration/data-management.spec.ts` test 6b: a transient
  error leaves the stream open and shows no toast; a fatal error still shows
  the failure and "connection lost" toasts.
