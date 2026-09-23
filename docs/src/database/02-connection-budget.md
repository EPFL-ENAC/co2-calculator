# DB connection budget

On dev every pod reaches Postgres through the DBaaS PgBouncer, in
**transaction pooling** since 2026-09-23; stage and prod still hit Postgres
directly. Up to three pools sit between a query and a backend, each with
its own limit, timeout and error text. This page is the map: where the
wall is per environment, who opens connections, and which knob to turn
when an alert fires. History and the DBaaS checklist live in the
[2689 plan](../implementation-plans/2689-pgbouncer-query-wait-timeout.md);
sizing decisions are made here, not during an incident.

## Where the wall is

| Env         | Path                                  | Wall                                         | Reserve | Budget | What sizes a pod                                                 |
| ----------- | ------------------------------------- | -------------------------------------------- | ------- | ------ | ---------------------------------------------------------------- |
| dev         | DBaaS PgBouncer 1.25.1, `transaction` | 60 **in-flight transactions** fleet-wide     | 5       | 55     | CPU and memory; the HPA adds DB concurrency                      |
| stage, prod | direct Postgres                       | `max_connections` 100 **client connections** | 10      | 90     | the [fleet-ceiling rule](#stage-and-prod-the-fleet-ceiling-rule) |

The reserve is the migration Job, the db-dump CronJob and one psql (plus
the superuser slots and pgAdmin on direct Postgres). **Stage and prod are
unchanged**: no bouncer in the path that matters, so their sizing and the
fleet-ceiling rule still bind there. They follow dev once DBaaS extends
the bouncer; do not assume their numbers will match dev's.

## Dev: transaction pooling

Dev bouncer config, agreed with DBaaS on 2026-09-23:

| Setting                   | Value                                                   | Before    |
| ------------------------- | ------------------------------------------------------- | --------- |
| `pool_mode`               | `transaction`                                           | `session` |
| `default_pool_size`       | 60                                                      | 25        |
| `min_pool_size`           | 5                                                       | 5         |
| `max_client_conn`         | 1000                                                    | 1000      |
| `max_prepared_statements` | 200                                                     | 0         |
| `query_wait_timeout`      | 10 s (agreed with DBaaS 2026-09-23; applied end of day) | 120 s     |

A server slot is held only while a transaction is in flight, not for the
life of the client connection. That retires the old rule: client
connections to the bouncer are cheap (1000 allowed, an idle one costs
Postgres nothing), so `pods × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` no longer
has to fit under the wall on dev. What is bounded is **concurrency**: at
most 60 transactions at once fleet-wide, the 61st queues for
`query_wait_timeout` and then fails with
`psycopg.errors.ProtocolViolation: query_wait_timeout`.

Pods are therefore sized by CPU and memory, and scale-out is what adds DB
concurrency (openshift-app-config #59, #60):

| Role    | `DB_POOL_SIZE` + `DB_MAX_OVERFLOW` | `DB_POOL_TIMEOUT` | Memory (request = limit) | CPU request / limit | Replicas                 | `MAX_CONCURRENT_JOBS` |
| ------- | ---------------------------------- | ----------------- | ------------------------ | ------------------- | ------------------------ | --------------------- |
| backend | 5 + 45                             | 5 s               | 512 Mi                   | 100m / 500m         | HPA 2..6, 70% CPU target | –                     |
| worker  | 5 + 15                             | 5 s               | 768 Mi                   | 150m / 1000m        | 1                        | 2                     |

Memory request must equal limit on this cluster; the HPA's memory target
is off.

**Why `query_wait_timeout` is 10 s.** A request queued at the bouncer
already holds its pod pool slot, so `DB_POOL_TIMEOUT` (5 s) cannot cut the
wait. At 120 s the pod's pool fills with waiting requests, its `/ready`
`SELECT 1` waits too, the pod goes NotReady after two failed probes
(about 60 s), traffic shifts to the other pods and they saturate in turn:
the 2026-09-08 and 2026-09-17 incidents. At 10 s the request is cut before
the second probe, the slot is handed back and the error stays on that one
request. 10 s is also the app's request-latency alert threshold.

**Prepared statements.** psycopg 3.3.6 with libpq 18 replays named
prepares through the bouncer natively, so the app keeps psycopg's default
`prepare_threshold` (#2921 briefly set it to `None` as a stopgap, #2922
removed it the same day).

**Code invariants under transaction pooling**, all already true (audit in
the plan):

- advisory locks are `pg_advisory_xact_lock` only (`app/tasks/_locks.py`);
- temp staging tables are `ON COMMIT DROP`;
- no `LISTEN/NOTIFY`, no session-level `SET`, no `WITH HOLD` cursors;
- the app sends `application_name=co2-<pod>`, which the bouncer forwards,
  so `pg_stat_activity` can still tell pods apart.

**Probes** (`backend/scripts/`, run through the bouncer, dev only, when
nobody is testing):

| Script                            | Proves                                                                                                                             |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `probe_pgbouncer_wait_timeout.py` | the effective `query_wait_timeout`: fills the pool with open transactions until one client queues, then times the wait (#2923)     |
| `probe_pgbouncer_prepared.py`     | prepared-statement replay across rotating server connections (#2922)                                                               |
| `probe_pgbouncer_pool.py`         | the **session-mode** pool only; its autocommit `SELECT 1` hands the slot back instantly, so it cannot fill a transaction-mode pool |

## Who opens connections

Per pod, in the order they start (`app/main.py` lifespan):

| Loop                                | Runs on                                                                            | Cadence      | Connections at once                                                                                         |
| ----------------------------------- | ---------------------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------- |
| DB health poller (`_db_health.py`)  | all pods                                                                           | 1 s          | 1, never held past 1 s; `/ready` reads its verdict                                                          |
| Pod heartbeat (`_pod_heartbeat.py`) | all pods                                                                           | 30 s         | 1, also refreshes the server-side gauge                                                                     |
| Pipeline reconciler                 | worker only (API pods set `RUN_PIPELINE_RECONCILER=false` in every overlay, #2854) | 60 s         | 1                                                                                                           |
| Safety poller (`_poller.py`)        | worker only (`RUN_BACKGROUND_POLLER`)                                              | 2 s          | 1, plus what it dispatches                                                                                  |
| Job runner (`runner.py`)            | worker                                                                             | per job      | up to 3 per running job (job session, data session, chain helper); measured 1 most of the time, see below   |
| Request handlers                    | backend                                                                            | per request  | 1 from the route's first query to the end of the response; auth releases its own before the route body runs |
| SSE streams (`data_sync.py`)        | backend                                                                            | per 2 s poll | 1 for a few ms per poll, none between polls                                                                 |

Measured (2026-09-18, local Postgres, `pg_stat_activity` every 50 ms via
`backend/tests/performance/pipeline_connections.py`; one 500-row upload
per module type, then three units at once for six modules):

| Situation                          | held connections, peak | median |
| ---------------------------------- | ---------------------- | ------ |
| pod at rest (loops only)           | 1                      | 0      |
| one pipeline, ingest phase         | 2                      | 1      |
| one pipeline, recalc phase         | 2                      | 1      |
| one pipeline, aggregation phase    | 3                      | 1      |
| three pipelines at once, whole pod | 5                      | 3      |

"Held" is any state but `idle`; an idle row is a pooled connection nobody
is using, which is what `pool_size` keeps open on purpose. On dev an idle
row costs no bouncer slot either; only the held ones count against the 60. Rule of thumb: a pod at rest holds 1 briefly, a worker peaks at
`MAX_CONCURRENT_JOBS + 2`, and `3 × MAX_CONCURRENT_JOBS + 3` is the
worker's direct-Postgres sizing rule, a 2× margin over that peak.

## The three layers

| Layer                  | Waits for                                                       | Timeout                             | What you see                                                                                                                                                            |
| ---------------------- | --------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQLAlchemy `QueuePool` | a slot in this pod's pool (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`)  | `DB_POOL_TIMEOUT`, 5 s              | `sqlalchemy.exc.TimeoutError: QueuePool limit of size … reached`; counter `db.pool.timeouts`                                                                            |
| PgBouncer (dev)        | a free server slot for its transaction (`default_pool_size` 60) | `query_wait_timeout`, 10 s          | NOTICE `client being queued` at once, counter `db.pgbouncer.queued`; then `psycopg.errors.ProtocolViolation: query_wait_timeout`, counter `db.pgbouncer.queue_timeouts` |
| Postgres login         | a backend under `max_connections` (100)                         | none, immediate                     | `FATAL: remaining connection slots are reserved` / `too many clients already`; counter `db.connect.failures{sqlstate="53300"}`                                          |
| Postgres execution     | locks, I/O                                                      | `statement_timeout`, `lock_timeout` | `canceling statement due to …`                                                                                                                                          |

The app logs which layer said no, in plain words, next to the raw error
(`app/db.py`, `explain_db_wait`). `pool_size` connections stay open for
the pod's life with TCP keepalives every 30 s (`_PG_KEEPALIVES`, #2566),
so a pod notices a dead peer in about a minute; overflow connections are
opened on demand and closed on check-in, so each one is a fresh login
(about 15 ms through the bouncer).

## Stage and prod: the fleet-ceiling rule

**Fleet ceiling = pods × (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) must fit
under `max_connections`, minus a rollout surge and the human clients.**
Overflow past that is not capacity: it is a 53300 refusal that hits every
client, the DBA included.

- Rollout surge: a role with one replica rolls with `maxSurge: 1`,
  `maxUnavailable: 0`, so one extra pod is alive at base size while the
  old one drains; a role with two or more rolls with `maxSurge: 0`,
  `maxUnavailable: 1` (`helm/templates/backend-deployment.yaml`,
  `backend-worker-deployment.yaml`). Nothing surges on stage or prod
  (three backends, two workers). Budget `pool_size` for each surging pod.
- Human clients: the migration Job (runs during the rollout), the db-dump
  CronJob, one psql, pgAdmin, and Postgres's 3 superuser slots. A laptop
  running the app with the default `DB_POOL_SIZE=20` from `.env.example`
  takes 20 slots on its own; point local runs at Docker Postgres.
- `DB_POOL_SIZE` is what stays open forever. On direct Postgres an idle
  connection is a cheap backend process, so set it at the measured steady
  `checked_out` (5 on prod) and avoid churning a login per request.
- Worker ceiling: `MAX_CONCURRENT_JOBS` + 3 at the floor, 3 ×
  `MAX_CONCURRENT_JOBS` + 3 when the budget allows. When the budget is
  tight, spend the margin on the backend, not on more worker overflow.
- `DB_POOL_TIMEOUT` stays 5 s: failing in-process beats waiting on the
  wall. Never `-1` for `DB_MAX_OVERFLOW`.

### Sizing formula

Size the **ceiling**, never the steady state: the ceiling is what a burst
reaches, and reaching the wall is the incident (dev, 2026-09-17, while
the bouncer was still in session mode).

```text
W  = Postgres max_connections − superuser_reserved (100 − 3 = 97)
R  = other clients: migration Job, dump CronJob, one psql = 3,
     plus what pg_stat_activity shows outside the fleet (pgAdmin: 2)
B  = W − R                                      fleet ceiling budget
J  = MAX_CONCURRENT_JOBS per worker pod
P  = pool_size, measured steady (5)
nb, nw = backend and worker replicas
S  = surge: P for each role that runs one replica, else 0

Cw = worker ceiling per pod  = 3J + 3, floor J + 3       (measured peak J + 2)
Cb = backend ceiling per pod = ⌊(B − nw·Cw − S) / nb⌋
DB_MAX_OVERFLOW = C − P for each role

check: nb·Cb + nw·Cw ≤ B, Cb ≥ 3 (a request holds 1 for its duration;
       95 rps × 80 ms ≈ 8 in flight fleet-wide at the dev load-test peak)
```

| Environment                       | W   | B   | nb / nw  | J   | Cw        | Cb  | backend / worker | ceiling / surge                                   |
| --------------------------------- | --- | --- | -------- | --- | --------- | --- | ---------------- | ------------------------------------------------- |
| dev, bouncer 60, transaction mode | –   | 55  | 2..6 / 1 | 2   | –         | –   | 5+45 / 5+15      | formula does not bind; 55 concurrent transactions |
| stage, prod, direct Postgres      | 97  | 92  | 3 / 2    | 4   | 15 full   | 20  | 5+15 / 5+10      | 90 / 90                                           |
| stage, prod, six jobs, same pools | 97  | 92  | 3 / 2    | 6   | 15 (2J+3) | 20  | 5+15 / 5+10      | 90 / 90                                           |

Stage and prod can run six jobs per worker without touching a pool: the
worker's 15 is 2J + 3 at J = 6, a 1.9× margin over the measured peak of 8. A worker pod requests 250m CPU there, so raise `MAX_CONCURRENT_JOBS`
together with the CPU request, on stage first, and watch
`db_pool_timeouts_total` stay at zero.

## Budgets per environment

| Env         | Wall                                                  | Budget | backend       | worker        | `MAX_CONCURRENT_JOBS` | Fleet client connections at ceiling  |
| ----------- | ----------------------------------------------------- | ------ | ------------- | ------------- | --------------------- | ------------------------------------ |
| dev         | 60 in-flight transactions (bouncer, transaction mode) | 55     | 5+45 × 2..6   | 5+15          | 2                     | 120 to 320 of 1000 `max_client_conn` |
| stage, prod | Postgres 100 − 3 reserved (no PgBouncer yet)          | 90     | 5+13 × 3 = 54 | 5+10 × 2 = 30 | 4                     | 84 (steady = surge)                  |

Stage and prod (openshift-app-config #47): the backend overflow is burst
insurance sized to spend the budget, not a measured need; stage peaked at
14 `checked_out` fleet-wide on 2026-09-15. 90 is the line, not 95:
Postgres keeps 3 for superusers, the migration Job runs during the
rollout, and a 53300 refusal locks out the DBA too.

Values live in `openshift-app-config`, `overlays/<env>/kustomization.yaml`,
backend and worker blocks. The VPN path to dev goes through the bouncer:
a VPN client's idle connection is free, its open transactions count
against the 60. On stage and prod a VPN client is one more Postgres
connection.

## Dashboard

The Grafana "Specific graphs" dashboard (openshift-app-config #61, #62)
has rows Traffic / Database / Worker / Scaling. On dev the wall panel
reads "wall (60) and budget (55)" and the layer-2 counters are
`db.pgbouncer.queued` and `db.pgbouncer.queue_timeouts`. A `DbBouncerQueued`
bar means "more than 60 in-flight transactions at once", which is allowed
by design; `DbBouncerQueueTimeout` is the one that failed requests.

## Which knob, when an alert fires

| Signal                                      | Meaning                                                                                                                      | Knob                                                                                                                                                                                      | Owner      |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `db.pool.timeouts` > 0                      | a pod ran more than `DB_POOL_SIZE + DB_MAX_OVERFLOW` concurrent requests (50 on dev, so rare there)                          | dev: look at the HPA, the pod should have scaled out. Stage/prod: raise that pod's `DB_MAX_OVERFLOW` only if the fleet ceiling still fits the budget; otherwise the budget is the problem | us         |
| `db.pgbouncer.queued` > 0                   | the fleet exceeded 60 concurrent transactions; 10 s until errors                                                             | a stray client (`application_name` in `pg_stat_activity`), a long transaction holding slots (COPY-based factor upsert, long routes), or ask DBaaS for a bigger `default_pool_size`        | us + DBaaS |
| `db.pgbouncer.queue_timeouts` > 0           | same, and the requests behind them failed after 10 s                                                                         | same                                                                                                                                                                                      | us + DBaaS |
| `db.connect.failures{sqlstate="53300"}` > 0 | Postgres itself is full: on stage/prod the fleet ceiling overran `max_connections`; on dev the bouncer passed logins through | stage/prod: orphans and stray clients first, then the ceiling rule; dev: cap the bouncer (`max_db_connections`) below `max_connections`, or raise `max_connections`                       | DBaaS      |

On dev the bouncer multiplexes, so the old seesaw between pod ceilings
and the bouncer pool is over: a pod that needs more concurrency scales
out, and the only shared limit is 60 transactions at once. On stage and
prod the fleet-ceiling rule is still the whole strategy until the bouncer
gets there.

## Open follow-ups

- A request-deadline middleware in the API would bound a request's total
  wait on our side and let `query_wait_timeout` rise to about 30 s for the
  worker's benefit.
- A `jobs.running` gauge on the worker's `MAX_CONCURRENT_JOBS` semaphore.
- Stage and prod behind the bouncer, once DBaaS extends it.
