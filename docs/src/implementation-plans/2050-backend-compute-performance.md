---
status: in-progress
issue: 2050
last_updated: 2026-08-12
title: "Backend compute performance — pod stability, worker split, request-path profiling"
summary: "Three-track plan against the dev-platform slowness and the intermittent 504s. Track A fixes availability: the 504s are caused by /ready blocking on a DB pool checkout for up to DB_POOL_TIMEOUT (30 s) inside a probe with a 3 s deadline — confirmed by a readiness timeout on stage with no deployment in progress and /healthz answering 200 throughout. It is bounded with asyncio.timeout, the external Accred call leaves readiness, and rollout strategy and CPU requests are corrected. Track B moves job execution off the API pods onto a poller-only worker Deployment, using the RUN_BACKGROUND_POLLER gate that already exists, removing the job-vs-request contention for the same 20 pooled connections. Track C's measurement phase is complete: musl costs ~11-20% and is only partly recoverable via jemalloc (one-line Dockerfile fix, kept on Alpine — a real Trivy scan confirmed the CVE rationale for staying on Alpine still holds); the recalc workflow is ~77% factor-resolution time, not Pydantic overhead; and the simulator-plan reference-year PATCH has a confirmed O(entries) N+1 (a per-entry SELECT+DELETE that should be one set-based statement, 50% of all statements at N=8000) with fixes and a regression test ready to implement. Both findings argue against a language rewrite: the bottleneck is round-trip count, not CPU cycles."
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

### C1. musl vs glibc — measured, decided

**Status: done.** Two rounds of benchmarking (Docker Desktop / macOS
arm64 — direction should transfer to the k8s x86 nodes, magnitude may not;
worth a one-off rerun on a `dev`/`dev2` pod before treating the numbers
below as final) plus a real Trivy scan of the actual `backend/Dockerfile`
against a Debian/glibc mirror of it.

**Round 1 — is there a real effect, or is it noise?** `bench_alloc.py`
(arithmetic control + allocation-churn workload proxying
`model_validate`-shaped Pydantic construction), alpine vs slim, 5
iterations each:

| Workload                | alpine (musl) | slim (glibc) | ratio |
| ----------------------- | ------------- | ------------ | ----- |
| arith (control)         | 52.3 M/s      | 62.4 M/s     | 1.19× |
| alloc (Pydantic-shaped) | 1.09 M/s      | 1.44 M/s     | 1.32× |

The alloc ratio being higher than the control ratio confirms a real,
allocation-specific effect — not just noise or a generic arch difference.

**Round 2 — does an allocator swap fix it, or is it musl/libc itself?**
Median of 3 fresh runs per variant, alpine-default vs `LD_PRELOAD`
jemalloc vs `LD_PRELOAD` mimalloc vs slim:

| Variant                   | arith vs slim | alloc vs slim |
| ------------------------- | ------------- | ------------- |
| alpine, default allocator | −15%          | −22%          |
| alpine + jemalloc         | −19%          | **−11%**      |
| alpine + mimalloc         | −17%          | −15%          |
| slim (glibc), baseline    | —             | —             |

**Answer: no, not primarily a malloc problem.** jemalloc recovers roughly
half the allocation-churn deficit (22%→11%); mimalloc about a third. The
arithmetic-loop gap (~15–19%, no allocation involved) is untouched by
_any_ allocator swap — that portion is musl/libc itself (`memcpy`, string
functions, dynamic linker / threading primitives), not `malloc`. Neither
allocator gets within striking distance of full parity. (Caveat: Alpine's
packaged mimalloc symlinks to the hardened/guard-page build, so upstream
mimalloc could do somewhat better than shown; single-run noise was
non-trivial — treat these as directional ratios, not absolutes.)

**Is the Dockerfile's CVE rationale still true?** Built the real
`backend/Dockerfile` as-is and a Debian/glibc mirror of it (same uv/
opentelemetry-bootstrap/appuser steps, `apt-get install git` in place of
`apk add git`; builds cleanly, no compatibility issues), ran
`trivy image --severity HIGH,CRITICAL` on both:

- **alpine (current): 0 findings**, 30 OS packages.
- **slim (mirror): 23 findings (19 HIGH / 4 CRITICAL)**, 87 OS packages,
  collapsing to ~6 distinct CVEs — all 4 CRITICALs in `perl-base`
  (regex miscompile, `Archive::Tar` symlink traversal, `Storable`
  integer overflow, heap overflow), the rest in the util-linux family
  (one CVE, `libblkid` partition-parser integer overflow) and ncurses
  (one CVE). **Fixed Version is empty on essentially every row** — this
  isn't a one-time triage, it stays red indefinitely without an ongoing
  `.trivyignore`.
- None of these packages are installed by, run by, or reachable from this
  headless FastAPI container (no perl scripts, no partition/mount
  operations, no interactive terminal). The Dockerfile comment's original
  reasoning holds verbatim.

**Decision: stay on Alpine, add jemalloc via `LD_PRELOAD`.** One-line
`ENV` change (`apk add --no-cache jemalloc`,
`ENV LD_PRELOAD=/usr/lib/libjemalloc.so.2`), recovers about half the
allocation-churn gap, zero CVE cost. Full parity with slim is not
achievable through allocator choice alone — closing the rest would require
the base-image switch, which buys a _permanent_ CVE-scan liability (23
always-red HIGH/CRITICAL findings needing a maintained suppression list)
against packages the app never touches. Per this project's own
no-silent-fallbacks stance, a perpetually-suppressed scan is worse than
the current honest zero. **Not revisiting the base-image question unless
C3's fix plus jemalloc still leaves the `<80ms`/`<400ms` budget missed for
reasons the profile shows are compute-bound**, not query-bound (see C2/C3
below — so far neither is).

Action: land the two-line jemalloc `Dockerfile` change alongside Track A
(it's independent, cheap, and already fully measured).

### C2. Recalc workflow profile

**Status: done**, on a local seed (`random_generator.seed_all`: 500 units,
12,000 modules, 804,798 data entries; factors seeded for 2025 only —
2023/2024 slices bail out with zero emissions and were excluded as
non-representative after being caught and re-run). Two valid measurements,
both headcount types (the only ones whose seeded `data` blobs matched
seeded factor classification codes closely enough to compute real
emissions — `process_emissions`, `plane`, `it` all produced 0-row bail-outs
against this seed and are excluded, not because they're cheap):

```
Recalc profile member/2025:  16684 entries in 38.9s (2.33 ms/entry) | validate=0.1 prepare=29.9 remainder=8.8
Recalc profile student/2025: 16862 entries in 40.7s (2.42 ms/entry) | validate=0.2 prepare=31.7 remainder=8.8
```

**`prepare` dominates — ~77% of wall time in both.** `validate`
(Pydantic `model_validate`) is under 1%; `remainder` (bulk DELETE+COPY
writes) is a steady ~22%. This settles the three-way split the section
originally posed:

- ~~`validate` dominates~~ — ruled out. Skipping the Pydantic round-trip
  in the loop is **not** the win the plan speculated it might be.
- **`prepare` dominates, confirmed** — factor resolution / handler
  `pre_compute` inside `prepare_create` is the primary cost, even with the
  slice-scoped `factor_query_cache` memo from plans 1661/310D already in
  place. Headcount fans out ~25 emission rows per entry (member/student
  wrote 417,100 and 421,550 rows respectively) — this may be close to a
  worst case rather than representative of every module type; one more
  data point from a non-headcount, non-bail-out combo would confirm that,
  but isn't blocking.
- ~~`remainder` dominates~~ — secondary but real at ~22%; not the primary
  lever.

**Implication for "another language":** this is a query/round-trip cost,
not a raw-arithmetic cost — a Rust or Go rewrite of the _formula_ layer
does nothing for `prepare`'s share, since the time is spent waiting on and
issuing DB round trips, not computing. See the closing section.

**Side finding, not part of this plan:** `backend/app/seed/random_generator/
seed_carbon_reports.py` has two `ON CONFLICT (col, col) DO NOTHING` clauses
targeting columns with no matching unique constraint (`carbon_projects` only
has partial unique indexes; `carbon_reports` has none on
`(carbon_project_id, year)`) — throws `InvalidColumnReferenceError` on a
fresh DB. Worked around locally to unblock seeding, not fixed here. Worth
its own small issue.

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

#### Findings — all four confirmed by measurement

Written against `app/services/simulator_plan_service.py`; measured with a
pytest suite (`backend/tests/unit/services/test_simulator_plan_reference_year_perf.py`,
not yet on this branch — written in an agent's disposable worktree, to be
brought over with the fix) using a `before_cursor_execute` statement
counter against an in-memory sqlite fixture. Statement counts are portable
evidence of the _shape_ of the bug (O(N) vs O(1) round trips); absolute
wall-clock numbers on sqlite don't transfer to pooled Postgres and aren't
cited as such below.

1. **`_recalculate_report_emissions` (line 649) is an N+1 per entry —
   confirmed, and it is O(entries), not O(1).** Isolated to this method
   alone: N=10→50 gave a 3.22× statement-count ratio; at production scale,
   N=200→8000 (a 40× entry increase) gave a **39.42× statement ratio** —
   essentially perfectly linear (40× would be exact). The `_recalculate_
report_emissions` in-loop `prepare_create()` call passes **no**
   `factor_resolver`, **no** `factor_query_cache`, **no** `slice_cache` —
   confirmed as the root cause, exactly the pattern plans 1661/310D removed
   from the recalc workflow but never migrated here.

   **Exact mechanism identified** (this is the concrete answer to "it's
   always the delete that pauses"): `upsert_by_data_entry` calls
   `DataEntryEmissionRepository.delete_by_data_entry_id` per entry, which
   **SELECTs the entry's existing emissions, then lets the ORM issue their
   DELETE separately** — two round trips per entry — rather than the
   set-based `delete_by_data_entry_ids` (plural) that `bulk_replace_for_
entries` already uses elsewhere in this same file. At N=8000, emission
   SELECT+DELETE alone is **50% of all statements issued**. Confirmed
   generic, not `process_emissions`-specific: reproduces identically
   against `purchase`/`scientific_equipment` entries (ratio 3.55 at
   N=10→50).

2. **`prefill_module_from_reference` queries the same rows twice —
   confirmed exactly.** Call-count instrumentation on `list_by_module`:
   2 calls for one `prefill_module_from_reference` invocation, matching
   the line-484 (emptiness check) / line-497 (copy loop) citation exactly.

3. **`_prefill_reference_modules` (line 359) fans out per module type** —
   not separately measured; subsumed by (1)'s per-entry cost across every
   module it touches.

4. **`_sync_year_reports` (line 209) fans out per year — confirmed,
   near-perfectly linear.** 2 years → 288 statements, 5 years → 711
   statements; ratio 2.47 vs. 2.5 for an exactly linear year-count
   multiplier. Setting a multi-year range with a reference year multiplies
   (1)–(3) by year count inside one PATCH, as predicted.

#### Fixes — confirmed, ready to implement

No longer "expected" — each is now backed by a measurement above:

- Give `_recalculate_report_emissions` the same shared `FactorResolver`,
  `factor_query_cache`, `prefetch_slice` and bulk replace that
  `_persist_prefill_entries` (line 599) and the recalc workflow already use.
  The batched version exists a few lines above in the same file — this is
  reuse, not new code. This is the primary fix; (1) above is ~77%-of-`
prepare`-shaped and the delete/insert round trips confirmed at 50% of
  statements at N=8000.
- Route the emission replace through the existing set-based
  `delete_by_data_entry_ids` (plural) instead of per-entry
  `delete_by_data_entry_id` — this is the specific fix for the confirmed
  SELECT+DELETE-per-entry mechanism above.
- Drop the duplicate `list_by_module` call (finding 2).
- Add the wall-time `asyncio.sleep(0)` yield used by the recalc workflow and
  `base_csv_provider.py:969`, so a long plan-year PATCH cannot starve
  `/healthz` and `/ready`. Directly relevant given A1/A4 — a
  `_recalculate_report_emissions` call currently holds the pooled
  connection and the event loop for its entire O(N) duration.
- Bring `test_simulator_plan_reference_year_perf.py` onto this branch as the
  regression test — it is written to fail today (proves the bug) and pass
  once the fixes land.
- If the request stays long after the above, move it behind the job runner
  (Track B) and return a job id rather than a synchronous result.

## Priority order

C1, C2, and C3's measurement phase are all now done (2026-08-12); this
reorders the remaining implementation work by confirmed value instead of
investigation order.

1. **A1** — bound `/ready`, drop Accred from it. Confirmed cause of the
   504s; availability, not throughput. Ship alone, ahead of everything.
2. **C1's jemalloc `Dockerfile` line** — fully measured, zero risk,
   independent of everything else; ship alongside A1.
3. **A2, A3** — rollout strategy, replica count, CPU requests.
4. **C3** — implement the confirmed fixes (shared `FactorResolver` +
   set-based delete in `_recalculate_report_emissions`, drop the duplicate
   `list_by_module`, add the yield, bring the regression test over). No
   longer speculative — this is the largest confirmed lever in the whole
   plan: O(N) round trips per PATCH, 50% of statements at N=8000 being a
   single avoidable SELECT+DELETE-per-entry pattern.
5. **B** — worker split (also resolves A4).
6. **C2's finding informs, but doesn't gate, anything further** — see
   below; no additional compute work is indicated by the measurement.

A0 runs alongside 1–3 as verification.

## On rewriting in another language

**The measurements argue against this more strongly than originally
anticipated, not less.** C2 found `prepare` (factor resolution / DB round
trips) dominates recalc at ~77% of wall time, with `validate`
(pure-Python Pydantic construction) under 1%. C3 found the request-path
cost is a round-trip count problem (O(N) SELECT+DELETE pairs), not a
compute problem. Neither is the "hot pure-Python loop" shape a language
rewrite helps with — a Rust or Go recalc engine would still issue the same
DB round trips at the same latency, because the bottleneck was never CPU
cycles spent computing; it was query count and connection-pool contention,
both of which C3's fix and Track B resolve without touching the formula
layer at all.

Pure-Python compute is typically 10–50× slower than Rust or Go for actual
CPU-bound arithmetic, but that gain applies to a share of the total time
that these measurements now show is small. Against that: reimplementing
the formula layer either duplicates the source of truth — the
drifted-published-number failure this project fears most — or means
porting all of it. **Closed, not just deferred**, unless a future profile
on a _different_ workload shows a genuinely compute-bound hot path this
plan didn't cover.

Expected stacking: A1 alone ends the 504s; C1's jemalloc line recovers
~11 percentage points of the alloc-churn gap for one line of Dockerfile;
A3 + B on a properly requested worker brings `dev` toward `dev2`
throughput (~2.4×); C3's fix removes an O(N)-round-trip N+1 that was 50%
avoidable SELECT+DELETE traffic at production scale — this is now the
single largest confirmed win in the plan.
