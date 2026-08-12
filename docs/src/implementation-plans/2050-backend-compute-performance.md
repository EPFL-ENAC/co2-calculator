---
status: in-progress
issue: 2050
last_updated: 2026-08-12
title: "Backend compute performance — pod stability, worker split, request-path profiling"
summary: "Three-track plan against the dev-platform slowness and the intermittent 504s. Track A fixes availability: the 504s are caused by /ready blocking on a DB pool checkout for up to DB_POOL_TIMEOUT (30 s) inside a probe with a 3 s deadline — confirmed by a readiness timeout on stage with no deployment in progress and /healthz answering 200 throughout. It is bounded with asyncio.timeout, the external Accred call leaves readiness, and rollout strategy and CPU requests are corrected. Track B moves job execution off the API pods onto a poller-only worker Deployment, using the RUN_BACKGROUND_POLLER gate that already exists, removing the job-vs-request contention for the same 20 pooled connections. Track C profiles the synchronous request path — starting with the simulator-plan reference-year PATCH, which re-runs per-entry factor resolution the recalc workflow already eliminated — and records the measurements needed before anyone argues for a language change."
---

# Backend compute performance (#2050)

## Context

Recalculation throughput measured across environments (8453 entries):

| Environment | DB         | CPU                  | Throughput  |
| ----------- | ---------- | -------------------- | ----------- |
| Local (M4)  | Docker PG  | Apple M4             | ~384 rows/s |
| Local (M4)  | IT-CENTRAL | Apple M4             | ~330 rows/s |
| k8s `dev2`  | k8s PG     | AMD EPYC 9124        | ~180 rows/s |
| k8s `dev2`  | IT-CENTRAL | AMD EPYC 9124        | ~174 rows/s |
| k8s `dev`   | IT-CENTRAL | Intel Xeon Gold 6242 | ~72 rows/s  |

PostgreSQL location and network latency are ruled out: `dev2` performs the
same against both databases. The `dev`/`dev2` gap (~2.4×) tracks the
synthetic CPU benchmark gap (~1.8×), so the remainder is platform, not
formula.

Separately, users see intermittent 504s. **The mechanism is now identified.**

Restarts are ruled out in both environments: `restartCount: 0`,
`lastState: {}`, pods running continuously since 2026-08-11 on `dev` and
`stage`. The 50 ms event-loop yield shipped after the 2026-07-17 stage
incident is holding — liveness kills are no longer the mechanism.

On 2026-08-12 09:49 UTC, `stage` produced, with **no deployment in
progress**:

```
Unhealthy — Readiness probe failed:
Get "http://10.20.21.51:8000/ready": context deadline exceeded
(Client.Timeout exceeded while awaiting headers)
```

Access logs across the same window show `/healthz` returning 200
throughout. The event loop was healthy; the block was inside `/ready`
itself. See A1.

## Track A — stop the 504s

Priority 1. Three independent causes, all cheap, all worth doing.

### A1. `/ready` can block longer than its own probe timeout

**This is the confirmed cause of the 504s, and it is an availability bug
independent of everything else in this plan. Ship it first.**

`app/main.py:349` performs a DB round trip **and** an httpx call to Accred
inside a probe configured `timeoutSeconds: 3`, `failureThreshold: 2`.
Neither branch is bounded by the probe deadline:

1. **DB pool wait — the primary mechanism.** `/ready` calls
   `get_db_session()`, which waits on the QueuePool for up to
   `DB_POOL_TIMEOUT` (`app/core/config.py:95`, **default 30 s**) — ten
   times the probe's 3 s timeout. The pool is `DB_POOL_SIZE: 10` +
   `DB_MAX_OVERFLOW: 10`, and each running job holds 1–2 connections for
   its entire runtime (see the field's own description). Once the pool is
   saturated, `/ready` hangs, the probe deadline expires, the pod leaves
   the Service endpoints, and requests 504 — while `/healthz`, which
   touches nothing, keeps answering 200. That is exactly the 2026-08-12
   09:49 signature.

   `pool_pre_ping=True` (`app/db.py:60`) adds a second round trip per
   checkout, so `/ready` costs two.

2. **Accred DNS.** `httpx.AsyncClient(timeout=2)` does not reliably
   interrupt a blocking `getaddrinfo`; a slow DNS lookup for the Accred
   host sails past the 2 s httpx timeout into the 3 s probe deadline.

3. **Probe frequency is ~24× the configured rate.** Access logs on `stage`
   show two source IPs (`10.20.50.2`, `10.20.20.2`) each hitting `/ready`
   every ~5 s — ~2.5 s combined — against a configured
   `periodSeconds: 30`. Something beyond kubelet (most likely the
   OpenShift router's route health check) is probing. Every one of those
   is two DB round trips plus an outbound HTTP call. Identify the caller;
   the endpoint must be cheap enough that this cadence is harmless either
   way.

Readiness answers "can this process serve traffic", not "is Accred up".
An external dependency there converts someone else's incident into ours.

Fix:

- Drop the Accred check from `/ready`; move it to an operator-facing
  `/health/deps`, or cache its result with a ~60 s TTL.
- Wrap the remaining DB check in `asyncio.timeout(1)` so `/ready` **cannot**
  outlive the probe deadline under any circumstance. A readiness probe that
  can block ten times longer than its own timeout is the bug; bounding it is
  the fix, and it holds even if a future check is added.
- Give the readiness DB check a short explicit `pool_timeout` rather than
  inheriting the 30 s request default.

### A0. Verification commands

For the next occurrence, and to confirm the fix (k8s events expire in
~1 h — capture promptly):

```sh
NS=svc1751d-co2-calculator-stage
kubectl -n $NS get events --sort-by=.lastTimestamp \
  --field-selector reason=Unhealthy -o wide
```

The event `count` column distinguishes chronic from one-off.

Timing `/ready` against `/healthz` from inside the pod discriminates the two
A1 branches: spikes near 2 s point at Accred/DNS, multi-second and climbing
points at the pool wait. Pool state directly:

```sh
kubectl -n $NS exec -it $POD -- python -c \
  "from app.db import engine; p=engine.pool; \
   print(p.size(), p.checkedout(), p.overflow())"
```

Correlate 504 timestamps against recalc job start/end and against deploy
times.

### A2. Rollouts must not take the only replica down

`maxSurge: 0` + `maxUnavailable: 1` with one replica means **every rollout
is a guaranteed 504 window**. This is secondary to A1 — the confirmed
09:49 stage failure had no deployment in progress — but it is a real
outage source on `dev`, which runs one replica.

Open question: `stage` reports `observedGeneration: 325` since 2026-07-16
(~11/day) against at most 3–6 intentional deployments in the period.
Generation only increments on spec change, so something is churning the
Deployment spec — CD re-applying on every push, a Helm re-render with a
volatile annotation, or a GitOps reconcile loop. Each bump is a rollout.
On `stage` (2 replicas, `maxUnavailable: 1`) that degrades capacity; on
`dev` (1 replica) it is a full outage window. Find the churn source.

- `maxSurge: 1`, `maxUnavailable: 0`.
- `replicaCount: 2` on dev (values.yaml already says 2; the effective
  manifest does not — reconcile the env override).

### A3. Raise the CPU request

`requests.cpu: 100m` on `dev`, `250m` on `stage`, no limit in either. No
limit means no CFS throttling, but CFS _shares_ are proportional to the
request: on a shared node a 100m pod gets roughly a tenth of the weight of
a 1-core neighbour. Pod QoS is Burstable, so it is also first in line under
node pressure. This stacks on top of the 1.8× slower Xeon on `dev`.

- `requests.cpu: 1` for the API deployment, `2` for the worker (Track B).

### A4. Pool sizing is coupled to job concurrency

Not a fix on its own, but it is why A1's pool wait happens: `DB_POOL_SIZE`
(10) + `DB_MAX_OVERFLOW` (10) is a per-pod hard cap, and each running job
holds 1–2 connections for its whole runtime. Every job executing on an API
pod is competing with request traffic — including the probes — for the same
20 connections. Track B removes the competition entirely by moving jobs to
a pod that serves no traffic; revisit the numbers there rather than raising
them here.

### Rejected alternatives

- **gunicorn / `WORKERS=2`.** Would isolate API latency from a pinned
  worker process when the node has spare CPU, and it is one line. Rejected:
  memory doubles under the 1000Mi limit, the in-process poller duplicates
  per worker process, and it is obsolete the day Track B lands. It is a
  degraded version of the real fix.
- **Threads.** GIL-bound; the job is a single CPU-bound coroutine.
- **HPA.** HPA scales on utilisation _relative to the request_: with a 100m
  request any recalc reads as 1000 %+ and thrashes to max replicas, and
  extra replicas cannot speed a job one pod has already claimed via
  advisory lock. Revisit after Track B, on the API deployment only, never
  on the worker.

## Track B — move job execution off the API pods

Priority 2. This is the structural fix; after it, API responsiveness is
decoupled from recalc entirely and the 50 ms yield becomes belt-and-braces
rather than load-bearing.

Most of the infrastructure exists already: the unified runner
(`app/tasks/runner.py`), DB-polling dispatch (`_poller.py`), pod heartbeats,
claim/preempt, advisory locks, and the `RUN_BACKGROUND_POLLER` settings gate
(`app/core/config.py:452`).

What is missing:

1. The four direct-dispatch sites in `app/api/v1/data_sync.py` (lines 894,
   990, 1915, 2014) call `fire_and_forget(run_job(job_id))`, which runs the
   job on whichever API pod took the request. Gate them: API pods create the
   job row and return; the worker's poller picks it up.
2. A second Deployment — same image, `RUN_BACKGROUND_POLLER=true`, no
   Service, no ingress, liveness on `/healthz` only, generous CPU and
   memory.
3. API pods set `RUN_BACKGROUND_POLLER=false`.

Chained child jobs (`_chain.py:106,387`) fire in the process where the
parent ran, so they follow the parent onto the worker with no change.

Cost: enqueue-to-pickup latency of one `POLLER_INTERVAL_SECONDS`. Accept it
or lower the interval; do not reintroduce direct dispatch.

## Track C — profile the actual compute

Priority 3, but it is the prerequisite for any "make it faster" decision,
including a language change. **Nothing in this track is an optimisation
until a measurement backs it.**

### C1. musl vs glibc (owner: lead, in progress)

The runtime image is `python:3.14-alpine`. musl's `mallocng` is materially
slower than glibc's malloc under allocation churn, and per-entry
`DataEntryResponse.model_validate` across thousands of entries is exactly
that. Reported penalties on allocation-heavy Python workloads range 1.5–3×.

The key property: **musl is orthogonal to the `dev`/`dev2` gap** — the same
image runs on both, so it cancels out of that comparison — **but it may be
a flat multiplier on every row of the table above.** Also verify how the
local ~384 rows/s figure was obtained: if that was native macOS via `uv`
rather than the container, alpine is untested everywhere and part of the
local-vs-k8s gap may be musl too.

Test: run the existing CPU benchmark script on the same dev node in
`python:3.14-slim` and in the current backend image.

Both pods must land on the same node for the comparison to mean anything
(pin with `--overrides` nodeSelector, or start each with a long-running
`sleep` and `kubectl exec -i … python - < bench.py` into it).

Note the benchmark's `x += j` loop allocates a new int object per
iteration above the small-int cache, so it does exercise the allocator —
but a Pydantic-shaped microbenchmark would be a closer proxy. If slim wins
meaningfully, two branches:

- Switch the runtime base to `debian-slim`. Cost: the CVE-surface reduction
  the Dockerfile comment explicitly bought (perl, util-linux and friends
  return).
- Keep alpine and `LD_PRELOAD` a faster allocator (jemalloc is packaged for
  Alpine; verify mimalloc availability before committing to it). Two-line
  Dockerfile change, keeps the CVE posture.

### C2. Recalc workflow profile

`EmissionRecalculationWorkflow` already emits the measurement:

```
Recalc profile <TYPE>/<year>: N entries in Xs (Y ms/entry) |
  validate=… prepare=… remainder=…
```

Pull this line from a dev run and record it here. It discriminates three
different problems:

- **`validate` dominates** → per-entry `DataEntryResponse.model_validate`.
  Cheapest available win: avoid the round trip through the response schema
  in the loop, or use `model_construct`. No rewrite, no new pattern.
- **`prepare` dominates** → factor resolution / handler `pre_compute`.
  Already heavily memoised by plans 1661 and 310D; remaining wins are
  per-handler.
- **`remainder` dominates** → bulk writes, and the DB is partly the
  bottleneck after all.

### C3. Profile the synchronous request path — `set_reference_year`

**This is the higher-priority half of Track C.** Unlike recalc, this code
runs _inside an HTTP request_: it holds the event loop **and an open
database transaction** (the commit is in the route,
`app/api/v1/simulator_plan.py:207`) for its entire duration. It has no
`asyncio.sleep(0)` yields at all.

That connects it directly to Track A: a long-held pooled connection under a
small pool makes `/ready`'s `SELECT 1` wait for a slot, readiness fails, the
pod leaves the Service, and users get 504s — with no recalc job running at
all.

Reference request to profile:

```
PATCH /api/v1/project-plans/2221/years/2027
{"reference_year": 2026, "is_grant": true}
```

Reproduce locally against the seeded DB.

#### Static findings to confirm by measurement

These come from reading `app/services/simulator_plan_service.py`; the
profile must confirm or refute each before anything is changed.

1. **`_recalculate_report_emissions` (line 649) is an N+1 per entry.** It
   calls `upsert_by_data_entry` in a loop, and that calls `prepare_create()`
   with **no** `factor_resolver`, **no** `factor_query_cache` and **no**
   `slice_cache` — so every entry re-runs the full factor SELECT plus its
   Strategy-B classification queries, then issues a DELETE and an INSERT of
   its own. This is precisely the pattern plans 1661 and 310D removed from
   the recalc workflow; this call site was never migrated. Expected to
   dominate the request.

2. **`prefill_module_from_reference` queries the same rows twice.**
   `entry_repo.list_by_module(ref_module.id)` runs at line 484 (result used
   only for the emptiness check) and again at line 497 for the copy loop.
   One of the two is pure waste.

3. **`_prefill_reference_modules` (line 359) fans out per module type**, each
   doing its own delete / fetch / compute / `recompute_stats_many`.

4. **`_sync_year_reports` (line 209) is the worst case on the `update_plan`
   path**, not the one named above: it loops over _years_, calling
   `_prefill_reference_modules` and `recompute_report_stats` per year.
   Setting a 10-year range with a reference year multiplies everything in
   (1)–(3) by ten inside a single PATCH. Profile this second.

#### Method

Lazy and mirrors what the repo already does — no new dependency, no
profiling harness:

1. **A pytest that calls the service directly** against the local seeded DB,
   wrapping the call in a SQLAlchemy `before_cursor_execute` event listener
   that counts statements, plus a `perf_counter`. Report: wall time, query
   count, query count per entry.

   This doubles as the regression test the guardrails require — assert the
   query count does **not** scale with entry count. It fails today and
   passes after the fix, which is exactly the shape a bug-fix test must
   have.

2. **A segment-timing log line in `set_reference_year`**, mirroring the
   `seg{}` / `perf_counter` block the recalc workflow already carries:
   `prefill=… recalc=… read=…`. Ships to production, so a slow plan year is
   measured rather than guessed. Mirror the existing pattern; do not invent
   a new one.

3. Only if (1) and (2) fail to localise the cost: `cProfile` around the
   service call in the same test. No new runtime dependency.

#### Expected fixes (do not implement before measuring)

- Give `_recalculate_report_emissions` the same shared `FactorResolver`,
  `factor_query_cache`, `prefetch_slice` and bulk replace that
  `_persist_prefill_entries` (line 599) and the recalc workflow already use.
  The batched version exists a few lines above in the same file — this is
  reuse, not new code.
- Drop the duplicate `list_by_module` call.
- Add the wall-time `asyncio.sleep(0)` yield used by the recalc workflow and
  `base_csv_provider.py:969`, so a long plan-year PATCH cannot starve
  `/healthz` and `/ready`.
- If the request stays long after the above, move it behind the job runner
  (Track B) and return a job id rather than a synchronous result.

## Priority order

1. **A1** — bound `/ready`, drop Accred from it. Confirmed cause of the
   504s; availability, not throughput. Ship alone, ahead of everything.
2. **A2, A3** — rollout strategy, replica count, CPU requests.
3. **C1** — musl benchmark (10 minutes; may reorder everything below).
4. **C3** — profile and fix the `set_reference_year` request path.
5. **B** — worker split (also resolves A4).
6. **C2** — recalc profile, then targeted compute work.

A0 runs alongside 1–2 as verification.

## On rewriting in another language

Explicitly last, and gated on C2/C3. Pure-Python compute is typically
10–50× slower than Rust or Go, but end-to-end gain is capped by the share
of time that is not compute (DB reads, COPY writes, deserialisation you
still have to do) — realistically 3–10×, and only if the profile shows
compute dominating **after** Tracks A, B and C1.

Against that: reimplementing the formula layer either duplicates the source
of truth — the drifted-published-number failure this project fears most —
or means porting all of it. Do not open this until the profile justifies it.

Expected stacking without it: A alone ends the 504s; A3 + B on a properly
requested worker brings `dev` to roughly `dev2` throughput (~2.4×); C1, if
confirmed, adds ~1.5–2× everywhere including local; C3 removes an N+1 whose
cost is currently unmeasured but structurally O(entries) in round trips.
