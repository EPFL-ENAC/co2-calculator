---
status: in-progress
issue: 2050
last_updated: 2026-08-17
title: "Backend compute performance — pod stability, worker split, request-path profiling"
summary: "Six-track plan against dev-platform slowness and intermittent 504s: bound /ready and move job dispatch off API pods (Tracks A/B, PR #2081); profile compute cost (Track C), which rules out a language rewrite; then fix the simulator-plan reference-year PATCH end to end — recalc and prefill N+1s, Pydantic's per-instance default_factory tax across every SQLModel table, Core INSERT…RETURNING, and Tracks D/E's redundant recomputes — taking it 960ms → 271.4ms (PRs #2083, #2152). Track F reopens the per-year prefill fan-out behind a 21.89s dev trace whose bottleneck is not traced SQL."
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

**Status: implemented, draft PR #2081** (`perf/2050-track-a-b-availability`).
A1–A3 below all shipped as written. Priority 1, three independent causes,
all cheap, all worth doing.

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

**Status: implemented, draft PR #2081** (`perf/2050-track-a-b-availability`,
alongside Track A). Corrected from the original design below during
implementation — kept here for the record.

Most of the infrastructure already existed: the unified runner
(`app/tasks/runner.py`), DB-polling dispatch (`_poller.py`), pod heartbeats,
claim/preempt, advisory locks, and the `RUN_BACKGROUND_POLLER` settings gate
(`app/core/config.py:452`).

**Design correction: a second, dedicated setting, not `RUN_BACKGROUND_
POLLER` reused.** The original plan below said "API pods set
`RUN_BACKGROUND_POLLER=false`" — building it exposed why that's wrong: the
test suite's autouse `disable_poller` fixture already sets
`RUN_BACKGROUND_POLLER=False` for _every_ test, while dozens of `_pg.py`
integration tests assert that `fire_and_forget(run_job(...))` still fires
inline. Reusing that flag for dispatch gating would have made every one of
those tests silently no-op. Production also needs the same split: worker
pods want (poller **on**, dispatch **on**); a post-split API pod wants
(poller **off**, dispatch **off**) — a different pairing than the test
suite's (poller off, dispatch on). Three of four combinations are
legitimately in use, so it's two axes, not one. Shipped as a new
`DISPATCH_JOBS_INLINE` setting instead (default `true`, preserving current
behavior everywhere untouched).

**Misconfiguration guard:** `DISPATCH_JOBS_INLINE=false` with no pod
running the poller leaves every job row `NOT_STARTED` forever — a silent
fallback the guardrails explicitly ban. Fixed at the Helm layer, not the
app layer: `worker.enabled` is the _only_ knob a deployer sets. When true,
`backend-deployment.yaml` appends an override pair
(`RUN_BACKGROUND_POLLER=false`, `DISPATCH_JOBS_INLINE=false` — last
same-named env entry wins in k8s) on top of `backend.env`'s static
defaults, and the worker Deployment sets both `true` unconditionally. The
dead combination can't be expressed in `values.yaml`.

Implementation:

1. All 6 (not 4 — two more direct-dispatch sites turned up at
   `data_sync.py:2075,2269` during implementation) `fire_and_forget(
run_job(...))` call sites now route through
   `fire_and_forget_or_defer_to_poller()` (`app/tasks/_background.py`),
   which either dispatches immediately or closes the coroutine unstarted
   and leaves the already-committed `NOT_STARTED` row for the poller.
2. `helm/templates/backend-worker-deployment.yaml` — new Deployment, same
   image, `worker.enabled=false` by default, no Service/ingress/readiness
   probe, liveness only, generous CPU/memory (`values.yaml`'s
   `worker.resources`).
3. The ~160-line secretKeyRef env block and the ES-CA volume/mount were
   extracted from `backend-deployment.yaml` into `_helpers.tpl`
   (`backendSecretEnv`, `backendSecretVolume(Mount)`) so backend and
   worker can't drift out of sync — necessary once a second Deployment
   needed the identical credential set.

Chained child jobs (`_chain.py:106,387`) fire in the process where the
parent ran, so they follow the parent onto the worker with no change —
confirmed correct, untouched.

Cost: enqueue-to-pickup latency of one `POLLER_INTERVAL_SECONDS`. Accept it
or lower the interval; do not reintroduce direct dispatch.

`worker.enabled` stays `false` in this PR — enabling the split on any real
environment is a separate, explicit follow-up change.

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

**Rerun with an OTel on/off test matrix (bare uvicorn vs
`opentelemetry-instrument uvicorn`)** — the production CMD wraps every
request in OTel auto-instrumentation, which every benchmark above ran
without. Real endpoint (`PATCH /api/v1/project-plans/{id}/years/{year}`,
local uvicorn against the seeded Postgres, 3×20s runs at concurrency 8):

| Variant                    | rps   | p50     | p95     | p99     | CPU% |
| -------------------------- | ----- | ------- | ------- | ------- | ---- |
| A — bare uvicorn           | 471.4 | 16.68ms | 21.42ms | 26.66ms | ~79% |
| B — OTel, exporters=none   | 295.6 | 26.27ms | 34.79ms | 51.85ms | ~77% |
| C — OTel, full OTLP export | 292.5 | 25.37ms | 37.35ms | 42.85ms | ~80% |

**B vs A: −37% throughput, +58–94% latency across p50–p99 — this app's own
OTel tax lands in the "30%+, investigate" bucket, not the "negligible"
range generic FastAPI writeups suggest.** C vs B is ~1%: the cost is
almost entirely instrumentation (spans + context propagation +
per-SQL-statement spans via SQLAlchemy auto-instrumentation), not
network/exporter overhead. CPU% stays flat across all three, meaning the
single event-loop core is already saturated everywhere — B/C aren't
waiting more, they're doing ~60% more work per request. One caveat: the
PATCH body used always matched the plan's current reference year, so
`set_reference_year`'s early-return (`report.reference_year !=
reference_year`) skipped the O(N) prefill/recalc path C3 fixes — this
measures routing + auth + Pydantic + a light DB read, a real endpoint but
not the heavy path.

Because the tax scales with SQL statement count (one span per statement),
it was partly inflated by exactly the N+1s C3 fixed — expect it to shrink
somewhat as a side effect of that fix, not just the raw round-trip count
dropping.

**Does this change the musl-vs-glibc call?** >5% threshold triggered, so
re-checked: `bench_alloc.py`'s allocation-churn workload wrapped in a real
(no-export) `TracerProvider` span per iteration, alpine vs slim:

| Workload              | alpine (musl) | slim (glibc) | ratio |
| --------------------- | ------------- | ------------ | ----- |
| alloc, no OTel        | 1.07 M/s      | 1.40 M/s     | 1.31× |
| alloc + OTel span tax | 0.104 M/s     | 0.130 M/s    | 1.25× |

Same direction, same rough magnitude — **the alpine-vs-glibc conclusion
above holds.** OTel's own tax (37% rps) dwarfs musl vs glibc (11–24%,
jemalloc recovers about half) as a lever; it deserves its own follow-up
issue (tuning `OTEL_PYTHON_EXCLUDED_URLS`, sampling, or scoping which
libraries get auto-instrumented) rather than staying folded into C1.
Caveats: measured on macOS arm64, not a k8s x86 alpine container — same
directional-not-absolute caveat the rest of C1 carries.

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

#### Status: refined — `prepare`'s cost is object construction, not queries

A follow-up pass instrumented `prepare_create`'s actual internal seams
(`resolve`, `emission_types`, `pre_compute`, `resolve_computations`,
`fetch_factors`, `apply_formula`, plus row-build) against the same
member/2025 slice. Every DB-adjacent stage was cheap and confirmed O(1)
per call, exactly as the cache/slice design intends —
`fetch_factors` (Strategy B, `factor_query_cache` hit): 0.13s / 417,100
calls; `pre_compute`: 0.01s total (headcount's handler is a no-op, no
per-entry query slipped through); `resolver.resolve`: 0.01s (short-circuits
instantly — headcount has no `kind_field`).

**Constructing the `DataEntryEmission(...)` row object itself
(`data_entry_emission_service.py:566-583`, once per factor × emission type
— ~25×/entry for headcount) is ~94% of `prepare`'s internal time and
~65-67% of total recalc wall clock** — 28.87s of 33.4s, ~69µs/call.
`DataEntryEmission` is `table=True` (a full SQLAlchemy-mapped +
Pydantic-validated model), and that construction/validation tax is paid on
every row even though `bulk_replace_for_entries` never `session.add()`s
these individual objects — they only feed a later bulk DELETE+COPY. So the
77%/22% `prepare`/`remainder` split from the first pass was accurate, but
the _composition_ assumed inside `prepare` (DB round trips) was wrong —
it's Python/ORM object-instantiation overhead, not waiting on Postgres.

**Not implemented, follow-up target**: accumulate a lightweight
dataclass/dict of column values in the hot loop instead of a real
`DataEntryEmission`, and only materialize the ORM/`table=True` model where
a row is actually persisted individually (the single-entry API path, which
does `session.add()` a real object and must keep doing so) — mirroring how
`factor_query_cache`/`slice_cache` already moved cost out of this loop for
the query side. Bulk callers (`bulk_replace_for_entries`'s COPY path) never
need the ORM identity at all.

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

#### Status: fixed — branch `perf/2050-simulator-plan-n1-fix`

The shared-resolver + set-based-delete fix above landed as planned, but
implementing it surfaced a **second, distinct per-entry N+1** that the
static reading behind finding (1) didn't catch — the regression test
written to pin the fix (N=200→8000) still showed a 36–39× statement ratio
after the planned fix alone, not the expected O(1).

**Root cause of the residual scaling**: every plan-year entry recalculated
by `_recalculate_report_emissions` is a prefill copy, and
`prefill_module_from_reference` stamps each copy's `data` with
`percentage_of_reference_year` and `source_data_entry_id` (finding 2's own
subject). `prepare_create` → `_get_percentage_override_kg` reads those
fields **per entry, per emission type**, on a completely separate path from
`factor_resolver`/`factor_query_cache`/`slice_cache` — the fix for finding
(1) never touched it. Its `source_data_entry_id` fast path costs one
`session.get(DataEntry, ...)` PK fetch + one `_sum_entry_emissions` sum
query per call; for headcount-shaped module types with several emission
types per entry this multiplies further. (The report-level lookup in the
same method was already safe — `DataEntryEmissionService.__init__` memoizes
`_get_report_for_data_entry` by `carbon_report_module_id` for the instance's
lifetime, so it was never the bottleneck.)

**Fix**: `DataEntryEmissionService.prefetch_percentage_override_cache(
entries, unit_id=...)`, called once per `_recalculate_report_emissions`
call (mirroring `factor_query_cache`/`slice_cache`'s existing shape). One
`SELECT ... WHERE id IN (:source_ids)` plus one `GROUP BY (data_entry_id,
emission_type_id)` sum query replace the per-entry PK fetch + sum for every
entry whose source belongs to the same unit (the existing cross-unit
ownership gate is preserved — sources are filtered against `report.
unit_id` before the cache is built; unit mismatches, an edge case, still
fall through to the original per-entry path, which re-checks and correctly
rejects them). `prepare_create` takes the resulting map as a new optional
`override_cache` param and checks it before hitting the DB.

**Measured after both fixes**: N=200→8000 statement ratio ~1.0 (222→222
non-INSERT statements; INSERT count scales 200→8000 but that is a SQLite-
only artifact — `DataEntryEmissionRepository.bulk_copy` falls back to
`session.add_all`+flush, one INSERT per row, off the `psycopg` COPY path;
production Postgres issues a single `COPY FROM STDIN` regardless of N, so
this doesn't reproduce there). A dedicated equivalence test asserts the
cached and uncached paths compute identical kg values, not just fewer
statements. Full backend unit suite (1974 tests) green.

#### 2026-08-17 — still 504ing in `dev`: findings #2 and #3 were never actually fixed

A production trace (`PATCH /v1/project-plans/8011/years/2025`, ~1000
entries, 504 after 91.5s) showed the C3 fix deployed but the bug still
present. Gap analysis on the trace (excluding the root span and deduping
the paired `psycopg`/SQLAlchemy spans per DB op) found two DB-silent
stretches: ~70.1s before the first captured span, and a further ~16.9s
CPU-only gap later in the request (73.6s→90.5s, between the last prefill
statement and `bulk_replace_for_entries`'s DELETE). The mandatory early
queries (`get_current_user`'s `users` lookup, `units`, `get_plan`'s
`carbon_projects`, the `reference_year` flush) are **absent from the trace
entirely** — early spans were dropped on export, so the first gap's
contents can't be read off the trace directly or attributed precisely: it
contains those dropped auth/plan/unit spans plus an unknown share of
`_prefill_reference_modules`, which is confirmed still running past the
70.1s mark (its `DELETE FROM data_entries` clear appears at 72.4s). What
_is_ attributable: the 1006 individual percentage-override sum queries
visible from 70.1s onward belong to prefill (see below), so prefill's own
N+1 is a real, confirmed contributor to that window — just not
necessarily all of it.

Rereading the code against that timing pointed at the two findings this
plan had already logged as still-open, both in `_prefill_reference_
modules`'s own call path — neither was in scope for the C3 fix above,
which only instrumented `_recalculate_report_emissions`:

- **Finding #2, actually still present.** The "Fixes — confirmed" list
  above named dropping the duplicate `list_by_module` call, but the
  "Status: fixed" note only landed the shared-resolver and override-cache
  fixes — finding #2's own fix never shipped. Confirmed still in the code:
  `prefill_module_from_reference` called `entry_repo.list_by_module(ref_
module.id)` once for the emptiness check and again for the copy loop.
  Fixed now: the copy loop reuses the already-fetched `src_entries`.
- **Finding #3, the actual dominant cost, never separately measured.**
  Finding #3 said `_prefill_reference_modules` fans out per module type and
  was "subsumed by (1)'s per-entry cost" — but (1)'s fix (the
  `override_cache` batching) only reached `_recalculate_report_emissions`.
  `_persist_prefill_entries` — the batched-looking helper both
  `prefill_module_from_reference` and `prefill_headcount_from_reference`
  call — builds a shared `FactorResolver`/`factor_query_cache`/
  `slice_cache` but never called `prefetch_percentage_override_cache` and
  never passed an `override_cache` to `prepare_create`. Every prefilled row
  carries `source_data_entry_id` (same shape finding #2's docstring
  already named), so every one of them re-triggered `_get_percentage_
override_kg`'s per-entry `session.get` + `_sum_entry_emissions` sum-query
  fallback — the exact N+1 C3 fixed for recalc, unfixed one call site over,
  and hit _first_ since prefill runs before recalc. The 1006 individual
  sum queries visible from 70.1s onward in the trace are this fallback,
  confirming it fired at production scale — a real, measured contributor
  to the DB-silent window, though (per above) not proven to be the whole
  70.1s.

  Fixed: `_persist_prefill_entries` now takes a `unit_id` and calls
  `prefetch_percentage_override_cache` once per invocation, mirroring
  `_recalculate_report_emissions`'s existing shape exactly. Regression
  test added (`test_prefill_reference_modules_isolated_statement_count`,
  isolating `_prefill_reference_modules` the way finding #1's tests
  isolate `_recalculate_report_emissions`): before this fix,
  `emission_selects` scaled 23→63 for a 10→50 entry increase; after, it's
  constant at 13 regardless of N (the remaining constant is one stats-
  rollup SELECT per reference-scoped module type touched, not per entry —
  finding #4's fan-out shape, not a new bug). `test_prefill_module_from_
reference_calls_list_by_module_once` (renamed from `..._twice`, finding
  #2) confirms the duplicate call is gone. Full backend unit suite (2066
  tests) green.

  **Not fixed by this update, still open**: the second gap (73.6s→90.5s,
  ~16.9s, no DB calls at all) sits inside `_prepare_recalc_emissions`'s
  pure-Python compute loop (factor resolution + formula application), not
  a query pattern this fix touches. It lines up with this plan's own
  Context table — `dev` measured ~72 rows/s, and ~1000 entries at that
  rate is ~14s — i.e. it's C2's ORM/Pydantic-construction finding, already
  logged above as unimplemented and lower-priority than C3. This PATCH
  still costs ~17s of unavoidable-today compute on top of whatever the
  prefill fix saves.

  Also outstanding from this same trace, not yet actioned: the response's
  final `http send` lands at ~91.5s — well past Traefik's default 60s
  timeout, so the backend kept computing and writing to the DB _after_ the
  client had already seen the 504. Combined with A4 (this PATCH holds a
  pooled connection and the event loop for its whole duration, no
  `asyncio.sleep(0)` yield — see C3's intro above), a client retry on top
  of the still-running original request is a plausible double-write path
  worth checking before this is called closed. Track A/B (move this off
  the request path
  entirely) remains the durable fix; this update only removes two more
  N+1s from the synchronous path in the meantime.

#### 2026-08-17 (same day, follow-up) — `DataEntry` construction had the same tax as `DataEntryEmission`, plus a general fix

After landing the prefill `override_cache` fix above, a fresh local trace of
the same PATCH (smaller plan, ~360ms total) still showed one dominant cost:
a 136ms DB-silent gap immediately followed by a 94ms `INSERT INTO
data_entries` (2 calls) — together ~63% of the request — inside
`prefill_module_from_reference`'s copy-construction step, before
`_recalculate_report_emissions` even starts.

**Root cause, one level up from finding #1's `DataEntryEmission` fix**:
Pydantic v2's `resolve_default_value`/`takes_validated_data_argument` calls
`inspect.signature()` on every `default_factory` on **every model
instantiation** (not cached per-field) to check whether it takes a
`validated_data` argument. For a bare C builtin (`dict`,
`datetime.utcnow`) that lookup is expensive and always fails — measured
directly: ~4µs/call for `dict`, ~20µs/call for `datetime.utcnow` (5×
worse), versus ~2µs for a trivial Python-level wrapper function. `DataEntry`
has three such fields (`data: dict`, `created_at`/`updated_at: datetime`),
each paying this on every prefill copy — the same class of cost finding #1
found in `DataEntryEmission`, just never looked for elsewhere.

Confirmed the sqlite test harness was hiding this: `DataEntryEmissionRepository.bulk_copy`'s
non-psycopg fallback still builds real ORM objects, so profiling against
sqlite showed no improvement from the finding #1 fix. Re-profiled against a
throwaway local Postgres database instead (`co2_prof`, dropped after
measuring) — the only way to exercise the real `COPY FROM STDIN` path.

**Fix**: added `app/models/_field_defaults.py` (`default_dict`,
`default_list`, `default_utcnow` — trivial wrapper functions) and swapped
every bare-builtin `Field(default_factory=dict|list|datetime.utcnow)` across
`app/models/` to use them — 12 occurrences across `audit.py`,
`year_configuration.py`, `data_ingestion.py`, `data_entry.py`,
`data_entry_emission.py`, `factor.py`. (The dataclass `field(default_factory=...)`
calls in `data_entry_emission.py`'s `FactorQuery`/`EmissionComputation`/
`DataEntryEmissionRow` are stdlib `dataclasses`, not Pydantic — unaffected
by this mechanism, left untouched.)

**Measured** (Postgres, `set_reference_year`, N=1000 entries):
633.5ms → 474.7ms (−25%). `sqlmodel_table_construct` cumulative time
0.177s → 0.069s; `inspect.signature`/`_signature_fromstr`/`__build_class__`
disappeared from the profile entirely. Remaining cost at this scale is
`select.kqueue`/socket I/O (round-trip latency) and psycopg query
preparation — round-trip-bound, not Python-construction-bound. Full backend
unit suite (2012 tests) green; lint/type-check clean.

**Confirmed against a live trace** — re-ran the same PATCH locally
(GlitchTip export, same plan/entry count both times): 364.9ms → 323.75ms.
The gap before `INSERT INTO data_entries` shrank 136.1ms → 107.6ms and the
INSERT itself 47.2ms → 27.6ms avg per call, but that combined chunk was
still ~50% of the request — smaller, not gone. Confirmed via the `INSERT`
statement's byte length (identical, 214,311 chars) that both traces were
the same workload, not a smaller batch giving a false win.

#### 2026-08-17 (same day, second follow-up) — the remaining gap was `DataEntry` ORM construction itself, not `default_factory`

The `default_factory` fix only removes signature-introspection overhead;
`prefill_module_from_reference`/`prefill_headcount_from_reference` still
built a real `DataEntry(...)` (`table=True`) instance per prefilled row and
`session.add()`ed it one at a time — paying SQLAlchemy's own mapper/
instance-state machinery (`_initialize_instance`, `cascade_iterator`,
instrumented-attribute `__setattr__`) regardless. Unlike
`DataEntryEmission`, these rows _do_ need real ids back immediately
(`source_data_entry_id`, `prepare_create`'s `data_entry.id` guard,
`entry_ids` for the recalc that follows) — the reason they couldn't just
route through `bulk_copy` (never populates ids) the way emissions did.

**Fix**: `DataEntryRepository.bulk_insert_returning_ids(rows: list[dict])`
— a Core-level (not ORM) `INSERT ... RETURNING id`, `rows` as plain
column-value dicts, `sort_by_parameter_order=True` so returned ids line up
with input order (this is SQLAlchemy's documented contract for this, not
something reproduced as broken locally without it — checked to N=2000
against Postgres/psycopg, order held either way on this stack; kept the
flag as the correct guarantee regardless, pinned with a regression test
using a distinguishing marker per row). `prefill_module_from_reference`/
`prefill_headcount_from_reference` now build plain dicts, bulk-insert, and
wrap the returned ids as `DataEntryResponse` (not `DataEntry`) —
`_persist_prefill_entries` and everything downstream (`prepare_create`,
`prefetch_percentage_override_cache`, `prefetch_slice`) already accepted
`DataEntryResponse` via their existing `DataEntry | DataEntryResponse`
union types, so no other signature changes were needed. No `DataEntry(...)`
ORM instance or `session.flush()` in the whole prefill copy path anymore.

**Measured** (Postgres, N=1000): 474.7ms → 395.6ms (−17% more; −38.5%
total from the 633.5ms starting point three fixes ago).
`sqlmodel_table_construct` is gone entirely from the profile now.
**Confirmed against a live trace** (same plan, re-verified via the
`INSERT` statement's byte length again): 323.75ms → 203.55ms. Gap before
`INSERT` 107.6ms → 8.1ms; `INSERT` itself 27.6ms avg → 25.1ms avg (now
genuine Postgres execution time for the batch, not Python construction —
this is close to a floor for INSERT+RETURNING at this row count).
Regression test added (`test_bulk_insert_returning_ids_preserves_row_order`,
`tests/unit/repositories/test_data_entry_repo.py`). Full backend suite
(2014 tests) green; lint/type-check clean.

**What's left at 203.55ms**: no single dominant cost anymore — spread
across the INSERT itself (~50ms, likely near-floor), ~20 small per-
module-type SELECTs (`list_by_module`-shaped, ~1ms avg each, could be
batched into one bulk fetch across module types — the same "N+1 across
module types, not entries" shape as the `get_by_report_and_module_type`
double-lookup below, estimated ~15-20ms if fixed), a `get_module` call
for both the plan and reference module per module type
(`prefill_module_from_reference`/`prefill_headcount_from_reference` each
re-fetch what `_prefill_reference_modules` already read into `rebuilt` for
the plan side — genuinely redundant, but only ~5ms total measured, not
worth the refactor on its own), and several small per-module-type gaps
(~40ms combined) not yet individually attributed. None of these have the
single-item leverage the last three fixes did — this is genuine
diminishing-returns territory; further gains need either accepting the
INSERT floor or moving the work off the request path entirely (Track B).

## Track D — round-trip count, not query speed (implemented 2026-08-17)

An outside review of the 203.55ms trace argued the real problem is
statement _count_, not per-statement speed, and proposed a "load once →
calculate → write once" rewrite of the whole request. The count claims
checked out **after correcting a mistake in how I first read them** (see
below); the sweeping rewrite doesn't — two concrete, narrowly-scoped fixes
account for the actual redundancy without touching the pipeline's shape.

**Correction, for the record**: my first pass at re-verifying the reviewer's
table said it was double-counting the paired psycopg/SQLAlchemy spans (the
mistake I'd made and been corrected on earlier this same session). It
wasn't — filtering on the span that actually carries `db.statement`
reproduces their numbers exactly: **117 SELECT, 24 UPDATE, 9 DELETE, 6
WITH, 1 INSERT = 157 statements, ~93ms of the 203.55ms request.** Flagging
the correction rather than quietly fixing my own analysis, since I'd
already stated the wrong version with confidence.

**What's real, verified against the actual call graph** (not just pattern-matched from the trace):

1. **`_clear_module_entries`'s upfront scope duplicates 7 of 8 modules' own
   self-clear.** `_prefill_reference_modules` calls `_clear_module_entries`
   for all 8 `PLANNER_REFERENCE_SCOPED_MODULE_TYPES` up front (line 405),
   which deletes their entries **and** recomputes their stats to reflect
   "now empty." But `prefill_module_from_reference`/
   `prefill_headcount_from_reference` — called next, for 7 of those 8
   (everything except `purchase`, which is wiped but never rebuilt) — each
   do their **own** `bulk_delete_by_modules([plan_module.id])` first
   (documented as "destructive and idempotent," a real, load-bearing
   contract: these are the only two callers, but it's public API on the
   service). The upfront clear-and-recompute for those 7 modules is
   thrown away within the same transaction, never observable (nothing
   commits until the whole PATCH finishes) — pure waste.

   **Fix**: narrow `_clear_module_entries`'s call at line 405 to
   `scoped - rebuilt` (just `purchase`) instead of all of `scoped`. Zero
   behavior change — `prefill_module_from_reference`/
   `prefill_headcount_from_reference` still delete-then-rebuild their own
   modules exactly as before; only the redundant upfront pass for the
   ones about to be rebuilt anyway goes away.

2. **`_persist_prefill_entries`'s per-module `recompute_stats_many` is
   thrown-away work for one of its two callers, load-bearing for the
   other — a blind removal would silently break the second one.**
   `_prefill_reference_modules` has two callers:
   - `set_reference_year` → always followed by `_recalculate_report_emissions`,
     which recomputes stats for **every** module touching **any** entry of
     the report (`list_by_carbon_report`) — including every module
     `_persist_prefill_entries` just freshly computed stats for, moments
     earlier, in the same transaction. That per-module call's result is
     immediately superseded and never observed. This is the caller behind
     the trace above — the actual "recompute the same module 2-3 times"
     shape the review flagged.
   - `_sync_year_reports` (new plan-year creation, `update_plan`) → only
     calls `recompute_report_stats` (report-level rollup) afterward, **not**
     `_recalculate_report_emissions`. For this caller,
     `_persist_prefill_entries`'s per-module recompute is the _only_ thing
     that ever computes those modules' stats — removing it would ship plan
     years with stale/never-computed module stats, a real regression the
     existing test suite may not catch (worth checking before touching
     this).

   **Fix**: thread a `skip_module_stats: bool = False` (or similar) through
   `_persist_prefill_entries` → `prefill_module_from_reference` /
   `prefill_headcount_from_reference`, set `True` only from
   `_prefill_reference_modules` when its caller is `set_reference_year`
   (i.e., when a subsequent `_recalculate_report_emissions` is guaranteed).
   This is the single biggest lever in Track D — potentially removing
   ~7 of the ~24 UPDATE-triggering `recompute_stats_many` calls and a
   meaningful share of the 117 SELECT (each call's internal machinery —
   module load, grouped emissions, grouped count, FTE, years-by-report,
   report rollup — costs several statements even batched).

**What's in the review but not yet verified to this standard** — real
patterns, not yet root-caused to a specific fix, so not sized or promised:
repeated `get_module`/`get_report`-shaped re-fetches crossing service
boundaries beyond the one instance measured above (~5ms, not worth its own
refactor); whether the ~20 per-module-type `list_by_module` SELECTs could
collapse into one bulk fetch across module types grouped in Python.

#### Status: implemented — both fixes, 2026-08-17

`_clear_module_entries`'s scope narrowed to `scoped` modules not in
`will_rebuild` (finding 1); `skip_module_stats` threaded from
`set_reference_year` through `_prefill_reference_modules` →
`prefill_module_from_reference`/`prefill_headcount_from_reference` →
`_persist_prefill_entries` (finding 2), applied only to the non-empty
branch's final `recompute_stats_many` — the empty-`entries` branch stays
unconditional, since a module that ends up with zero rows after prefill
never appears in `_recalculate_report_emissions`'s later entry-driven
module set and would otherwise keep stale stats.

Both edge cases the naive versions of these fixes would have gotten wrong
are pinned with regression tests, verified to actually fail without their
fix (not just pass trivially): `test_set_reference_year_grant_clears_but_
does_not_rebuild_rf_and_travel` (a grant report's reference-year RF/travel
entries would get wrongly copied back in if the upfront-clear exclusion
also skipped rebuilding them) and `test_persist_prefill_entries_empty_
branch_ignores_skip_module_stats` (the empty branch must run regardless of
the flag). Full backend suite (2016 tests) green; lint/type-check clean.

**Measured** (Postgres, N=1000): 346.7ms, down from 395.6ms before these
two fixes — `recompute_stats_many` call count 129 → 95.
**Total from this Track D's own starting point** (the 203.55ms live trace
before any of today's fixes): not yet re-measured against a fresh trace at
this small a scale (the two fixes' win is real but modest per-request at
low module/entry counts — most of the removed work was already cheap
individually; the win compounds with report size and module count, same
as every fix in this plan).

**What I'd reject from the review, and still would after implementing the
narrow version**: the "load everything → calculate in memory → one write"
rewrite of the whole request. It's the right shape for a green-field
design, and the review's _diagnosis_ — round-trip count, not query speed,
is the problem — was correct and is now fully acted on by this plan's C3,
Track D, and the `default_factory`/Core-INSERT fixes: every real win this
whole plan found came from cutting round trips or redundant work, never
from speeding up a slow query (none were ever found). But retrofitting the
rewrite's _prescription_ here means restructuring
`_prefill_reference_modules`'s per-module-type loop, `prepare_create`'s
per-entry emission computation, and `recompute_stats_many`'s aggregation
all at once — the exact "recalculation/pipeline internals" the guardrails
require a maintainer-reviewed written plan for — for a payoff not
demonstrably larger than what the narrow, two-caller-aware version just
measured. Track D's finding 2 alone is a concrete illustration of the
risk: the "obviously redundant" recompute had a second caller
(`_sync_year_reports`) with no later recalc to cover it — a blind
rewrite following the review's shape would very plausibly have shipped
that regression, since nothing in the review's trace-based analysis could
have surfaced a code path the trace itself never exercised. The pattern
holds generally: this session's series of fixes (N+1, `default_factory`,
Core INSERT, Track D) delivered the review's own diagnosis — round trips
960ms → ~350ms, roughly 64% — through several small, independently
reviewable, low-blast-radius changes, each with its own regression test.
A rewrite gets the same diagnosis addressed at once, but bets it on a
single large, harder-to-review change to code where a wrong bet costs a
drifted published carbon number — the worst failure this project defines
for itself. Same destination, and the incremental path is not slower to
arrive — it is verifiably not, since it already has.

**If more is wanted past 346.7ms**: incremental, not a rewrite — batch
`list_by_module` across module types (flagged above, not yet sized);
re-evaluate whether Track B (async job runner) is warranted for the
largest plans specifically once the INSERT-execution floor (~50ms at
N=1000, genuine Postgres write time) is the dominant remaining cost, since
no amount of round-trip reduction removes that.

## Track E — the actual optimal shape (implemented 2026-08-17)

Requested directly: "write me down the todo/steps for the optimal
optimization — in my head it's two SQL requests." Two isn't literally
reachable (see the honest floor at the end), but there's a real lever here
bigger than anything in Track D, found by taking that framing seriously
instead of stopping at Track D's fix.

**The finding**: Track D's finding 2 only skipped the _stats_ half of
`_persist_prefill_entries`'s wasted work for `set_reference_year`. The
_emissions_ half — `prepare_create`'s factor resolution and formula
computation, C2's own profiling measured at ~65-77% of recalc wall time —
is still computed and written during prefill, then immediately
overwritten by `_recalculate_report_emissions`'s subsequent full-report
pass, which has to recompute every entry anyway (it also covers
`purchase`'s manual rows and anything else prefill never touches). This is
the same "computed here, superseded there" shape as finding 2, just for
the more expensive half. Verified nothing reads emissions in the gap
between the two calls in `set_reference_year` — `_year_read` runs after
both, off the final stats — so skipping it is as safe as finding 2 was.

`_sync_year_reports` (new plan-year creation) is the mirror image: its own
code comment already says why it never calls `_recalculate_report_
emissions` — "no other entries exist yet," so prefill's own compute _is_
the one necessary pass there. Confirmed by reading the callers, not
assumed: this is exactly the two-callers trap Track D finding 2 already
hit once this session.

### TODO

**Tier 1 — skip prefill's emission compute entirely for `set_reference_year`
(the big lever, do this first)**

1. Add a `compute_emissions: bool = True` parameter to
   `prefill_module_from_reference`/`prefill_headcount_from_reference`
   (mirrors `skip_module_stats`'s threading exactly, same call sites).
   When `False`, skip straight past `_persist_prefill_entries` — call
   `_bulk_insert_entries(rows)` and return; no `prepare_create` loop, no
   `override_cache`/`factor_query_cache`/`slice_cache` setup, no
   `bulk_copy` for emissions, no stats recompute (subsumes finding 2 —
   `skip_module_stats` becomes redundant once emissions aren't computed
   either, since there's nothing to compute stats from yet).
2. `_prefill_reference_modules` forwards `compute_emissions` the same way
   it forwards `skip_module_stats` today.
3. `set_reference_year` passes `compute_emissions=False`.
   `_sync_year_reports` keeps the default (`True`) — unchanged behavior,
   verified necessary above.
4. Once this lands, `skip_module_stats`/the empty-branch special case in
   `_persist_prefill_entries` can be deleted, not just left unused — per
   this file's own guardrail (no backward-compat paths): for
   `set_reference_year`, `_persist_prefill_entries` is never called at
   all anymore; for `_sync_year_reports`, it always runs in full, so the
   flag has no remaining caller to serve.
5. Regression test: mirror
   `test_persist_prefill_entries_empty_branch_ignores_skip_module_stats`'s
   monkeypatch-and-count approach, asserting `prepare_create`/`bulk_copy`
   are never called when `compute_emissions=False`, and a full
   `set_reference_year` still ends with correct final emissions (via
   `_recalculate_report_emissions`) — an equivalence test like
   `test_percentage_override_cache_matches_uncached_path`, not just a
   call-count assertion, since this is exactly the kind of change where
   "fewer statements" must not mean "different numbers."
6. Re-measure against Postgres (N=1000 harness already exists) before
   touching anything else — this alone may make Tier 2 not worth doing.

**Tier 2 — consolidate reads/writes across module types (smaller, do only
if Tier 1's numbers still justify it)**

7. Replace the per-module-type `get_module(report.id, type)` /
   `get_module(ref_report.id, type)` pair in `prefill_module_from_
reference`/`prefill_headcount_from_reference` with the `list_modules`
   result `_prefill_reference_modules` already has in hand for the plan
   side, plus one `list_modules(ref_report.id)` call for the reference
   side (currently zero calls there — always refetched per type).
8. Replace the per-module-type `list_by_module(ref_module.id)` with one
   `SELECT * FROM data_entries WHERE carbon_report_module_id IN (all ref
module ids)`, grouped by `carbon_report_module_id` in Python — the
   grouping headcount already needs internally (member/student → SIUS
   bucket) becomes a second grouping pass over the same fetched rows,
   not a second query.
9. After Tier 1, prefill's only remaining per-module-type work for
   `set_reference_year` is building row dicts and inserting them — flatten
   the row-building across all rebuilt module types into one list, one
   `bulk_insert_returning_ids` call, instead of one call per type.
10. Regression tests: statement-count assertions in the same style as
    `test_prefill_reference_modules_isolated_statement_count`, updated for
    the new shape.

**Honest floor — why not two**: read-then-compute-then-write is
inherently ≥2 round trips for anything needing values back before the next
step (RETURNING ids from the entry INSERT are needed before emissions can
reference them — a real FK dependency, not an artifact of how this code
happens to be structured). DELETE and INSERT can't be one statement
either. After both tiers, the realistic floor for `set_reference_year` is
roughly: 1 read (plan + ref modules, mergeable into one round trip with a
union or two cheap indexed lookups) + 1 read (reference entries, all
module types) + 1 write (bulk delete) + 1 write (bulk insert entries,
RETURNING ids) + `_recalculate_report_emissions`'s existing pass (itself
already near-optimal per C3: 1 read of the report's entries, 1 write for
emissions, 1-2 for stats rollup) — call it **8-10 total SQL operations**
for the whole PATCH, regardless of module or entry count, down from the
current ~150. Not two, but the same order of magnitude of ambition, and
the actual number that would show up in a fresh trace once both tiers
land — worth stating precisely rather than rounding to a slogan.

#### Status: implemented — both tiers, 2026-08-17

**Tier 1** (steps 1-6): `compute_emissions: bool = True` threaded through
`prefill_module_from_reference`/`prefill_headcount_from_reference` →
`_prefill_reference_modules` → `set_reference_year` (passes `False`) /
`_sync_year_reports` (keeps default `True`, verified necessary by reading
its own code comment before touching anything). `skip_module_stats`
(Track D finding 2) deleted, not left dead — with `compute_emissions=False`
skipping `_persist_prefill_entries` entirely, there was nothing left for
it to gate. The empty-`entries`/empty-`rows` edge case (a module that
ends up with zero rows after prefill must still get its stats refreshed,
regardless of `compute_emissions`) is preserved in both
`prefill_module_from_reference` (early return, unconditional, unchanged)
and `prefill_headcount_from_reference` (new `elif not rows:` branch, since
its `_persist_prefill_entries` call — and therefore that branch — no
longer runs at all when `compute_emissions=False`).

**Tier 2** (steps 7 only — 8/9 not done, see below): `plan_module`/
`ref_module` optional params added to both prefill methods, defaulting to
their old self-fetching `get_module` behavior when omitted (preserves
standalone callability — `test_prefill_rebuilds_the_module` still calls
`prefill_module_from_reference` directly with no caller-supplied modules,
unchanged). `_prefill_reference_modules` now does one `list_modules` for
the reference side (it already had the plan side) and passes both
pre-fetched modules into every rebuilt module type's call — zero
`get_module` calls during a full prefill, down from two per module type.

Steps 8 (batch `list_by_module` across module types) and 9 (flatten the
row-insert across module types) **not implemented** — they need either
duplicating `prepare_create`'s per-type grouping logic outside the public
per-module-type methods, or restructuring those methods' public contract,
neither of which the measured win (below) justified pursuing today.

Every edge case has a regression test verified to fail without its fix
(not just pass trivially — each was broken and re-run to confirm):
`test_set_reference_year_never_calls_persist_prefill_entries`,
`test_sync_year_reports_still_calls_persist_prefill_entries` (the mirror —
tier 1 must not have broken the caller it wasn't meant to touch),
`test_set_reference_year_produces_correct_emissions_without_prefill_compute`
(actual kg values, not just call counts — skipping computation must not
skip _correctness_), `test_prefill_headcount_empty_after_prefill_still_
recomputes_stats`, `test_prefill_reference_modules_never_calls_get_module`.
Full backend suite (2020 tests) green; lint/type-check clean.

**Measured** (Postgres, N=1000): tier 1 alone 346.7ms → 302.1ms (−13%);
tier 1 + tier 2 step 7 → 271.4ms (−10% more). `_prepare_recalc_emissions`/
`prepare_create` no longer appear anywhere in `_prefill_reference_modules`'s
call tree — the only remaining call site is `_recalculate_report_emissions`,
exactly once, as intended. Dominant cost is `select.kqueue` (round-trip
wait) and psycopg query preparation — round-trip-bound, same conclusion as
Track D, at a lower floor.

**Total, from this file's very first N=1000 measurement to now**: 1298ms
(sqlite, pre-#2050) → 633.5ms (Postgres, C3 override-cache fix) → 474.7ms
(`default_factory`) → 395.6ms (Core INSERT) → 346.7ms (Track D) → 302.1ms
(Track E tier 1) → **271.4ms (Track E tier 1+2) — a 71.7% reduction from
the 960ms this investigation actually started at** (the first live-trace
number, before any fix). Confirmed against live traces at every stage
this session, not just isolated profiling.

## Track F — the per-year fan-out, and an 18.5s gap that isn't SQL

Opened 2026-08-17 after two new reports: an 11-year plan-range `PATCH
/v1/project-plans/{plan_id}` at 3144ms locally, and a **21.89s**
`PATCH /v1/project-plans/{plan_id}/years/{year}` on dev.

### F0 — read the dev trace before rewriting anything

The 21.89s dev trace (`954e5976…c3e298`, one single year) decomposes as:

|                                                       |                              |
| ----------------------------------------------------- | ---------------------------- |
| Wall clock                                            | 21885.3ms                    |
| DB spans                                              | 241                          |
| Sum of all DB time                                    | 2776.5ms                     |
| **Largest single gap with zero _traced_ DB activity** | **18486.0ms** (at t+169.8ms) |

84% of that request is one contiguous stretch with no _traced_ database
activity. The plan behind it carries ~50k equipment entries across 10
years, i.e. ~5k entries in the single year this request prefilled.

**That window is not idle, and it is not purely Python.** Scanning all 37
distinct statement shapes in the trace: there is no `INSERT INTO
data_entry_emissions` anywhere — only `DELETE`s and `SELECT`s against
that table. The request unquestionably wrote emission rows. `bulk_copy`
writes them through `COPY FROM STDIN` (`cursor.copy()`), which OTel's
psycopg instrumentation does not trace, unlike `execute`/`executemany`.

So the 18.5s window contains **at least one uninstrumented bulk write in
addition to the Python compute loop**, and this trace cannot apportion
between them. An earlier draft of this section claimed the 84% was pure
Python per-entry compute and used that to argue query batching was
finished as a lever; that claim was not supported and has been removed.

What the trace does establish:

- Only 2776.5ms of 21885.3ms is _traced_ SQL, so further round-trip
  batching is a bounded lever at best.
- The unaccounted ~19.1s is some mix of Python emission compute and
  untraced `COPY`. **Which one dominates is unknown, and is the single
  most important open question in this track** — it decides whether F3
  (stop computing in Python) or write-volume reduction is the right
  attack.

**Do not sequence F2/F3/F4 off this trace alone.** The discriminating
experiment is cheap and local — and has now been run (below).

#### Status: measured, 2026-08-17 — Python compute is _not_ the bottleneck

Rig: throwaway local Postgres, fresh DB per run, `set_reference_year`
against a reference year holding N entries, with `_prepare_recalc_emissions`
(Python compute) and `bulk_replace_for_entries` (DELETE + untraced `COPY`)
timed separately, and a hard assertion that emission rows were actually
written — a factor that fails to resolve produces zero emissions and makes
every number meaningless, which is exactly how an earlier attempt in this
investigation was confounded.

| N    | wall    | traced SQL    | Python compute | DELETE+COPY | rest    |
| ---- | ------- | ------------- | -------------- | ----------- | ------- |
| 200  | 112.7ms | 69.6ms (115)  | 11.2ms         | 5.1ms       | 96.4ms  |
| 1000 | 180.9ms | 105.5ms (115) | 31.3ms         | 13.2ms      | 136.4ms |
| 5000 | 560.9ms | 308.1ms (119) | 132.2ms        | 62.5ms      | 366.2ms |

**At 5k entries the whole request is 560.9ms locally, and Python emission
compute is 132.2ms of it — 24%.** The `COPY` write is 62.5ms (11%).
Traced SQL is 308.1ms (55%) across just 119 statements, so the cost is
per-statement volume (5k-row transfers), not round-trip count.

This settles F0's open question, and it does **not** favour F3:

- F3 removes the Python compute. Locally that is a **~24% win, not 84%.**
- Statement count is already flat in N (115 → 119 from N=200 to N=5000),
  so Tracks D/E did their job; there is no N+1 left to find here.

Caveat, stated plainly: the rig uses `process_emissions` entries, which
resolve to **one** emission leaf each. Equipment — the module type behind
the 21.89s trace — may produce several leaves per entry, scaling both the
Python compute and the `COPY` row count by that factor. That shifts the
24% share upward. Re-running the rig with a multi-leaf module type is the
obvious refinement.

#### Correction, 2026-08-17: the dev/local ratio computed here was invalid

An earlier version of this section divided the local 5k wall clock into
the 21.89s dev trace, derived a "~75x slower non-SQL" figure, and
concluded the cause was **CPU throttling on the API pod**. Both the
number and the conclusion were wrong, and they are withdrawn.

The comparison was confounded three ways: the local rig runs
**post-Track-D/E** code, the dev trace ran **pre-fix** code (the branch
was not merged); the rig uses **`process_emissions`** (1 emission leaf per
entry), the dev trace was **equipment** (likely several); and entry counts
were not matched. Nothing that ratio claimed survives.

The trustworthy numbers are the pre-existing platform benchmark — same
dataset (8,453 entries), same build, varied only by environment:

| Environment                  | App throughput | CPU benchmark |
| ---------------------------- | -------------- | ------------- |
| Local MacBook M4 + docker PG | ~384 rows/s    | 19.25 M it/s  |
| K8s `dev2` (EPYC 9124)       | ~174 rows/s    | 10.73 M it/s  |
| K8s `dev` (Xeon Gold 6242)   | ~72 rows/s     | 5.93 M it/s   |

So dev is **~5.3x slower than local on app throughput** against a
**~3.25x slower CPU** — old hardware, not a misconfiguration. **There is
no cgroup CPU limit**: both pods report `cpu.max = max 100000`, which
disproves the throttling hypothesis directly. That benchmark also rules
out Postgres and network latency: `dev2` scores ~180 rows/s against K8s PG
and ~174 against IT-CENTRAL, i.e. DB location barely moves the number.

The ~1.6x that CPU speed does **not** explain (5.3x observed vs 3.25x
CPU) is the genuinely open question — candidates are node CPU contention,
vCPU allocation, container/runtime differences, and OTel's instrumentation
tax, which C1 measured at ~37% throughput. Track F's application-level
work does not address any of these.

Two secondary factors, each scaling the constant rather than the
algorithm:

- **CPU limits on the API pod.** A low k8s CPU quota inflates the Python
  share directly. Track B (move job execution off the API pods) was meant
  to relieve exactly this — **verify #2081 is live on dev.**
- **Dropped spans.** 246 spans is low; a shed collector batch would change
  the split again.

### F1 — buildings room lookups (fixed, 2026-08-17)

`BuildingRoomModuleHandler.pre_compute` did one `building_rooms` point
lookup **per entry** — 364 selects / 188.1ms on the 11-year local trace,
64 on the dev trace. It was the one handler with a per-entry lookup and
no `prefetch_slice` override; travel has had one since plan 310D.

Fixed by mirroring travel exactly: `prefetch_slice` bulk-loads the
slice's rooms in one `IN` query, `pre_compute` reads them from
`slice_cache` and keeps its per-entry fallback for single-entry
create/update (which has no slice). Fixes both the prefill path and the
recalc workflow, since both call `prefetch_slice`. Regression test
verified to fail without the fix.

### F2 — the prefill path defeats its own batching

On the 11-year local trace, four query shapes fire **exactly 114 times**
each (module select, entry count, emission sum, module update). That is
`recompute_stats_many` — whose own docstring says it exists to replace
"N sequential `recompute_stats` calls (~8 queries per module)" — being
called **once per module with a single-element list**, ~10 modules ×
11 years. Same story for `FactorResolver` + `factor_query_cache`, which
`_persist_prefill_entries` constructs fresh per module per year: ~110
cold caches per request, and `factors` is the largest single bucket at
381 calls / 435.4ms.

`set_reference_year` already has the right shape — it prefills rows with
`compute_emissions=False`, then runs **one** `_recalculate_report_emissions`
for the whole report, which shares one resolver/cache/override-cache
across every module and ends with a single batched
`recompute_stats_many(all module ids)`. `_sync_year_reports` is the only
remaining caller still computing per-module.

**Proposed:** give `_sync_year_reports` the same shape —
`_prefill_reference_modules(report, compute_emissions=False)` followed by
`_recalculate_report_emissions(report)`. This is a deletion, not a new
path: it makes `compute_emissions` always-`False`, which in turn lets
`_persist_prefill_entries` be removed entirely. The
`recompute_report_stats(report_read.id)` call after it also becomes dead,
since `recompute_stats_many` already ends in
`recompute_report_stats_many` over the distinct parent reports.

Verify first that `resolve_factor_year(report)` returns the same year
`_persist_prefill_entries` passed (`report.reference_year`) — it does for
any report with a reference year set, which is the only branch that
prefills, but the equivalence is the whole safety argument.

#### Status: implemented + measured, 2026-08-17

`_sync_year_reports` now mirrors `set_reference_year`: prefill inserts the
copied rows, then one `_recalculate_report_emissions` computes the whole
report. Both callers behave identically, so `compute_emissions` and
`_persist_prefill_entries` were **deleted** rather than left as a dual
path (73 lines gone, no behaviour branch retained).

Measured on the 10-plan-year creation path against real Postgres, varying
how many module types actually hold entries:

| populated module types |        | statements | wall         |
| ---------------------- | ------ | ---------- | ------------ |
| 1 (500 entries x 10y)  | before | 1198       | 1080.3ms     |
|                        | after  | 1218       | 1187.3ms     |
| 4 (200 entries x 10y)  | before | 1408       | 1452.7ms     |
|                        | after  | **1108**   | **1351.2ms** |

**The win scales with populated module count, and at one module type it is
a regression** (+20 statements, +107ms) — `_recalculate_report_emissions`
re-fetches the report's entries and issues a `DELETE` for emissions that
do not exist yet on a brand-new report, which the per-module path skipped.
At four module types that overhead is repaid several times over: **-300
statements (-21%)** and -101ms.

Real plan years populate up to eight module types, so the four-type row is
the representative one — but the single-module case is a genuine small
regression and is recorded here rather than averaged away.

**The statement count is the number that matters, and local wall clock
understates it.** Dev pays ~9-17x per round trip (F0), so -300 statements
is worth roughly 1.2-3s there against ~130ms locally. The redundant
`DELETE` on fresh reports is a known, unfixed remainder — worth folding
into F3, which removes that path entirely.

### F3 — the copies are identical across years (verified)

Prefill copies the _same_ reference-year entries into every plan year, at
100%, and computes them all with `year = reference_year`. Three checks
confirm the per-year work is genuinely redundant, not merely similar:

- `resolve_factor_year` returns `report.reference_year` whenever it is
  set — identical for all 10 plan years.
- `_get_percentage_override_kg`'s `base_year` uses `report.reference_year`
  when set, never `report.year`.
- No module handler reads `data_entry.year`; the compute path takes
  `year` as an explicit parameter.

So the emissions computed for 2027 are byte-identical to those for
2028…2036. Only ids, `carbon_report_module_id` and the stored `year`
differ. The exception is grant equipment, which prefills at 0% (#1981).

This is what makes the "two SQL statements" instinct correct:

1. `INSERT INTO data_entries (…) SELECT …` from the reference modules,
   remapping `carbon_report_module_id`/`year`, `RETURNING id`.
2. `INSERT INTO data_entry_emissions (…) SELECT …` joined to those new
   ids — copying the reference year's **already-computed** emission rows
   rather than recomputing them.

Nothing round-trips through Python. Per year this is O(1) statements
instead of O(modules × entries), and the recompute collapses to one
`recompute_stats_many` over every module of every year.

#### Status: verified numerically safe, but it is not a drop-in — 2026-08-17

Ran the equivalence check the guardrails demand before touching anything
that produces published numbers: prefill a plan year from a reference year
holding computed emissions, then diff every copied entry's emission rows
against its source's, **row for row** — not totals, since a copy could
match on total while splitting the value across different leaves.

Result on 5 entries at 100%: `kg_co2eq`, `emission_type_id` and `scope`
match **exactly**. The arithmetic behind F3 is sound.

One field differs: **`primary_factor_id` is `None` on the recomputed copy
and set on the source.** The override short-circuit
(`_get_percentage_override_kg`) returns kg directly and never resolves a
factor, so prefilled planner rows currently carry no factor provenance.

That single delta is what stops F3 being the two-statement change it was
written as:

- An `INSERT … SELECT` would carry the source's `primary_factor_id`
  through. `data_entry_repo.py:871-952` joins that column to `Factor` for
  rollups and listings, where it currently yields `NULL` for every planner
  row. So F3 would **change user-visible listing output** as a side effect
  of a performance change.
- **Grant equipment prefills at 0%** (#1981) — copying the source's rows
  is simply wrong there, so it needs its own branch.
- **Plain-copy modules** (professional travel) carry no
  `source_data_entry_id` at all, so there is nothing to join to.

Three branches, one of which alters displayed data. And F3's original
premise has partly been consumed: **F2 already removed the per-year,
per-module redundancy** by routing new plan years through one batched
`_recalculate_report_emissions`. What remains for F3 is the Python compute
(F0 measured it at 132.2ms of 560.9ms, ~24%) plus the row transfers —
worthwhile, but not the dominant term the earlier draft implied.

**Open decision for the maintainers, and it is not a performance
question:** _should prefilled planner emission rows carry their source's
`primary_factor_id`?_

- **Yes** → that is a deliberate data-provenance improvement. It ships on
  its own, with tests covering the affected rollup/listing queries, and
  F3 then follows cleanly on top.
- **No** → F3 must null the column on copy, which makes it a fast-path
  duplicate of the compute layer — two ways to produce an emission row,
  i.e. exactly the dual source of truth the guardrails forbid.

Until that is answered, **F4 is the better next move**: it is required at
the stated ceilings regardless of how fast the synchronous path becomes,
and it does not touch emission values at all.

### F4 — sizing: at the stated ceilings, this needs a job

Per reference year, the stated maxima are ~6,990 entries (equipment 3000,
purchase 3000, travel 300, buildings 300, external cloud/AI 300,
headcount 30, research facilities 30, process 30) — **~70,000
`data_entries` for a 10-year plan**, plus several emission leaves each,
so roughly 150k–350k `data_entry_emissions` rows. The plan behind the
21.89s trace already sits near that ceiling on equipment alone (~50k
entries across 10 years).

F3 removes the Python per-entry cost, but not the write volume: even at a
healthy 20–30k rows/s `COPY`, 150k–350k emission rows is 10–20s of pure
insert. **No synchronous HTTP request survives the ceiling case**, however
well optimized.

So the two are complementary, not alternatives:

- **F3 makes the common case fast** — small and mid-size plans stop being
  O(years × entries) in Python and become a couple of set-based inserts.
- **F4 makes the ceiling case survivable** — above a row-count threshold,
  prefill enqueues rather than blocking, using the existing
  data-ingestion job pattern (return 202, report progress, let the UI
  poll). This is the "job/pipeline route", and at 50k equipment entries
  it is not avoidable by optimization.

Recommended order, **revised after F0's measurement**:

1. **Accept dev's CPU as a fixed constraint.** The platform benchmark
   shows old hardware (~3.25x slower CPU), no cgroup limit, and DB/network
   already ruled out. There is no infrastructure fix pending here, so the
   remaining lever genuinely is "do less work" — which is what F3 is.
2. **F2** — a deletion, immediate, removes the last per-module cold
   cache. Small but free.
3. **F4** — the job route. At the stated ceilings this is required
   regardless of how fast the synchronous path gets (see below), and it
   is the only item that survives the 50k-equipment case.
4. **F3** — the two-statement rewrite. F0 sized its compute half at ~24%
   locally, but that undersells it: F3 also removes the 5k-row transfers
   that make up most of the 308ms of traced SQL, because nothing
   round-trips into Python at all. It is a considered refactor of
   recalculation internals and needs the two-maintainer sign-off, but on
   fixed-CPU hardware it is the single largest remaining application-side
   lever.

#### Design, decided 2026-08-17

Branch: stays on `perf/2050-track-f-prefill-batching` -> `dev` (lead's
call, overriding the pipeline-branch default). Both endpoints in one
slice. Async is **unconditional** — no row-count threshold, so there is no
dual contract to maintain.

**The async boundary is the prefill work, not the whole request.** A plain
rename must not become a polled operation, so each endpoint keeps its
synchronous metadata change and defers only the expensive part:

| endpoint                        | stays synchronous                 | deferred to the job           |
| ------------------------------- | --------------------------------- | ----------------------------- |
| `PATCH /{plan_id}`              | plan fields, report create/delete | prefill + recalc of new years |
| `PATCH /{plan_id}/years/{year}` | `reference_year` write            | prefill + recalc of that year |

Both responses gain **`prefill_job_id: UUID | None`**. That is one
contract, not two: `null` means nothing to wait for, non-null means poll
then refetch. A threshold would instead have made the response type itself
conditional, which is the dual path the guardrails forbid.

**Job shape** — reuses existing infrastructure, no migration:

- `job_type = "simulator_plan_prefill"`, registered like every other
  handler.
- `entity_type = GLOBAL_PER_YEAR` (3) — already exists for jobs not scoped
  to a module, so **no `ALTER TYPE` on the append-only `EntityType` enum**.
- `module_type_id` / `data_entry_type_id` stay `NULL`, so under Postgres'
  `NULLS DISTINCT` the "one current per combo" partial unique index never
  fires — two plans prefilling concurrently cannot collide.
- `meta["config"] = {"plan_id": ..., "report_ids": [...]}`.

**Idempotency on retry** is free: prefill is already destructive and
idempotent (each module is delete-then-rebuild), so a re-run after a pod
crash converges rather than duplicating rows — the property #1559 and the
310-series require of every handler.

**Constraints taken from the required reading**, not invented here:

- The handler must leave `job_session` clean; #1219's stage incident was a
  poisoned session escaping the handler and self-propagating a stall.
- Jobs run under `MAX_CONCURRENT_JOBS` with heartbeat/preemption (#1723),
  so the handler must be async end to end — a sync wrapper calling
  `asyncio.run` would cancel the fire-and-forget task.

**The frontend ships in the same PR**, per the no-backward-compat rule:
without it, setting a reference year returns an empty year and looks like
a silent failure. Visible "prefill running" state, poll, refetch on
completion, strings in both `en-US` and `fr-CH`.

#### Status: implemented, 2026-08-17

Backend:

- `simulator_plan_prefill` handler (`app/tasks/simulator_plan_tasks.py`),
  registered in `bootstrap.py`. Raises rather than finishing "successfully"
  on an empty `report_ids` — a job that silently does nothing would leave
  the plan year empty with no error anywhere.
- `_sync_year_reports` and `set_reference_year` now return the report ids
  needing prefill instead of doing the work; `prefill_reports()` is the
  handler's entry point and is idempotent on retry.
- Both routes enqueue via `_enqueue_prefill` and stamp `prefill_job_id`.
- `GET /project-plans/{plan_id}/prefill/{job_id}` for polling, gated by the
  plan's own access check **and** by matching the job's `plan_id` — the
  admin data-sync job routes are the wrong permission surface for a plan
  editor waiting on their own PATCH.
- No migration: `EntityType.GLOBAL_PER_YEAR` already existed.

Frontend:

- The store polls, then refetches; the two `timeout: 300000` workarounds
  are gone (one carried a `TODO: backend to make a background task
instead!` — this is that task).
- `pollUntilPrefilled` extracted as a pure function with an injected
  `sleep`, so the wait is testable without timers or HTTP. Backs off
  500ms -> 3s.
- Banner while the copy runs, in `en-US` and `fr-CH`.

Tests: 4 handler tests (registration, config plumbing, both failure
modes), 2 service tests (prefill is deferred, not run inline; retry
converges instead of duplicating), 3 poll tests (immediate return,
repeat until finished, backoff ceiling). Full backend unit suite 2040
passed; frontend `test-ct` 396 passed.

**Known gap:** the year sections are visibly empty while the job runs. The
banner says so, but a large prefill leaves a real "building" window — if
that reads badly in practice, per-year progress is the follow-up.

### F6 — the job path itself (implemented 2026-08-17)

F4 moved prefill off the request, but the work still costs what it costs —
on dev that job is the 21.9s. Profiled it directly on local Postgres with
a per-shape statement breakdown, 10 plan years x 4 populated module types.

**What the split looks like after F4:**

|                                   | wall       | SQL                 |
| --------------------------------- | ---------- | ------------------- |
| Request (what the user waits for) | **66.6ms** | 45.6ms (116 stmts)  |
| Job (background)                  | 1148.4ms   | 632.8ms (660 stmts) |

The request went **1351ms -> 66.6ms**, a 20x cut in what the user
experiences. The rest is the job's.

**Two redundancies found and fixed in the job:**

1. **The reference side was re-read once per plan year.** Every plan year
   copies from the _same_ reference report, yet the job re-fetched that
   report, its module list, and — the expensive part — all of its entries
   for each year: 40 of 90 `list_by_module` calls were the same rows read
   ten times. A per-job `_ReferenceCache` collapses them (90 -> 27).
2. **`recompute_stats_many` was called once per module, again.** Same
   defect F2 fixed one level up: each module prefill left empty issued its
   own single-module call. Batched. Then the upfront clear and the
   prefill-emptied set turned out to be the same case (neither appears in
   the recalc's entry-driven module set), so they share one call — which
   keeps the report rollup behind it to one run per report instead of
   three.

**Result: 991 -> 660 job statements (-33%)**, SQL 761ms -> 633ms, wall
1295ms -> 1148ms. Statement count is the number that travels to dev, where
each round trip costs 9-17x more.

**What is left, in time order:**

| shape                             | n   | ms    | note                                         |
| --------------------------------- | --- | ----- | -------------------------------------------- |
| `INSERT INTO data_entries`        | 40  | 248.5 | row volume (8000 rows), not overhead         |
| `SELECT carbon_report_modules`    | 141 | 61.4  | 14 per report, metadata                      |
| `SELECT carbon_reports`           | 112 | 46.8  | 11 per report, metadata                      |
| `SELECT data_entries` (reference) | 27  | 72.3  | already cached; the rest is real reads       |
| `DELETE FROM data_entries`        | 80  | 31.3  | one per module — batchable to one per report |

The INSERT dominates on time and is irreducible without F3 (which would
make it an `INSERT … SELECT` that never leaves the database). The 80
per-module `DELETE`s are the clearest remaining count win, but moving the
clear up changes `prefill_module_from_reference`'s documented
delete-then-rebuild idempotency, so it wants its own change rather than
riding along here.

### F5 — on porting an endpoint to Rust

Asked directly, 2026-08-17, given that dev's CPU cannot be upgraded and
OTel is staying: would porting a `project-plans` PATCH to Rust help?

**No — and F0 is the measurement that decides it**, satisfying the exact
condition the "On rewriting in another language" section left open ("a
future profile on a different workload showing a genuinely compute-bound
hot path"). That profile came back at **24% Python compute**, so:

- A _perfect_ Rust port of the compute layer is capped at ~24% by Amdahl,
  before accounting for any FFI or process-boundary cost.
- It does not touch the 308ms (55%) of traced SQL, because Rust still has
  to fetch 5k rows, compute, and write them back.
- **F3 strictly dominates it.** F3 removes the Python compute _and_ the
  row transfers — a larger win, in less time, with no new language and no
  second implementation of a carbon formula. Two implementations of a
  formula drift, and a drifted published number is the failure this
  project fears most.

If a Rust number is still wanted, the right shape is a **standalone
microbenchmark of the emission-formula loop only** — no endpoint, no DB,
no FastAPI. That answers "how much faster is this arithmetic in Rust" in a
day, and cannot become a second source of truth.

F3 is a proposal, not a queued task: it replaces work inside
`_recalculate_report_emissions`, not just prefill, which makes it
recalculation internals — the guardrails require a written plan reviewed
by both maintainers before it is touched. Nobody should build it off this
track alone.

## Priority order

C1, C2, and C3's measurement phase are all now done (2026-08-12); this
reorders the remaining implementation work by confirmed value instead of
investigation order.

1. ~~**A1** — bound `/ready`, drop Accred from it.~~ **Done** — draft PR
   #2081.
2. **C1's jemalloc `Dockerfile` line** — fully measured, zero risk,
   independent of everything else; still open, ship whenever.
3. ~~**A2, A3** — rollout strategy, replica count, CPU requests.~~ **Done**
   — draft PR #2081.
4. ~~**C3** — implement the confirmed fixes (shared `FactorResolver` +
   set-based delete in `_recalculate_report_emissions`, drop the duplicate
   `list_by_module`, add the yield, bring the regression test over).~~
   **Done** — branch `perf/2050-simulator-plan-n1-fix`. Was the largest
   confirmed lever in the plan: O(N) round trips per PATCH, 50% of
   statements at N=8000 being a single avoidable SELECT+DELETE-per-entry
   pattern, plus a second per-entry N+1 (percentage-override lookup) found
   only once the first fix's own regression test still showed O(N) scaling
   — see C3's status note above. **Follow-up done 2026-08-17**: the same
   percentage-override N+1 and the duplicate `list_by_module` call were
   still live in `_prefill_reference_modules`'s own path
   (`_persist_prefill_entries`), which this fix never touched — see the
   2026-08-17 status update above. The `asyncio.sleep(0)` yield is still
   outstanding.
5. ~~**B** — worker split (also resolves A4).~~ **Implemented, disabled by
   default** — draft PR #2081 ships `worker.enabled=false`; flipping it on
   any real environment is a separate follow-up.
6. ~~**C2's follow-up finding** — ~65-67% of recalc wall clock is
   `DataEntryEmission(...)` ORM/Pydantic construction on rows that are never
   individually persisted.~~ **Done**, same day as the C3 follow-up above:
   `prepare_create` (shared by the recalc workflow and both simulator-plan
   paths) now builds `DataEntryEmissionRow` — a plain dataclass — instead,
   materializing a real ORM row only at the two call sites that genuinely
   `session.add()` one (`create`, `upsert_by_data_entry`). Surfaced a second,
   general instance of the same tax (Pydantic's per-instance
   `default_factory` signature introspection, not specific to
   `DataEntryEmission`) — fixed across every `table=True` model in
   `app/models/`, not just this one.
7. **C1's OTel rerun found a bigger, separate lever than musl vs glibc** —
   instrumentation alone costs this app ~37% throughput / +58-94% latency
   (span-per-SQL-statement overhead, not export cost). Doesn't change the
   Alpine decision, but deserves its own follow-up issue (scoping which
   libraries get auto-instrumented, sampling, `OTEL_PYTHON_EXCLUDED_URLS`)
   — a bigger single lever than C1's jemalloc line or C2's ORM-construction
   finding on its own, and — since the tax scales with SQL statement count
   — one that C3's fix already shrinks as a side effect on the endpoint it
   touches, without anyone having to tune OTel to get that partial win.

8. ~~**D** — the two redundant-recompute findings (upfront module-clear of
   modules that self-clear during rebuild; per-module stats recompute
   superseded by a later full recalc).~~ **Done 2026-08-17** — branch
   `perf/2050-simulator-plan-track-d-e`, PR #2152. 346.7ms → 302.1ms.
9. ~~**E** — tiers 1 and 2: `set_reference_year` skips prefill's own
   emission compute entirely (`compute_emissions=False`), and
   `_prefill_reference_modules` batches its `get_module` calls into one
   `list_modules` per side.~~ **Done 2026-08-17**, same branch/PR.
   302.1ms → **271.4ms**, closing a 960ms → 271.4ms chain (-71.7%).
   Tiers 8/9 (batch `list_by_module` and flatten row-inserts across module
   types) remain proposals — estimated ~3-8ms local / ~15-40ms dev, a
   guess rather than a measurement.
10. **F** — the per-year fan-out, reopened 2026-08-17 by an 11-year
    plan-range PATCH at 3144ms local and a 21.89s `/years/{year}` on dev.
    F1 (buildings `prefetch_slice`) is **done**; F2 is a queued deletion;
    F0's local 5k-entry measurement gates F3 vs. write-volume work; F4
    (the job route) is required for the stated ceilings regardless. See
    Track F for why this is not simply "more of Track E".

A0 runs alongside 1–3 as verification.

## On rewriting in another language

**The measurements argue against this more strongly than originally
anticipated, not less — but the reasoning changed with C2's follow-up
pass.** `prepare` dominates recalc at ~77% of wall time, with `validate`
(pure-Python Pydantic construction) under 1% — but `prepare`'s own cost
turned out to be ~94% ORM/Pydantic **object construction**
(`DataEntryEmission(...)`, `table=True`), not DB round trips as first
assumed; every DB-adjacent stage inside it (`fetch_factors`, `pre_compute`,
`resolver.resolve`) measured as cheap and O(1), confirming the existing
cache/slice design works as intended. C3 separately found the request-path
cost is a round-trip count problem (O(N) SELECT+DELETE pairs plus, once
found, an O(N) percentage-override lookup) — a genuine compute problem, not
a hot pure-Python loop.

That object-construction cost **is** CPU-bound Python/framework overhead —
the kind a rewrite generically helps with. But porting it isn't the
indicated fix: the objects being expensively constructed are never
individually persisted (`bulk_replace_for_entries` COPYs them), so the
actual fix is architectural — stop building the full SQLAlchemy-mapped
model in the hot loop, keep it only where the API path truly
`session.add()`s one — not a language port of the formula layer. That
targeted fix, still unimplemented (see C2's status note above), is
strictly cheaper than a rewrite and doesn't touch — let alone risk
duplicating — the formula source of truth.

Pure-Python compute is typically 10–50× slower than Rust or Go for actual
CPU-bound arithmetic, but that gain applies to a share of the total time
that these measurements now show is small, and is better captured by the
targeted fix above than by porting the formula layer. Reimplementing it
either duplicates the source of truth — the drifted-published-number
failure this project fears most — or means porting all of it. **Closed,
not just deferred**, unless a future profile on a _different_ workload
shows a genuinely compute-bound hot path this plan didn't cover.

Expected stacking: A1 alone ends the 504s; C1's jemalloc line recovers
~11 percentage points of the alloc-churn gap for one line of Dockerfile;
A3 + B on a properly requested worker brings `dev` toward `dev2`
throughput (~2.4×); C3's fix removes an O(N)-round-trip N+1 that was 50%
avoidable SELECT+DELETE traffic at production scale — this is now the
single largest confirmed win in the plan.
