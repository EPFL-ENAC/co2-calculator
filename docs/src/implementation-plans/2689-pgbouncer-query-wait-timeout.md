---
status: delivered
issue: 2689
last_updated: 2026-09-09
title: "DB queries queue at the DBaaS PgBouncer: query_wait_timeout waves"
summary: "Dev lost two hours on 2026-09-08 to psycopg ProtocolViolation query_wait_timeout waves, each 120 s long. The error is PgBouncer's client-wait timeout: DBaaS bounces dev, stage and prod, and the server-side connection count plateaus at ~40 in dev. Our SQLAlchemy pool was never the wall (no QueuePool limit error), it was 17 coroutines each holding a slot while queued at the bouncer. Shipped: get_current_user hands its connection back before any route body runs (the general form of #2654), the DB health poller no longer freezes /ready for two minutes per wave, the orphan-poller log stops spamming, and both pods move to 5+50 in openshift-app-config."
---

# DB queries queue at the DBaaS PgBouncer (#2689)

## Symptom

2026-09-08, dev, while bulk-uploading CSVs from the backoffice: streams
showed "Connection to sync job lost", `/ready` flapped to 503 on backend
and worker pods, ingest jobs died mid-run, and the pod-saturation panel
showed backend pod `5p8vq` at 17/17 (94%). Waves at 13:52, 13:58, 14:15,
14:17, 14:19, 14:21 UTC, then again around 20:30 to 22:00 UTC. Loki counts
66 `query_wait_timeout` lines in dev over the day, none in stage or prod
in the same two days.

## What actually happened

Every error, backend and worker, is

```
psycopg.errors.ProtocolViolation: query_wait_timeout
```

on trivial statements (`SELECT ... FROM data_ingestion_jobs WHERE id = 71`,
`SELECT 1`, `pg_advisory_xact_lock`), each after ~120 s. That string is
PgBouncer's "client waited too long for a server connection". DBaaS
confirmed on 2026-09-08 that dev, stage and prod are bounced, with "about
1000" as the client limit. On dev every server-side connection arrives
from one address (`10.95.64.75`), the bouncer.

Tempo for the incident window (`{duration>1s}`, 148 traces):

| Root                                                                    | Count | What it was doing                         |
| ----------------------------------------------------------------------- | ----- | ----------------------------------------- |
| `GET /v1/sync/pipelines/{id}/stream`                                    | 46    | per-poll job select blocked 112 to 118 s  |
| `GET /v1/sync/jobs/{id}/stream`                                         | 29    | same                                      |
| bare `SELECT` / `UPDATE` / `INSERT` (backend + worker background loops) | 36    | 50 to 120 s, all `query_wait_timeout`     |
| worker `job csv_ingest` / `factor_ingest`                               | 15    | up to 700 s                               |
| `GET /v1/sync/pipelines`, `/active-pipelines`, `/year-configuration/`   | 5     | 88 s on `SELECT users` (get_current_user) |

Nobody was slow. Everybody was queued at the bouncer. The 17 on pod `5p8vq`
were 17 coroutines each holding one SQLAlchemy slot while waiting; the
error-level log export for the whole day contains zero
`QueuePool limit ... reached` lines, so our pool never refused anyone. The
in-flight list on that pod at the peak (`kind=server && duration>2s`) is 19
stream polls and one connector check, all waiting, no holder.

Prometheus `max(db_server_connections)` over 21 days:

| Env   | Baseline | Peaks                                  |
| ----- | -------- | -------------------------------------- |
| dev   | 20       | 38 to 41 on 09-02, 09-03, 09-07, 09-08 |
| stage | 19       | 46 on 09-01                            |
| prod  | 17       | 31 on 09-01                            |

Caveat: that gauge is emitted by the pod heartbeat, which itself blocks at
the bouncer during a stall, so the flat line _during_ a wave is a frozen
value. The repeated ~40 plateau across four days is real.

## Root cause on our side

`get_current_user` took its session from `get_db`, a `yield` dependency.
Since FastAPI 0.118 a `yield` dependency is released only after the
response is fully sent, and the `SELECT users` autobegins a transaction, so
every authenticated request pinned one pooled connection from auth to the
last byte. For a JSON route that is milliseconds. For an SSE stream it is
minutes, for a CSV `temp-upload` it is the whole S3 write, for the connector
test it is the outbound HTTP call. #2654 patched the two streams with a
second dependency (`get_current_user_detached`) and left every other route
as it was. Under a bulk upload the pinned connections outnumbered the
bouncer's server pool, and from then on every new checkout, including the
health poller's `SELECT 1`, queued 120 s and died.

Two more of ours made it worse:

- `_db_health._check_once` wrapped the probe in `asyncio.timeout(1)`.
  Cancelling a SQLAlchemy call mid-checkout blocks in the connection
  teardown until the server answers, so the loop stopped ticking for the
  whole 120 s wave and `/ready` reported "unknown"/503 (worker log:
  13:52:05 to 13:52:55, 13:57:05 to 13:58:52, 14:13:22 to 14:15:59 UTC,
  each ending on a Task-6 invalidation).
- The worker overlay still shipped `DB_MAX_OVERFLOW: "50"` in all three
  environments while its comment said "both 2+15".

## Shipped

1. **`get_current_user` releases its connection** (`app/core/security.py`):
   after the lookup it expunges the `User` and rolls the session back, so
   the connection is in the pool before the route body runs. The route's
   own `get_db` session is untouched: its first query autobegins again and
   takes a connection only then. `User` has no relationships, so a detached
   instance is complete. `get_current_user_detached` is deleted; the two
   streams and their tests use the one dependency. Regression test:
   `tests/unit/core/test_get_current_user_releases_connection.py` (fails on
   the old code: the user is still attached and the session in a
   transaction).
2. **`/ready` survives a stall** (`app/tasks/_db_health.py`): the probe
   runs as its own task and is waited for, never cancelled. A probe that
   outlives the 1 s wait is reported "down" now and re-awaited on the next
   tick, so a hung teardown neither freezes the loop nor stacks a second
   connection behind the stall. Regression test:
   `test_stuck_probe_teardown_does_not_freeze_the_loop` (fails on the old
   code: the tick takes the whole hang).
3. **Poller log noise** (`app/tasks/_poller.py`): "dispatching job N" is
   logged inside `schedule_job` after the in-flight guard, once per real
   dispatch instead of every 2 s sweep.
4. **5+50 on backend and worker, dev, stage, prod** (openshift-app-config,
   both `configMapGenerator` blocks per overlay, comment rewritten). 5 is
   the per-pod base DBaaS recommends; overflow sockets are closed on
   check-in, so 50 is burst room. `DB_POOL_TIMEOUT` stays 5 s: it bounds
   the wait for one of our own slots, never the in-query wait at the
   bouncer, and a request that fails in 5 s in-process beats one that
   queues 120 s.
5. **Docs**: `database/01-overview.md` is the canonical PgBouncer note;
   ADR-004 and plan 1723's "no PgBouncer" sections are marked superseded;
   the architecture pages drop the "no PgBouncer" claims.

## Still open

- **Pool mode on the app path.** From pgAdmin over VPN on stage, `SET` +
  pid stay stable across autocommit statements, which is session
  behaviour, but that session shows up in `pg_stat_activity` with the
  laptop's own IP, so the VPN path is probably not bounced. Check with
  `SELECT inet_client_addr()` from psql on dev: the bouncer's address
  means the psql path is bounced and the `SET` + pid test is conclusive
  there. Otherwise run it from a pod:

  ```bash
  oc -n svc1751d-co2-calculator-dev exec deploy/co2-calculator-backend -- \
    uv run python -c "
  import asyncio, psycopg
  from app.db import engine
  url = engine.url.render_as_string(hide_password=False)
  async def main():
      async with await psycopg.AsyncConnection.connect(url, autocommit=True) as c:
          for _ in range(5):
              cur = await c.execute('select inet_client_addr(), pg_backend_pid()')
              print(await cur.fetchone())
  asyncio.run(main())"
  ```

  Same pid every time: session pooling. Changing pid: transaction pooling,
  and then `prepare_threshold=None` goes into `connect_args` unless the
  bouncer is 1.21+ with `max_prepared_statements`.

- **Server pool size.** DBaaS says ~1000; that is a client limit. The
  number that ran out is the bouncer's pool towards Postgres, or Postgres
  `max_connections=100` when the bouncer cannot open a new backend. The
  ~40 plateau is the effective cap until DBaaS says otherwise. Questions
  sent per environment: `pool_mode`, `default_pool_size` /
  `max_db_connections`, `query_wait_timeout`, `server_idle_timeout` /
  `server_lifetime` (rotation, so orphans from dead pods do not hold
  slots), `client_idle_timeout`, PgBouncer version.
- **Routes that hold their own session across slow work.** After this PR
  the connection is held from a route's first query to the end of the
  response. `POST /v1/connectors/{connector}/test` reads config, then does
  the outbound probe, then audits, all on one session. Audit the others
  with `{kind=server && duration>500ms}` in Tempo once dev has run a week
  on this build.
- **Dashboard and alert** (openshift-app-config): drop the
  `max_connections=100` reference line, plot the ~40 plateau, add a Loki
  alert on `query_wait_timeout` per namespace (one Grafana per cluster).
- **Long ingests** (job 59: 144k rows in one transaction, ~70 min at 34
  rows/s): read the trace first. Batch commits touch pipeline idempotency
  (310-series, 1215, 1219, 1559, 1723) and need a written plan reviewed by
  both maintainers.

## Rejected

- **`max_overflow` 200 or -1**: moves the queue from our pool to the
  bouncer, where the wait is 120 s instead of 5 s.
- **Raising `DB_POOL_TIMEOUT`**: same reason, and it does not bound the
  in-query wait anyway.
- **`pool_use_lifo=True`**: it only changes which idle connection is
  reused; it does nothing for queueing. Worth adding if the pod-side test
  says session pooling, so idle base connections age out server-side.
- **A second auth dependency per slow route** (the #2654 shape): every
  route is a slow route behind a stalled bouncer. One dependency that
  releases is smaller than two that differ.
- **Frontend retry tolerance on the streams** (first cut of #2654): hides
  the 500 and leaves the queue in place.

## Verification

- `uv run pytest tests/unit`: 2905 passed on sqlite; both regression tests
  verified failing with the fix reverted.
- `make lint`, backend `make type-check` green.
- After the config PR: `db_client_connections_usage{state="size"}` reads 5
  per pod on every env.
- Next upload burst in dev: Loki `query_wait_timeout` count stays at 0, and
  `/ready` never leaves 200 for more than one probe.
