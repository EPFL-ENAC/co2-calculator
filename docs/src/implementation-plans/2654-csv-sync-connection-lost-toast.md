---
status: delivered
issue: 2654
last_updated: 2026-09-03
title: "SSE streams pinned one DB connection each; the 'connection lost' toast was the pool timing out"
summary: "Both job/pipeline SSE endpoints authenticated through get_current_user, whose get_db session FastAPI releases only after the response is fully sent. For a stream that is its end, so every open stream held a pooled connection in an open transaction until the job finished. On stage the pod cap (2+15) filled, new stream requests timed out after 5 s, and the browser reported 'Connection to sync job lost'. The streams now resolve the user in a short-lived session."
---

# SSE streams pinned one DB connection each

## Symptom

Uploading a scientific-equipment CSV in the Calculator purchase module on
stage showed the red toast "Connection to sync job lost. Please refresh to
check status." although the import completed (#2654).

## What actually happened

2026-09-03 11:03, stage (`svc1751t-co2-calculator-stage`): backend pod
`jfdg5` reached 17 `checked_out` connections, its hard cap
(`DB_POOL_SIZE=2` + `DB_MAX_OVERFLOW=15`, all envs since 2026-09-01). Tempo
listed 26 `GET /v1/sync/pipelines/{id}/stream` requests all ending at
5.0x s with

```
QueuePool limit of size 2 overflow 15 reached, connection timed out, timeout 5.00
```

(traces `05db09492de3ff87d70877410300b3ce`,
`5d7168d029e0d4a4108c39c04f8c662f`). Postgres itself peaked around 45 of
`max_connections=100`; the squeeze was per pod, not the server.

## Root cause

`job_stream_by_id` and `pipeline_stream_by_id`
(`backend/app/api/v1/data_sync.py`) took their user from
`get_current_user`, which takes `db: AsyncSession = Depends(get_db)`.
`get_db` is a `yield` dependency. Since FastAPI 0.118 a `yield` dependency
without an explicit `scope` is scope `request`
(`fastapi/dependencies/models.py`, `_get_computed_scope`), and that stack
exits only after `await response(...)` returns (`fastapi/routing.py`,
`request_response`). For a `StreamingResponse` that is the end of the
stream. We run 0.141.1.

So every open SSE stream held one pooled connection for its whole life, in
the transaction the `SELECT users` had autobegun: one Postgres backend
`idle in transaction` for as long as the job ran. The per-poll
`SessionLocal()` inside the generators (added earlier for the same reason)
only freed the generator's own session; the auth session was left behind.
Each pool timeout returned a 500, the browser's `EventSource` retried
~3 s later and burned another 5 s wait, hence the 26-row storm.

The first trace shows it: two checkouts succeed (auth, then the up-front
jobs check), the third (first poll) times out while the auth one is still
held.

## Fix

- `get_current_user_detached` (`backend/app/core/security.py`): same JWT
  resolution, in its own `async with SessionLocal()` block, no `yield`. The
  returned `User` is detached; the connection is back in the pool before
  the stream opens.
- Both stream endpoints depend on it. `pipeline_stream_by_id` keeps the
  `require_module_or_config_view` rule as an inline `can_view_module_flow`
  check, the way `job_stream_by_id` already did.
- Integration tests that reach the streams over HTTP override the new
  dependency next to `get_current_user`.

A stream now costs one connection for a few milliseconds every 2 s.

## Rejected

- **Swallowing transient `EventSource` errors in the frontend** (first cut
  of this branch, reverted): it hid the 500 and left the pinned connections.
- **`DB_MAX_OVERFLOW` 15 → 50 or `-1`**: moves the failure from a 5 s 500
  on one pod to Postgres/PgBouncer refusing connections for every pod
  (SQLSTATE 53300). Pinned sessions in an open transaction also defeat
  PgBouncer transaction pooling, so the pool would have filled at the same
  rate.
- **Raising `DB_POOL_TIMEOUT`**: streams last minutes, a longer wait only
  delays the same failure.

## Revisit

Any other `StreamingResponse`/`FileResponse` endpoint on `get_current_user`
has the same pin for the length of the download. Pool sizing (2+15 vs a
`pool_size` nearer steady state) is worth a look once a week of stage data
with this fix exists.
