# DB connection budget

Every pod talks to Postgres through the DBaaS PgBouncer. Three pools sit
between a query and a backend, each with its own limit, timeout and error
text. This page is the map: who opens connections, where the ceiling is
per environment, and which knob to turn when an alert fires. Sizing
decisions are made here, not in a hurry during an incident (#2689).

## PgBouncer rollout status (2026-09-15)

A tuned PgBouncer is deployed on **dev only**, replacing the previous
100-connection direct-to-Postgres ceiling with a 25-connection pool.
**Stage and prod are unchanged** — still the old ~100-connection direct
path — pending an internal review/alignment decision on whether to roll
the same PgBouncer treatment out to them. Don't assume the stage/prod
numbers below will match dev's once that lands.

Dev's config:

```yaml
pgbouncer:
  poolMode: session # transaction, session, or statement
  parameters:
    max_client_conn: "1000"
    default_pool_size: "25"
    min_pool_size: "5"
```

`poolMode: session` confirms the bouncer is not multiplexing connections
(that would be `transaction` mode) — a server connection is held for a
client's whole session, so the fleet-ceiling rule below is still the
whole story on dev, not a fallback.

## Who opens connections

Per pod, in the order they start (`app/main.py` lifespan):

| Loop                                | Runs on                               | Cadence      | Connections at once                                                                                         |
| ----------------------------------- | ------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------- |
| DB health poller (`_db_health.py`)  | all pods                              | 1 s          | 1, never held past 1 s; `/ready` reads its verdict                                                          |
| Pod heartbeat (`_pod_heartbeat.py`) | all pods                              | 30 s         | 1, also refreshes the server-side gauge                                                                     |
| Pipeline reconciler                 | all pods                              | 60 s         | 1                                                                                                           |
| Safety poller (`_poller.py`)        | worker only (`RUN_BACKGROUND_POLLER`) | 2 s          | 1, plus what it dispatches                                                                                  |
| Job runner (`runner.py`)            | worker                                | per job      | 3 per running job: job session, data session, chain helper; `MAX_CONCURRENT_JOBS` jobs                      |
| Request handlers                    | backend                               | per request  | 1 from the route's first query to the end of the response; auth releases its own before the route body runs |
| SSE streams (`data_sync.py`)        | backend                               | per 2 s poll | 1 for a few ms per poll, none between polls                                                                 |

Rule of thumb: a backend pod at rest holds 2, a worker at rest 3 plus
`3 × MAX_CONCURRENT_JOBS` under load. Measured steady `checked_out` is
2 to 4 per pod (#2566, #2689).

## The three layers

| Layer                  | Waits for                                                      | Timeout                             | What you see                                                                                                                                                                    |
| ---------------------- | -------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQLAlchemy `QueuePool` | a slot in this pod's pool (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) | `DB_POOL_TIMEOUT`, 5 s              | `sqlalchemy.exc.TimeoutError: QueuePool limit of size … reached`; counter `db.pool.timeouts`                                                                                    |
| PgBouncer              | a server connection in its pool (`default_pool_size`)          | `query_wait_timeout`, 120 s         | NOTICE `client being queued` at once (1.22+), counter `db.pgbouncer.queued`; then `psycopg.errors.ProtocolViolation: query_wait_timeout`, counter `db.pgbouncer.queue_timeouts` |
| Postgres login         | a backend under `max_connections` (100)                        | none, immediate                     | `FATAL: remaining connection slots are reserved` / `too many clients already`; counter `db.connect.failures{sqlstate="53300"}`                                                  |
| Postgres execution     | locks, I/O                                                     | `statement_timeout`, `lock_timeout` | `canceling statement due to …`                                                                                                                                                  |

The app logs which layer said no, in plain words, next to the raw error
(`app/db.py`, `explain_db_wait`). `pool_size` connections stay open for
the pod's life; overflow connections are opened on demand and closed on
check-in, so each one is a fresh login through the bouncer (about 15 ms).

## The rule

**Fleet ceiling = pods × (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) must fit
under the layer that says no, minus a rollout surge and the human
clients.** Overflow past that is not capacity: it is a 120 s queue at the
bouncer, or on an environment whose bouncer pool exceeds Postgres, a
refusal that hits every client including the DBA.

- Rollout surge: `maxSurge: 1`, `maxUnavailable: 0` (`helm/templates/
backend-deployment.yaml`), so one extra backend and one extra worker are
  alive at base size while the old ones drain. Budget for base, not
  ceiling, on the surge pods.
- Human clients: only clients on the **app role** share the bouncer pool;
  a DBA on a superuser role has a pool of its own. That leaves the
  migration Job (runs during the rollout surge), the db-dump CronJob and
  one psql: reserve 3. A laptop running the app with the default
  `DB_POOL_SIZE=20` from `.env.example` takes 20 slots on its own; point
  local runs at Docker Postgres.
- `DB_POOL_SIZE` is what stays open forever. Set it at the measured steady
  `checked_out` where the budget allows, so normal traffic never churns a
  login; on a small budget set it to 2 and accept the churn.
- Worker ceiling ≥ `MAX_CONCURRENT_JOBS` × 3 + 3 loops, or jobs queue on
  the pod's own pool.
- `DB_POOL_TIMEOUT` stays 5 s. Failing in-process in 5 s beats the
  bouncer's 120 s, and nothing on the SQLAlchemy side bounds that 120 s.
- Never `-1` for `DB_MAX_OVERFLOW`: it moves the wall to the bouncer, where
  the wait is 120 s per query.

## Budgets per environment (dev updated 2026-09-15)

Measured with `backend/scripts/probe_pgbouncer_pool.py`, which opens
connections through the bouncer until it queues one. Re-run it after any
DBaaS change; it holds the pool for a couple of seconds, so on prod pick
a quiet moment.

| Env         | Wall                                                           | Budget      | backend      | worker       | `MAX_CONCURRENT_JOBS` | steady | surge |
| ----------- | -------------------------------------------------------------- | ----------- | ------------ | ------------ | --------------------- | ------ | ----- |
| dev         | PgBouncer `default_pool_size` 25 (configured, session pool)    | 25 − 3 = 22 | 1+5 ×3 = 18  | 1+3 = 4      | 1                     | 22     | 23    |
| stage, prod | Postgres 100 − 3 reserved (no PgBouncer yet, see status above) | 90          | 5+13 ×3 = 54 | 5+10 ×2 = 30 | 4                     | 84     | 89    |

Stage and prod (updated 2026-09-17, openshift-app-config#47): the backend
overflow is burst insurance sized to spend the budget, not a measured
need — stage peaked at 14 `checked_out` fleet-wide on 2026-09-15 against
a ceiling of 75. 90 is the line, not 95: Postgres keeps 3 for superusers,
the migration Job runs during the rollout surge, and a 53300 refusal
locks out the DBA too. The worker's 15 per pod is exactly
`MAX_CONCURRENT_JOBS` × 3 + 3 loops; more overflow there is idle.

Dev (resized 2026-09-17, #2854): the previous 30-ceiling sizing was
calibrated against a 35-slot pool and got discovered as an incident once
the pool was 25. A 20-job worker pushed total open past 25; every fresh
login then queued 120 s at the bouncer while still holding a slot in its
pod's pool, all three backend pools filled to 100%, requests timed out
after 5 s, `/ready` went red and the backend served 503 for seven
minutes. Two lessons are baked into the new numbers: the **ceiling**, not
the steady state, is what must fit under the bouncer, and one pod
overrunning a shared pool locks out every other pod. Interactive traffic
gets the overflow, the worker is capped to one job, `pool_size` is 1
everywhere (a persistent connection holds a bouncer slot even idle), and
the pipeline reconciler runs on the worker only. The structural fix is a
second DB role for the worker so it gets its own bouncer pool; until
then the worker runs one job at a time.

Values live in `openshift-app-config`, `overlays/<env>/kustomization.yaml`,
backend and worker blocks. The VPN path to stage bypasses the bouncer; the
VPN path to dev and prod goes through it.

## Which knob, when an alert fires

| Signal                                        | Meaning                                                      | Knob                                                                                                                    | Owner      |
| --------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ---------- |
| `db.pool.timeouts` > 0, bouncer counters at 0 | a pod hit its own ceiling while the bouncer still had room   | raise that pod's `DB_MAX_OVERFLOW` only if the fleet ceiling still fits the budget; otherwise the budget is the problem | us         |
| `db.pgbouncer.queued` > 0                     | the bouncer's pool is full; 120 s until errors               | nothing on our side helps: fewer pods, smaller ceilings, or a bigger `default_pool_size`                                | DBaaS      |
| `db.pgbouncer.queue_timeouts` > 0             | queued clients gave up; `/ready` flaps on the locked-out pod | same, plus check for a stray client (`application_name` in `pg_stat_activity`)                                          | us + DBaaS |
| `db.connect.failures{sqlstate="53300"}` > 0   | Postgres itself is full; the bouncer passed logins through   | cap the bouncer (`max_db_connections`) below `max_connections`, or raise `max_connections`                              | DBaaS      |

The seesaw ends only when the bouncer either multiplexes (transaction
pooling, which our code tolerates since #2689 once `prepare_threshold` is
off) or has a pool sized for the fleet. Until then the ceiling rule is the
whole strategy, and every alert above says which side of it moved.
