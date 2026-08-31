---
status: delivered
issue: 2566
last_updated: 2026-08-31
title: "Release the DB pool on shutdown, and make real connection counts visible"
summary: "Pods exited without closing their connection pool, orphaning ~10-20 Postgres backends per rollout until TCP keepalives expired; dev filled max_connections and 500'd. Dispose the engine in the lifespan, size the pool from measurement, and export the two series that would have shown it coming."
---

# Release the DB pool on shutdown, and make real connection counts visible

## Problem

2026-08-31, dev: every request 500'd with

```
FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute
```

`pg_stat_activity` at 11:10 — **53 of 85 connections belonged to pods that no
longer existed**, idle between 46 min and 2 h 08. The `pods` heartbeat table
showed only 4 live pods (3 backend + 1 worker); their pools accounted for 19.

Root cause: **`engine.dispose()` was called nowhere.** `lifespan` cancelled its
five background loops, logged "Shutdown complete", and exited with up to
`DB_POOL_SIZE` sockets open. Behind the cluster's SNAT (every pod reaches
Postgres as `10.95.64.75`) the FIN does not reliably arrive, so Postgres held
the orphaned backends until OS TCP keepalive defaults expired — roughly 2 h.
Dev deploys faster than that, so slots accumulated until the cap.

`Dockerfile` uses `exec`, so uvicorn is PID 1 and SIGTERM does reach it: the
teardown ran, it simply never closed the pool.

Aggravating factor, not the cause: a forgotten local `uvicorn --workers 2`
against dev (that worktree's `.env` had `DB_POOL_SIZE=20`) held 35 slots for
22 h. Killed during the incident.

## Why no dashboard caught it

The Grafana panel plotted `pods x (DB_POOL_SIZE + DB_MAX_OVERFLOW)` — a
ceiling — against `max_connections`. `checked_out` peaked at 13 fleet-wide,
which was accurate and healthy. Neither series is the number that fills the
server, and orphans belong to pods that are gone, so **no pod-local gauge can
ever see them**.

## Design

1. **`await engine.dispose()` at the end of the lifespan teardown** — after
   every loop has stopped using the pool (notably `_pod_heartbeat`'s
   `_delete_pod_row`, which needs a working connection). Closes each socket
   while the pod still has a network.
2. **`DB_POOL_SIZE: "5"` on dev only** — measured, not guessed: peak
   `checked_out` is ~4/pod. `DB_MAX_OVERFLOW` stays 10, so bursts still reach
   15/pod, and overflow connections are closed on return rather than parked.
   Deliberately **not** a chart default: this repo's `helm/values.yaml` reaches
   every environment, and prod concurrency is unmeasured — too small a pool
   trades idle sockets for per-checkout connect churn. It goes in the deploy
   repo's dev values, in both `backend.env` and `worker.env`.
3. **`checked_in` in `read_pool_state`** — `checked_in + checked_out` is the
   count comparable to `max_connections`; it was the missing series.
4. **`db.server.connections` gauge** — `count(*)` over `pg_stat_activity`,
   refreshed on the existing 30 s pod-heartbeat tick (Postgres-only; sqlite
   has no such view). The only in-app signal that sees orphans. Every pod
   reports the same server-wide number: **aggregate with `max()`, never
   `sum()`**.

5. **TCP keepalives in `connect_args`** — psycopg leaves them off, so a pod
   whose server vanished mid-connection waits out the OS default (~2 h) rather
   than failing. Stage proved it on the same day: the cluster restarted the
   network underneath, every pooled socket became a black hole, and probes
   timed out instead of erroring. 30 s idle + 3 probes 10 s apart caps that at
   ~60 s. Client half only — the server reaps its own orphans via the role
   GUCs below.

### Ungraceful shutdown is not covered by any of the above

A pod killed by OOM, by SIGKILL past the grace period, or by node loss never
runs the teardown. Applied at role level on the dev DB during the incident:

```sql
alter role app set tcp_keepalives_idle='60';
alter role app set tcp_keepalives_interval='10';
alter role app set tcp_keepalives_count='3';
alter role app set idle_session_timeout='30min';
```

Postgres then probes idle clients and reaps dead-pod backends in ~3 min
instead of ~2 h. `pool_pre_ping=True` (already on) absorbs the reconnects.
Applied to **all three** environments the same day — stage forced the issue
by locking its own pods out. Note `ALTER ROLE ... SET` only takes effect for
**new** sessions: connections already open keep the OS defaults and have to
age out (or be terminated) once.

## Steps

- [x] `await engine.dispose()` at the end of `lifespan` (`backend/app/main.py`),
      with `engine` imported at module top (no inline imports).
- [x] Regression test: the lifespan swaps in a fresh pool object
      (`backend/tests/unit/test_lifespan_shutdown.py`). Verified failing with
      the line removed, passing with it.
- [x] `DB_POOL_SIZE` 15 → **8** in `backend.env` **and** `worker.env`, in all
      three overlays — EPFL-ENAC/openshift-app-config#31, merged. Not in this
      repo: `helm/values.yaml` carries only a comment saying why, since a chart
      default reaches every environment. 8 + 5 caps a 6-pod rollout at 78 of 97
      usable slots (backend HPAs cap at 3, worker has none).
- [x] `checked_in` in `read_pool_state` (`backend/app/db.py`) + updated
      assertion in `test_db_pool_settings.py`.
- [x] `db.server.connections` observable gauge fed by
      `_refresh_server_connection_count` (`backend/app/tasks/_pod_heartbeat.py`),
      with tests for the sqlite guard and the before-first-tick silence.
- [x] TCP keepalives in the engine's `connect_args` (`backend/app/db.py`),
      pinned by a test.
- [x] `max_overflow` in `read_pool_state` (#2569) so the saturation panel's
      denominator is `size + max_overflow` instead of a `+ 5` hardcoded in a
      Grafana query in another repo. Reads SQLAlchemy's private
      `_max_overflow`, pinned by an assertion so a rename fails in CI rather
      than silently in a dashboard.
- [x] Grafana: `total open (checked_in + checked_out)` and a server-side
      `db.server.connections` series, in all three environments' dashboard
      ConfigMaps (they live in `openshift-app-config`, not outside git as
      first assumed). The old "total pool capacity" series was
      `sum(state="size")` — the _configured_ pool_size, i.e. `pods x 15`,
      which read a healthy 60 while the server was full.
- [ ] **Alert at 80% of `max_connections`** on `db_server_connections` — the
      one piece of the observability work still missing, and the only rule that
      would have paged for either outage. Proposed as `DbServerConnectionsHigh`
      on EPFL-ENAC/openshift-app-config#30, whose existing
      `DbPoolSaturationHigh` measures _per-pod_ saturation and so sat at ~20%
      through both of them.
- [x] Role GUCs on stage and prod. Not deferred after all: a network blip
      orphaned stage's entire pool the same day and locked its own pods out
      (`/healthz` 200, `/ready` 503, indefinitely) until its idle backends
      were terminated by hand.
- [x] DBaaS request raised for `max_connections=200` (or PgBouncer) on all
      three instances: 100 leaves no room to scale the backend past 3 replicas,
      and the role-level keepalives are hand-applied state the DBaaS team should
      own rather than us.

## Open

- **The worker Deployment renders `worker.env`, not `backend.env`** (see the
  note in `backend-worker-deployment.yaml`), so dev's `DB_POOL_SIZE: "5"` must
  be set in both maps or the worker keeps the code default of 10.
- **The role GUCs exist in no repo.** They were applied by hand on all three
  instances; a DBaaS instance rebuild or restore drops them silently. Re-check
  with `select rolconfig from pg_roles where rolname='app'`.
- Two `pods` rows survived their pods (last heartbeat 06:52 and 07:36), which
  means those teardowns did not complete — either an ungraceful kill, or
  `_delete_pod_row` failing because the DB was already refusing connections.
  Worth confirming from pod logs after the next incident-free rollout: it
  decides whether `dispose()` alone is enough in practice.

## Related

- [#1723](./1723-job-concurrency-and-db-pool.md) — pool sizing. Its own revisit
  trigger (`replicas x (pool_size + overflow)` nearing 80% of
  `max_connections`) fired here.
- #2050 A2 — `maxSurge: 1` / `maxUnavailable: 0`, which doubles pod count
  during a rollout. Deliberately left alone: shrinking the pool is the change
  that does not re-open that outage window.
- #2220 — the local-instance-against-shared-DB incident behind
  `assert_poller_isolation`, which behaved correctly here.
