---
status: delivered
issue: 2572
last_updated: 2026-08-31
title: "Count DB pool timeouts and connection failures instead of inferring them"
summary: "Both DB failure modes were alerted on through gauge thresholds standing in for countable events, so a burst that started and recovered inside the alert window never fired. Two OTel counters make `increase(...) > 0` possible, and DB_POOL_TIMEOUT drops 30 → 5 so a timeout costs a user 5 seconds instead of 30."
---

# Count DB pool timeouts and connection failures instead of inferring them

Follow-up to [#2566](./2566-db-pool-disposal-and-visibility.md) and
EPFL-ENAC/openshift-app-config#30.

## Problem

The two DB failure modes are both alerted on, but only through gauge
thresholds standing in for events that are actually countable:

| failure mode                                 | signal before this change             | gap                                                                      |
| -------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------ |
| QueuePool timeout (pod-local, recoverable)   | `DbPoolSaturationHigh` > 80% for 10m  | a pod can hit 100%, time out real requests and recover inside the window |
| `FATAL: remaining connection slots` (global) | `DbServerConnectionsHigh` > 80 for 2m | dev went 60 → 100 in minutes on 2026-08-31; the burst outran the window  |

`HighErrorRate` is the backstop — both modes end in 500s — but it cannot say
_which_, and on 2026-08-31 that distinction was the whole diagnosis: pod-local
saturation sat at ~20% while the server itself was full.

## Design

### `db.pool.timeouts` — a subclassed pool, not `handle_error`

`handle_error` is the obvious single choke point and **it does not work**. A
`QueuePool` checkout timeout never reaches the DBAPI, so no listener on that
event ever sees one. Verified against a live engine (`pool_size=1,
max_overflow=0, pool_timeout=1`, two concurrent checkouts): `sqlalchemy.exc.TimeoutError`
propagated and the `handle_error` listener recorded nothing.

`InstrumentedQueuePool` subclasses `AsyncAdaptedQueuePool` and counts in
`connect()`. That is the single call every checkout makes, so it is exactly one
increment per timed-out request — unlike `_do_get`, which re-enters itself on
the overflow path and would double-count.

It reaches the engine through `_pool_kwargs`, which already returns `{}` for
sqlite. That is what makes the counter a no-op under `NullPool`/`StaticPool`,
for free and in the same place as the existing guard.

### `db.connect.failures` — `handle_error`, narrowed to `connection is None`

`handle_error` _does_ fire for connect failures, and its `ExceptionContext`
discriminates cleanly. Verified on a live engine:

- connect failure (closed port) → `context.connection is None`
- query error (`select 1/0`) → `context.connection` is the `Connection`

The listener is registered only when the engine is not sqlite, mirroring
`_connect_args` / `_pool_kwargs`.

### The SQLSTATE label is derived from message text, and that is a ceiling

**psycopg exposes no SQLSTATE on connection-_establishment_ errors.** Verified
against a real 53300, forced locally with `create role ... connection limit 1`
and a second login: `err.sqlstate` and `err.diag.sqlstate` are both `None`, and
the `pgconn` handed to the exception is a `FinishedPGconn` carrying only
`error_message` text. libpq has no result object at that point, so there is
nothing else to read. (Query-time errors are unaffected — those carry a real
`sqlstate`, e.g. `22012`.)

So `connect_failure_sqlstate()` prefers a real `sqlstate` when one exists, and
otherwise recognises 53300 from the four messages Postgres uses for it:

- `too many clients already`
- `remaining connection slots are reserved`
- `too many connections for role`
- `too many connections for database`

Anything unrecognised is still counted, labelled `unknown` — the total is what
says "connections are failing", the label only says which kind.

**The ceiling:** this is message matching, so a server running with a
non-English `lc_messages` would label a real 53300 as `unknown`. All three of
our instances are English. If that ever changes, the alert should move to the
unlabelled total.

### `DB_POOL_TIMEOUT` 30 → 5

A pool timeout today means a user watches a spinner for 30 seconds and _then_
gets an error. Five carries the same information at a sixth of the harm, and
surfaces the counter sooner. Under normal load it changes nothing: measured
peak is ~4 `checked_out` per pod against a ceiling of 13 (#2566), so nothing
ever waits.

## Steps

- [x] `InstrumentedQueuePool` + `db.pool.timeouts` counter (`backend/app/db.py`),
      wired through `_pool_kwargs` so sqlite skips it.
- [x] `count_connect_failure` + `db.connect.failures` counter, registered as a
      `handle_error` listener on `engine.sync_engine` for non-sqlite only.
- [x] `connect_failure_sqlstate` with the four 53300 messages and the `unknown`
      bucket.
- [x] `DB_POOL_TIMEOUT` default 30 → 5 (`backend/app/core/config.py`), with
      `backend/.env.example` and the pinned assertion in
      `backend/tests/unit/test_db_pool_settings.py` updated to match.
- [x] Tests in `test_db_pool_settings.py`: a **real** exhausted-pool checkout
      timeout driven through `greenlet_spawn` (the async engine's own wrapper
      around every pool call), a successful checkout that must _not_ count, the
      four 53300 messages, the `unknown` fallback, a real `sqlstate` winning
      over the message, and `handle_error` on an open connection not counting.
      Both counter tests verified failing with the increments removed.
- [ ] **Prometheus rules.** `DbPoolTimeouts` and `DbConnectionsRefused` on
      `increase(...) > 0` live in EPFL-ENAC/openshift-app-config
      (`overlays/*/monitoring/specific-namespace-alerts.yaml`) and are a
      separate PR now that the metrics exist.

## Open

- **No auth/network split.** With psycopg dropping SQLSTATE at connect time,
  every non-53300 failure lands in `unknown` — an unreachable host and a bad
  password are indistinguishable on the label. Add markers for `28P01` /
  `3D000` if that distinction is ever wanted; the total already counts them.
- **Not exercised against a real 53300 in a deployed environment.** The label
  logic is pinned to the verbatim psycopg message text captured from a forced
  local 53300, but the end-to-end path (server full → counter → Prometheus)
  will only be confirmed by the next incident, or by deliberately squeezing
  dev's `max_connections`.
- **Nothing counts a pool timeout that is retried and succeeds** — there is no
  such retry today, but if one is ever added the counter starts measuring
  something other than failed requests.

## Related

- [#2566](./2566-db-pool-disposal-and-visibility.md) — engine disposal, the
  `checked_in`/`max_overflow` gauge series, and the incident that produced both
  failure modes on the same day.
- [#1723](./1723-job-concurrency-and-db-pool.md) — the original pool sizing,
  and where `DB_POOL_TIMEOUT` came from.
