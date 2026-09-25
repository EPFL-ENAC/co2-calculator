---
status: in-progress
issue: 2956
last_updated: 2026-09-25
title: "SSE streams end cleanly on DB errors"
summary: "Follow-ups from #2946/#2954. A DB error in an SSE stream's poll loop surfaced as Starlette's 'response already started' RuntimeError, with the real error only in __cause__. Both SSE streams now log it and end: the job stream with its existing 'Job not found' event shape, the pipeline stream silently so native EventSource retry reconnects."
---

# SSE streams end cleanly on DB errors

## SSE streams: mid-stream DB errors

### Problem

`job_stream_by_id` and `pipeline_stream_by_id` in `api/v1/data_sync.py` open
a `SessionLocal()` on every poll, after the 200 has been sent. `main.py`
registers `db_unavailable_handler` for `DBAPIError` and SQLAlchemy's pool
`TimeoutError`. Once a response has started, Starlette
(`_exception_handler.py`) re-raises any exception with a registered handler as
`RuntimeError("Caught handled exception, but response already started.")`.
The DB error survived only as `__cause__`, so log queries keyed on
`OperationalError` missed it (plan
[2049](2049-async-db-health-poller.md), last section).

### Decisions

1. **One wrapper, two callers.** `_end_stream_on_db_error` re-yields the
   stream's events and catches `DBAPIError` and the pool `TimeoutError`
   only. It logs the real exception with `exc_info` and the request path,
   then ends the stream. The poll is the only DB access inside either
   generator, so wrapping the generator is the same as catching in the poll
   loop. Any other exception still propagates.
2. **Every `DBAPIError`, not only "unavailable".** The stream has no 503 to
   pick, so it doesn't need `db_unavailable_handler`'s predicate. The
   terminal message therefore says "database error", not "temporarily
   unavailable".
3. **Job stream: the "Job not found" shape.** It emits
   `{"job_id", "status_message": "Job status unavailable: database error"}`
   and returns. `subscribeToJobUpdates` (`stores/backofficeDataManagement.ts`)
   treats neither payload as finished. The server close fires `onerror`,
   which unsubscribes and calls the caller's `onError` ("connection lost").
   A `state: FINISHED, result: ERROR` payload was rejected: it would write a
   fake failed row into `syncJobs` and fire `onFail` for a job that may
   still be running.
4. **Pipeline stream: no event.** Its only terminal shape is a
   `pipeline-update` with `stream_closed: true`, which needs real `jobs` and
   `progress`. Without them it would clobber the store entry.
   `usePipelineStream` relies on native `EventSource` retry. The reconnect
   runs the pre-stream check, so a DB that is still down answers a real 503
   there. Client behaviour matches the aborted connection of before; only
   the log changes.
5. **No frontend change.**

### Found, not fixed

- `ModuleTable.vue` passes no `onError` to `subscribeToJobUpdates`, and
  `useSubmoduleConfig.ts`'s `onError` only resets the spinner. Both were
  already silent when the stream ended on "Job not found".
- No other stream reads the DB after the response starts. The audit
  exports (`api/v1/audit.py`) and the backoffice exports
  (`api/v1/backoffice.py`) build the whole body before responding.
  `report_detailed`'s lazy generator only reads a temporary zip file.

### Tests

`tests/unit/v1/test_data_sync_stream_db_errors.py` drives both generators
with a repository that fails on the second poll:

- job stream, for `OperationalError` and the pool `TimeoutError`: the
  first event is the real state, the second and last is the terminal
  payload, and the log record's `exc_info` holds the raised error;
- pipeline stream: one `pipeline-update`, then the stream ends and the error
  is logged;
- a `ValueError` still propagates.

The first two fail without the fix: the DB error escapes the generator.
