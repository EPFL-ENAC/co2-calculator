# DB connection budget

On dev every pod talks to Postgres through the DBaaS PgBouncer; stage and
prod still hit Postgres directly (status below). Up to three pools sit
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
is using, which is what `pool_size` keeps open on purpose. So the 3 per
job is a ceiling the aggregation step touches for milliseconds, not a
steady cost, and concurrent jobs do not add up: three jobs peaked at 5
for the process, not 9. The 43 s train ingest held the same 3 to 5 as the
sub-second ones. Seven module types could not be measured locally (no
factors seeded for that year); the fifteen that ran agree.

Rule of thumb from that: a pod at rest holds 1 briefly, a worker peaks at
`MAX_CONCURRENT_JOBS + 2`, and `3 × MAX_CONCURRENT_JOBS + 3` stays the
sizing rule because it is 2× that peak, the margin that keeps a burst
from costing a user a 5 s pool timeout.

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

- Rollout surge: the chart derives the strategy from the replica floor
  (`helm/templates/backend-deployment.yaml`, `backend-worker-deployment.yaml`):
  a role with one replica rolls with `maxSurge: 1`, `maxUnavailable: 0`,
  so one extra pod is alive at base size while the old one drains; a role
  with two or more rolls with `maxSurge: 0`, `maxUnavailable: 1` and never
  exceeds its replica count. Today only dev's single worker surges; every
  backend (3 on dev and stage, HPA 2 to 3 on prod) and the two-replica
  workers do not. Budget `pool_size` for each surging pod.
- Human clients: only clients on the **app role** share the bouncer pool;
  a DBA on a superuser role has a pool of its own. That leaves the
  migration Job (runs during the rollout surge), the db-dump CronJob and
  one psql: reserve 3. A laptop running the app with the default
  `DB_POOL_SIZE=20` from `.env.example` takes 20 slots on its own; point
  local runs at Docker Postgres.
- `DB_POOL_SIZE` is what stays open forever. Behind a bouncer in session
  mode an idle persistent connection still holds a server slot, so set it
  to 1 there. On direct Postgres an idle connection is only a cheap
  backend process, so set it at the measured steady `checked_out` (5 on
  prod) and avoid churning a login per request.
- Worker ceiling: `MAX_CONCURRENT_JOBS` + 3 at the floor, 3 ×
  `MAX_CONCURRENT_JOBS` + 3 when the budget allows. Measured peak is
  `MAX_CONCURRENT_JOBS` + 2 (table above); the floor leaves 1 spare, the
  full rule a 2× margin. When the budget is tight, spend that margin on
  the backend, not on more worker overflow.
- `DB_POOL_TIMEOUT` stays 5 s. Failing in-process in 5 s beats the
  bouncer's 120 s, and nothing on the SQLAlchemy side bounds that 120 s.
- Never `-1` for `DB_MAX_OVERFLOW`: it moves the wall to the bouncer, where
  the wait is 120 s per query.

### Sizing formula

Inputs, then two lines of arithmetic. Size the **ceiling**, never the
steady state: the ceiling is what a burst reaches, and reaching the wall
is the incident (dev, 2026-09-17).

```text
W  = the wall: bouncer default_pool_size in session mode,
     else Postgres max_connections − superuser_reserved (100 − 3 = 97)
R  = other clients on that same pool: migration Job, dump CronJob,
     one psql = 3; on direct Postgres add what pg_stat_activity shows
     outside the fleet (pgAdmin: 2)
B  = W − R                                      fleet ceiling budget
J  = MAX_CONCURRENT_JOBS per worker pod
P  = pool_size: 1 behind a bouncer, measured steady (5) on direct Postgres
nb, nw = backend and worker replicas

S  = surge: P for each role that runs one replica (dev's worker), else 0

Cw = worker ceiling per pod  = 3J + 3, floor J + 3       (measured peak J + 2)
Cb = backend ceiling per pod = ⌊(B − nw·Cw − S) / nb⌋
DB_MAX_OVERFLOW = C − P for each role

check: nb·Cb + nw·Cw ≤ B, Cb ≥ 3 (a request holds 1 for its duration;
       95 rps × 80 ms ≈ 8 in flight fleet-wide at the dev load-test peak)
```

Worked, with the reserve of 3 and the measured peaks:

| Environment                       | W     | B       | nb / nw | J   | Cw        | Cb  | backend / worker | ceiling / surge |
| --------------------------------- | ----- | ------- | ------- | --- | --------- | --- | ---------------- | --------------- |
| dev, bouncer 25, one job          | 25    | 22      | 3 / 1   | 1   | 4 floor   | 5   | 1+4 / 1+3        | 19 / 20         |
| dev, bouncer 25, two jobs         | 25    | 22      | 3 / 1   | 2   | 5 floor   | 5   | 1+4 / 1+4        | 20 / 21         |
| dev, bouncer 40 (asked, #2854)    | 40    | 37      | 3 / 1   | 2   | 9 full    | 9   | 1+8 / 1+8        | 36 / 37         |
| stage, prod, direct Postgres      | 97    | 92      | 3 / 2   | 4   | 15 full   | 20  | 5+15 / 5+10      | 90 / 90         |
| stage, prod, six jobs, same pools | 97    | 92      | 3 / 2   | 6   | 15 (2J+3) | 20  | 5+15 / 5+10      | 90 / 90         |
| stage, prod, bands 65 / 35        | 65+35 | 62 / 35 | 3 / 2   | 4   | 15 full   | 20  | 1+19 / 1+14      | 60+30 / 60+30   |

Two jobs on dev cost nothing on the backend side: the worker floor grows
by 1, the backend keeps 1+4, and the fleet still fits with 1 spare under
the surge. The deployed dev values (#51: backend 1+5, worker 1+3, one
job) spend that spare on backend overflow instead; either is within the
rule.

Stage and prod can run six jobs per worker without touching a pool: the
worker's 15 is 2J + 3 at J = 6, a 1.9× margin over the measured peak of 8. What that buys is a different question: a worker pod requests 250m
CPU, and six CPU-bound ingests on a quarter core each run slower, so
raise `MAX_CONCURRENT_JOBS` there together with the CPU request, on
stage first, and watch `db_pool_timeouts_total` stay at zero. Behind a
bouncer with per-role bands the backend's `P` drops to 1 too, which is
where the extra backend overflow in the last row comes from.

## Budgets per environment (dev updated 2026-09-15)

Measured with `backend/scripts/probe_pgbouncer_pool.py`, which opens
connections through the bouncer until it queues one. Re-run it after any
DBaaS change; it holds the pool for a couple of seconds, so on prod pick
a quiet moment.

| Env         | Wall                                                           | Budget      | backend      | worker       | `MAX_CONCURRENT_JOBS` | steady | surge |
| ----------- | -------------------------------------------------------------- | ----------- | ------------ | ------------ | --------------------- | ------ | ----- |
| dev         | PgBouncer `default_pool_size` 25 (configured, session pool)    | 25 − 3 = 22 | 1+5 ×3 = 18  | 1+3 = 4      | 1                     | 22     | 23    |
| stage, prod | Postgres 100 − 3 reserved (no PgBouncer yet, see status above) | 90          | 5+13 ×3 = 54 | 5+10 ×2 = 30 | 4                     | 84     | 84    |

Stage and prod (updated 2026-09-17, openshift-app-config#47): the backend
overflow is burst insurance sized to spend the budget, not a measured
need — stage peaked at 14 `checked_out` fleet-wide on 2026-09-15 against
a ceiling of 75. No role surges there (two-replica workers, three
backends; prod's HPA floor is 2, sized at its max of 3). 90 is the line,
not 95: Postgres keeps 3 for superusers, the migration Job runs during
the rollout, and a 53300 refusal locks out the DBA too. The worker's 15 per pod is exactly
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
backend and worker blocks. The VPN path to dev goes through the bouncer
and counts against its pool; stage and prod have no bouncer, so a VPN
client there is one more Postgres connection.

## Which knob, when an alert fires

| Signal                                        | Meaning                                                      | Knob                                                                                                                    | Owner      |
| --------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ---------- |
| `db.pool.timeouts` > 0, bouncer counters at 0 | a pod hit its own ceiling while the bouncer still had room   | raise that pod's `DB_MAX_OVERFLOW` only if the fleet ceiling still fits the budget; otherwise the budget is the problem | us         |
| `db.pgbouncer.queued` > 0                     | the bouncer's pool is full; 120 s until errors               | nothing on our side helps: fewer pods, smaller ceilings, or a bigger `default_pool_size`                                | DBaaS      |
| `db.pgbouncer.queue_timeouts` > 0             | queued clients gave up; `/ready` flaps on the locked-out pod | same, plus check for a stray client (`application_name` in `pg_stat_activity`)                                          | us + DBaaS |
| `db.connect.failures{sqlstate="53300"}` > 0   | Postgres itself is full; the bouncer passed logins through   | cap the bouncer (`max_db_connections`) below `max_connections`, or raise `max_connections`                              | DBaaS      |

The seesaw ends only when the bouncer either multiplexes (transaction
pooling, which our code tolerates since #2689: `prepare_threshold` is
off) or has a pool sized for the fleet. Until then the ceiling rule is the
whole strategy, and every alert above says which side of it moved.
