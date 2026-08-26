---
status: in-progress
issue: 2049
last_updated: 2026-08-26
title: "Optimize Pipeline/Report Performance — what remains after the v3 investigation"
summary: "Updated 2026-08-26. The v3 trace investigation is finished and its alerting half shipped as #1402. The caching, batching, upload-auth and http.route work has since merged (#2280, #2266, #2265), and #2220 is closed. What is left: confirm the win with one measurement, the OTel instrumentation tax, the remaining ops/alerting items, and three gated changes. Ten claims are corrected here - read those first; two of them retire proposals this plan itself made."
---

# Optimize Pipeline/Report Performance — what remains

Rewritten 2026-08-22, replacing the verbatim v3 investigation dump. That
document did its job: it drove ~15 PRs and its alerting half is live. What
it is now is mostly **history plus several claims we've since disproved**,
which makes it actively misleading to work from. The full v3 text is in
this file's git history if you need to challenge a number; the measurements
worth keeping are in [Appendix A](#appendix-a-measured-evidence).

## Status — 2026-08-26

**Shipped since the 2026-08-22 rewrite:** `#2280` (taxonomy cache +
cross-pod invalidation + batching), `#2266` (upload auth-before-body),
`#2265` (`http.route` dual-write), ops `#13` and `#15`, plus the `#2360`
series removing duplicate and eager frontend fetches. `#2220` is **closed**
— root-caused to a laptop claiming the shared dev DB's jobs, not S3.

**The next step is a measurement, not a merge.** Two independent workstreams
have now cut the report page's request count (`#2280` batching, `#2360`
de-duplication), and nobody has re-counted. Reload the report page, read the
XHR count and wall time, and compare against the 31-request / 2064 ms
baseline in [Appendix A](#appendix-a-measured-evidence). **That number
decides whether most of what follows is still worth doing** — in
particular it may retire A1, C1 and C2 outright, since the per-request
floor only mattered when it was paid ~31 times.

**Dropped:** B2 (batching `modules/{m}/{sub}`) — see its entry for why, and
for the trap to re-read if it is ever revived.

## Scope

**In:** backend performance — DB connection pool, the per-request floor,
OTel instrumentation cost, request fan-out, pipeline execution time.

**Not here:**

- **Alerting and dashboards → [#1402](1402-trim-down-alerting.md).** Done
  and live in dev+stage (ops repo PRs #8–#11 merged). `route_class` exists,
  streams/uploads/jobs are out of the normal-API latency alert, the
  deadman and error-rate rules are fixed.
- **Factors query caching → [#2258](https://github.com/EPFL-ENAC/co2-calculator/issues/2258)**
- **Route/`http.target` collisions → [#2260](https://github.com/EPFL-ENAC/co2-calculator/issues/2260)**
- **Upload path → [#2261](https://github.com/EPFL-ENAC/co2-calculator/issues/2261)**,
  sibling route bug **[#2267](https://github.com/EPFL-ENAC/co2-calculator/issues/2267)**
- **S3 404s / storage decision → [#2220](https://github.com/EPFL-ENAC/co2-calculator/issues/2220)**,
  written up in [2220-s3-vs-pvc-storage.md](2220-s3-vs-pvc-storage.md)

## Corrections to v3 — read before trusting anything it said

Per v3's own output contract ("Contradictions: put this first").

1. **"The `.*upload.*` matcher is probably a no-op" (§2 reason 1) — REFUTED.**
   `http_target` _is_ present and populated on
   `http_server_duration_milliseconds`, and `/api/temp-upload` does contain
   "upload", so the old exclusion **did** exclude uploads. It was never a
   no-op; it filtered the wrong thing. §2 reason 2 is the real one: uploads
   are 1.1% of request-time, streams were 95%.

2. **"Derive `route_class` from `http_route`" (§4.3) — REFUTED.**
   `http_route` never appears on this metric under the default semantic
   conventions. `route_class` is derived from `http_target` instead.

3. **"No connection pooling" (§1.8) — REFUTED (already by v3.1).**
   The pool exists and works: `connect` is a pool _checkout_ costing
   0.4–1.3 ms, and the `;` span nested inside it is `pool_pre_ping` doing a
   network round trip. **Consequence: v3's "Done when: zero `connect` spans
   inside request spans" checklist item is wrong and is struck** — it would
   have us "fix" correct code and delete the very signal that verifies the
   pool.

4. **"Probes have never been measured" (§1.6, §3.1b) — REFUTED for metrics.**
   `/api/healthz` and `/api/ready` both appear in
   `http_server_duration_milliseconds`. `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS:
"/api/health"` is empirically a **no-op** — if it matched, those series
   wouldn't exist. Probable mechanism: kubelet hits the pod directly at
   `/healthz`, and the `/api` prefix exists only in the _synthesized_
   `http.target` (see correction 7). **P0-6 is therefore answered**, and
   after ops #11/#12 probes are `route_class="probe"` with their own panel.
   ⚠️ That no-op is load-bearing — "fixing" it would delete probe metrics
   and with them the head-of-line-blocking canary.

5. **"Is `users (institutional_id, provider)` indexed?" (§3.5b) — ANSWERED,
   and the implied fix is wrong.** `institutional_id` is already
   `unique=True, index=True` (`backend/app/models/user.py:343`). A composite
   index would add nothing: uniqueness on the first column already reduces
   the scan to one row. So 15.2 ms (idle) → 71.7 ms (burst) on that lookup
   is **network RTT + DB load**, not a missing index — the same ~5× burst
   amplification the pre-ping probe shows independently. The fix is to stop
   making the round trip at all (caching), not to add an index.

6. **NEW — the `/api`-prefix bug has a third instance.** The collector's
   `tail_sampling` `drop-health` policy matches `http.target` exactly
   against `/health`, `/healthz`, `/ready`; real values are `/api/healthz`,
   `/api/ready`. Exact match fails, and with `invert_match: true` the trace
   is **kept**. Probe traces are being exported to Tempo on every probe
   interval, on every pod, when the intent was to drop them. Same bug class
   as the alert exclusion and the chart-default `filter` processor, both
   already fixed.

7. **Root mechanism of the `/api` collapse — CONFIRMED** (from #2265, with a
   live repro against this repo's pinned `fastapi==0.141.1`).
   `opentelemetry-instrumentation-asgi`'s `_collect_target_attribute` builds
   `http.target` as `f"{root_path}{scope['route'].path_format}"`. FastAPI's
   dispatcher (`fastapi/routing.py`, `_handle_selected`) sets
   `scope["route"]` to `effective_context.original_route` — the **leaf**
   `APIRoute` as declared on its own sub-router, _before_ any ancestor
   `include_router(prefix=...)` folds a prefix in. `root_path` is a separate
   static ASGI-scope value, untouched by routing — which is exactly why
   `/api` survives and `/v1/<router-prefix>` doesn't.
   **Corollary found the same way:** `GET /v1/units` and `GET /v1/connectors`
   declare their leaf path as `""` — falsy, so `_collect_target_attribute`
   returns `None` and those endpoints emit **no `http.target` at all**.
   Silently invisible to any target-keyed dashboard or alert, which is worse
   than a collision.

8. **NEW — C3's premise ("streams are probably being cut today") is
   WRONG, twice over.** Established by reading the ops repo and the
   chart, 2026-08-22.
   **(a) It is an inactivity timeout, not a total-duration cap.**
   `haproxy.router.openshift.io/timeout` sets HAProxy's `timeout server`,
   which HAProxy defines as "the maximum inactivity time on the server
   side". Every byte written resets it. Our SSE streams emit on a ~2.015 s
   poll and, since `#2262`, a keepalive bounds the silent gaps — the
   worst measured gap was 16.2 s. A 30 s **inactivity** timeout is
   unreachable for a stream that never goes 30 s without a write, at any
   total duration.
   **(b) The measurement itself is the counter-example.** The 201.6 s
   pipeline stream was recorded on **stage**, which has **no** timeout
   override (see the table in C3), and it ran to completion and closed
   with 200. If a 30 s cap applied, that trace could not exist.
   The **real** finding underneath C3 is different and smaller:
   **stage and prod lack the annotation dev has** — config drift, not a
   live incident. See C3 for the per-environment table.

9. **NEW — the pipeline task modules are in `app/tasks/`, not
   `app/workflows/`.** `runner.py`, `_chain.py`, `_pipeline_reconciler.py`,
   `_locks.py` and the `*_tasks.py` handlers all live in
   `backend/app/tasks/`. `backend/app/workflows/` holds only the three
   compute workflows (`emission_recalculation.py`,
   `carbon_report_module.py`, `embodied_energy.py`). C4 named the wrong
   directory; corrected there.

## Delivered

| Task      | What shipped                                                                                                                                                        | Where                              |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| T2        | `factors` root-caused: 846 vs **20,915** rows → result-set size, not a missing index. Cache + cross-pod invalidation                                                | `#2280` **merged**                 |
| T3/T4     | `route_class` in the collector; streams/uploads/jobs out of the normal-API latency alert                                                                            | ops `#9`–`#11` **merged**          |
| T5        | `event_loop_lag_seconds` probe                                                                                                                                      | `#2263` **open**                   |
| T6 (half) | Taxonomy fan-out batched, 16 → 5 calls per page load                                                                                                                | `#2280` **merged**                 |
| T7 (part) | SSE keepalive + `Cache-Control`/`X-Accel-Buffering`; heartbeat gap off-by-one (`>=15` unreachable on a 2 s poll → fired at 16 s, the exact gap it existed to close) | `#2274` **merged**                 |
| T9        | Alert rules: 5xx-only error rate + traffic floor, `absent()` deadman, `PodHighCPU` disabled with reasoning, `repeatInterval` 24h                                    | ops `#8` **merged**                |
| T10       | Auth-before-body (DoS surface closed), size limit enforced, `http.request_content_length`                                                                           | `#2266` **merged**                 |
| —         | S3 404s **fully root-caused and closed**: a laptop running `make dev` against the shared dev DB was claiming jobs and resolving files locally. Boot guard shipped   | `#2349` **merged**, `#2220` closed |
| —         | `http.route` dual-write, so observability can stop tail-matching `http.target`                                                                                      | `#2265` **merged**                 |
| —         | Handled S3 pre-check 404s no longer flagged as ERROR spans                                                                                                          | ops `#16`                          |
| —         | Duplicate/eager frontend fetches removed (explore page, factors, carbon-report)                                                                                     | `#2360` series **merged**          |

Deliberately **not** built, with reasoning recorded: `Last-Event-ID` (both
streams re-derive full state on every poll, so the failure mode it prevents
doesn't occur here) and the job/pipeline not-found contract asymmetry (real,
but no demonstrated defect and it would break a live consumer).

## Remaining work

### A. Blocked on data only a human can pull

**A1 — Is the pool actually being exhausted?** (was P0-1b, gates B1, C1, C2)
Open the "DB Pool Usage" Grafana panel during a report-page load and read
whether `checked_out` pins to the `size` line. One screenshot. v3 predicts
it does: `pool_size` 15 (+5 overflow on dev/stage) against a ~31-request
fan-out each holding a connection for a 1338 ms query. **This is the single
highest-leverage five minutes available** — two P1 tasks are explicitly
sequenced behind it.

**A2 — `pool_pre_ping`: keep or drop.** Needs `SHOW max_connections` and
the DBaaS idle-timeout policy. Measured cost: 103 pre-pings = 220.7 ms
across one 201 s stream, 80% of all `connect` time; 4.6 ms idle → 28.7 ms
under burst.
**Recommendation: keep it.** It makes a stale connection impossible after a
DBaaS failover, and its cost is trivial next to the query costs already
identified. Dropping it requires `pool_recycle` below an idle timeout
nobody has measured _plus_ a real retry-on-disconnect path in the stream
and recalculation code — that is code, not a config flag. Revisit only if
A1 shows checkout contention is the actual bottleneck.
Bonus: the pre-ping is a fixed trivial statement, so its duration is a free
pure-RTT probe to Postgres. Worth charting.

**A3 — Why does a pipeline take 201.6 s?** (T11) The stream reported it
faithfully and closed cleanly — this is a pipeline-execution question,
not a stream bug. **Code investigation done 2026-08-22** (below); the
confirming measurement is still the one thing a human has to pull.

_Execution model, established from code._ A pipeline is a DAG of
`data_ingestion_jobs` rows sharing a `pipeline_id`, three phases deep:

```
root ingest (csv_ingest | api_ingest | factor_ingest)
   └─ N × emission_recalc          one child per det of the SAME module
        └─ 1 × aggregation         chained by the LAST recalc sibling only
```

Fan-out width N is `len(MODULE_TYPE_TO_DATA_ENTRY_TYPES[module])`
(`backend/app/models/module_type.py:71`) — **10 for `purchase`**, 3 for
headcount/equipment/buildings, 2 for travel, 1 for process_emissions.
Dispatch itself is concurrent: `chain_job` queues children in a
ContextVar and `drain_pending_dispatches` fires them all through
`fire_and_forget` after the parent commits
(`backend/app/tasks/_chain.py:93-108`).

**But they do not run concurrently.** Three gates, in order of how much
they bind:

1. **The `(module, year)` advisory lock — the dominant one _when N > 1_.**
   Every `emission_recalc` handler opens with
   `pg_advisory_xact_lock(1237, module_type_id * 100000 + year)`
   (`backend/app/tasks/_locks.py:38-78`, taken at
   `emission_recalculation_tasks.py:330`). It is **exclusive**, and it is
   held until `data_session` commits — which the runner does only _after_
   the handler returns, so it spans the whole job. The key does **not**
   include `data_entry_type_id`, and the fan-out is one child per det of
   **one** module — so **all N siblings of a pipeline hash to the same
   key and execute strictly one at a time**, serialised by Postgres.
   A `purchase` upload is 10 recalcs in a queue of one.
2. **`MAX_CONCURRENT_JOBS = 4`** (`config.py:471`), a per-pod
   `asyncio.Semaphore` acquired in `run_job` _before_ the claim
   (`runner.py:131`). Caps this pod at 4 jobs at once.
3. **Per-entry Python.** `recalculate_for_data_entry_type` loops entry by
   entry doing `model_validate` + `prepare_create`
   (`backend/app/workflows/emission_recalculation.py:147-241`), yielding
   on wall time only. Same event loop, so co-resident jobs interleave but
   do not parallelise.

Then the **aggregation** takes a _second_, coarser lock:
`pg_advisory_xact_lock(1236, year)` (`aggregation_tasks.py:131-135`) —
per-**year**, so it serialises aggregations across _every module and
every pipeline_ of that year.

_Inherent vs incidental._ This is the distinction the task turns on:

- **Inherent — do not touch.** The parent-commit-before-children gate
  (#1236; firing children early caused FK violations on
  `data_entry_emissions_data_entry_id_fkey`). The trailing-aggregation
  phase gate (`_is_last_recalc_sibling`,
  `emission_recalculation_tasks.py:108`) — earlier aggregations would see
  partial `data_entry_emissions`. **`factor_ingest` (writer) excluding
  `emission_recalc` (reader)** — that is exactly what `_locks.py`'s
  docstring says it is for, and it is real.
- **Incidental — `emission_recalc` excluding `emission_recalc`.** Gate 1
  is an _exclusive_ lock, but siblings only **read** `factors`; they write
  `data_entry_emissions` for **disjoint** entry sets (different
  `data_entry_type_id`), and module-stats writing was moved out of this
  workflow into the aggregation handler
  (`emission_recalculation.py:276-283`), so there is no shared write
  target left between them. The docstring's own justification —
  "`factor_ingest` writes, `emission_recalc` reads" — describes a
  **reader/writer** lock; the code implements a full mutex. Nothing found
  in code requires reader-vs-reader exclusion.
  Proposal (not implemented, needs review): shared lock on the recalc
  side, exclusive on the factor side → **[#2276](https://github.com/EPFL-ENAC/co2-calculator/issues/2276)**.
- **Second-order, also incidental:** the advisory lock is taken _inside_
  the semaphore, so a job **blocked on the lock still burns a
  `MAX_CONCURRENT_JOBS` permit and both its pool connections** for the
  whole wait. Four queued purchase siblings can occupy every permit on a
  pod and head-of-line-block unrelated pipelines. Recorded in the same
  issue.

_Not the bottleneck (ruled out in code, so nobody re-checks it)._ The
connection pool: `DB_POOL_SIZE=10 + DB_MAX_OVERFLOW=10 = 20` per pod
(`config.py:76-95`, wired in `db.py`), against `4 jobs × 2 sessions = 8`
reserved for background work. Gate 2 binds before the pool does, so pool
exhaustion — the original #1723 symptom — cannot be what a 201 s pipeline
is waiting on. ⚠️ This is about the **job** path only; A1 is still open
for the **HTTP** path, which shares the same 20.

_The measurement that settles it._ `started_at`/`finished_at` are real
columns, stamped by `claim_job` and `finish_job`. One query:

```sql
SELECT id, job_type, module_type_id, data_entry_type_id,
       started_at, finished_at, finished_at - started_at AS dur
FROM data_ingestion_jobs
WHERE pipeline_id = '8aff966d-b4eb-4d64-ae56-68e16e0d8154'
ORDER BY started_at;
```

Read it as, **in this order**:

- **Only ONE `emission_recalc` row?** Then gate 1 never engaged — an
  uncontended lock costs nothing — and the whole 201.6 s is a single
  slice's per-entry compute. Go to gate 3. **Check this branch first:
  it is not an edge case.** `_chain_emission_recalc_for_data_ingest`
  produces exactly one target whenever the parent has a
  `data_entry_type_id` (any single-det CSV or API ingest), which is a
  common shape. Nothing in the traces says which shape
  `8aff966d-b4eb-4d64-ae56-68e16e0d8154` was — that is why the original
  A3 asked for `pipelines.job_count`, and the question still stands.
- **N > 1, intervals disjoint and back-to-back?** Confirms gate 1 — and
  `sum(dur) ≈ 201.6 s` confirms serialisation is the whole story.
- **N > 1, intervals overlapping?** Refutes gate 1; the time is per-entry
  compute inside one slice. Go to gate 3.

Gate 3's instrument already exists: the `Recalc profile …` log line
(`emission_recalculation.py:263`) prints ms/entry split
validate/prepare/remainder for every slice.

⚠️ Until that query runs, gate 1 is a **ranked hypothesis from code
reading, not a measurement** — the mechanism and the shared lock key are
facts, the claim that they account for the bulk of 201.6 s is not.
This document has been wrong four times by reasoning past that line.

### B. Ready now

**B1 — Fix the third `/api`-prefix instance** (correction 6). Fix the
trace-side `drop-health` policy; leave the metrics-side exclusion dead.
_Not started._

⚠️ **Do not "fix" this blind.** The `transform` processor carries only
`metric_statements`, so `route_class` exists on metrics and **never on
spans** — the tail-sampling policy cannot key on it. Whether the current
policy is already a no-op depends on whether span-side `http.target`
carries the `/api` prefix, which is a **Tempo lookup**, not a PromQL one:
search for `/healthz` spans — present means the policy is dead, absent
means it already works. Getting `invert_match` wrong here risks silently
dropping worker traces, which is how the pipeline investigation would
lose its evidence.

**B2 — Batch the `modules/{m}/{sub}` fan-out. DROPPED (2026-08-26).** Not
being built; the empty branch and worktree are deleted. Recorded here with
its findings so it is not re-proposed from the request-count argument alone.

The blocking question it was waiting on **was answered, and the answer was
"no gate needed"**: the authorization check is
`check_module_permission_for_report(..., module_id=module_id, action="view", …)`
(`carbon_report_module.py:759`) — keyed on **module, not submodule**. N
single-entry calls ask the identical question, so batching collapses N
redundant checks into one and introduces **no new authorization decision**.
It was ordinary work, not permission scoping.

⚠️ **If this is ever revived, the trap is
`_get_professional_travel_institutional_id_filter`**
(`carbon_report_module.py:162`). It _does_ vary per submodule: `None` for
most types, but for `plane`/`train` it restricts rows to the caller's own
`institutional_id` unless they hold principal/global access. It sits next to
the permission check and reads like boilerplate, so the obvious batch
implementation hoists it out of the loop — at which point a request for
`[plane, equipment]` returns **unfiltered travel rows, i.e. other people's
trips**. That is a **200 with too much data**, so every status-code test
still passes. It must be computed per entry, inside the loop, with a test
asserting exactly that.

Note also that #2360's fix took a different route for the explore page —
_deferring_ fetches until expansion rather than batching them — so the
request-count argument for B2 is weaker than when it was written.

**B6 — Suppress per-chunk ASGI spans** (was D2, promoted 2026-08-26).
805 spans for one upload, one per body chunk, **created and exported on the
event loop**. It was filed under "after A and B land", but that bucket's
rationale is "re-measure once the shared latency floor is fixed", which
applies to D1's triage table and not to this — it has no dependency on A or
B. It is also the prime suspect for the event-loop blocking `#2263` exists
to measure, so the two belong together: land the probe, then this, and the
lag number says whether it mattered.
Check whether the pinned `0.65b0` supports
`exclude_receive_span`/`exclude_send_span`; if not, a `SpanProcessor`
dropping `* http receive` / `* http send`. _Not started — plan first._

**B3 — Dashboard remainder** (§4.9): split 4xx/5xx, scope the `$pod`
variable to a metric name, add `$namespace`. _Not started._

**B4 — `ApiLatencySLOBreach`, added in parallel.** Measured live: job-class
p95 **and** p99 both returned exactly `10000` — the histogram's highest
finite bucket. A quantile past the last bucket is a boundary, not a
measurement; 10 s and 200 s are indistinguishable. Proportion-of-slow-
requests has no interpolation and degrades gracefully at low volume.
**Add only — do not delete `LatencyP50/P95/P99High` yet.** Run both a week,
compare fire counts; "the new rule never fired" is a result to measure, not
assume. _Not started._

**B5 — Alertmanager severity routing + inhibit rules, and de-hardcode the
namespace.** `severity` is set on every rule and consumed by nothing; a
`PodCrashLooping` currently emails its own crash _plus_ the latency and
error-rate alerts it caused. ⚠️ A malformed `AlertmanagerConfig` is
**silently dropped** — symptom is no alerts at all, with nothing reporting
an error. Ships with a post-merge verification checklist, not
fire-and-forget. _Not started._

### C. Gated — needs a written plan reviewed by both maintainers

**C1 — Cache the per-request user lookup.** _Highest-leverage untouched
item._ Every single request pays an uncached `SELECT users WHERE
institutional_id = … AND provider = …` (`backend/app/core/security.py:165`)
— 15.2 ms idle, 71.7 ms under burst, and it is the most-executed query in
the application. Correction 5 rules out an index fix; the answer is not to
make the round trip.
**Why this is gated, not just "do it":** the cached object carries the
user's roles, from which permissions are calculated. A stale entry is a
**stale authorization decision** — revoked access still working. That is
squarely the guardrails' "permission scoping" category. Needs an explicit
decision on TTL, on invalidation at role-sync time, and on what happens on
a cache miss under DB failure (must fail closed).
Note the machinery already exists: `#2273` built exactly this
shape — a pod registry, an internal invalidation endpoint, and a
best-effort concurrent broadcast — for the factors cache. Reuse it rather
than inventing a second pattern.

**C2 — Drop the duplicate OTel DB instrumentation** (T8, gated on A1).
33–39% of every DB-touching trace is redundant spans: SQLAlchemy emits
`connect` + `SELECT app`, psycopg emits `SELECT` + `;`, for the same work.
Two things to get right:

- **Sequencing.** `connect` is a _SQLAlchemy_ span and it is the evidence
  that answers A1. Do not drop SQLAlchemy, and do not do this at all until
  A1 is settled — a clean before/after needs a constant span set.
- **The chart default is not the fix.** `helm/values.yaml` defaults to
  `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS: "sqlalchemy,psycopg"` — disabling
  **both**, which would delete the `connect` signal. dev and stage
  currently override it to `""` (both enabled) _deliberately_, for this
  investigation; their own comments say "revert once the investigation is
  done". The correct end state is `"psycopg"` — neither the current
  override nor the chart default.
- Also revert `OTEL_TRACES_SAMPLER: "always_on"` on dev/stage, added for
  the same investigation. It is ~2/3 of the measured OTel throughput tax.

**C3 — ~~Path-scoped `/v1/sync` Route~~ → mirror dev's timeout annotation
to stage and prod.** **Rewritten 2026-08-22 — the original premise was
wrong (correction 8); the proposed mechanism is withdrawn.**

_What each environment actually has_ (read from
`openshift-app-config`, the git source ArgoCD syncs; each overlay carries
a full `valuesInline`, there is no shared default):

| Env       | backend Route timeout | Source                                    |
| --------- | --------------------- | ----------------------------------------- |
| **dev**   | **`10m`**             | `overlays/dev/kustomization.yaml:46`      |
| **stage** | **absent**            | `overlays/stage/kustomization.yaml:42-44` |
| **prod**  | **absent**            | `overlays/prod/kustomization.yaml:42-44`  |

The chart sets no default either — `routes.{frontend,backend,docs}.annotations`
are all `{}` in `helm/values.yaml:348-372`, and the only `haproxy.*` string
in the chart is `rewrite-target`. A repo-wide grep for
`haproxy.router.openshift.io/timeout` across the ops repo returns exactly
one line: dev. It was added by a single commit
(`chore(co2-calculator-dev): add route timeout`) and never mirrored.
stage and prod fall through to the cluster router default
(`ROUTER_DEFAULT_SERVER_TIMEOUT`, 30 s unless the cluster overrides it —
reading the live `IngressController` would confirm the number).

_Is anything being cut?_ **No evidence that it is, and one solid
counter-example.** `timeout server` is an **inactivity** timeout, not a
duration cap (correction 8a), and the 201.6 s trace was recorded on
**stage — the environment with no override** — completing with 200
(correction 8b). Both streams write on a ~2.015 s poll and the worst
silent gap ever measured was 16.2 s — comfortably under 30 s on the poll
cadence alone. `#2262`'s keepalive tightens that further; the conclusion
does not depend on it having shipped.

_So what's left is config drift, and the fix is one line, not a Route._
Add the same `annotations` block dev has to the stage and prod overlays.
Cheap, consistent, and it is genuine defence-in-depth for a **non**-streaming
request that could go quiet for >30 s (a slow upload or a blocking POST) —
not for the streams that motivated the item.
⚠️ **Not done here.** That edit lives in `openshift-app-config`, a
different repo; this investigation was read-only on it. Someone with
write access has to make it.

_Verdict on the path-scoped Route: withdrawn._ Three reasons.

1. **The surviving rationale doesn't need it.** A path-scoped Route earns
   its keep when a path needs a _different timeout value_. With `10m`
   applied route-wide, `/v1/sync` needs nothing the rest of `/api` doesn't.
2. **It's the wrong instrument for the metrics bonus.** Splitting
   `HaproxyRouteHighLatency`'s `avg` is an **alerting** problem, and the
   OTel-side equivalent is already solved and merged — `route_class` puts
   streams in their own bucket (ops #9–#11). Restructuring **production
   traffic routing** to fix a dashboard inverts the risk/benefit, and
   "ship small / defer, don't improvise" points the other way. Rescope or
   retire the HAProxy-side alert instead.
3. **Concrete footgun.** All three Routes are _already_ path-scoped
   (`/api`, `/docs`, `/`; `helm/templates/routes.yaml:24,55,83`), and the
   backend Route carries `haproxy.router.openshift.io/rewrite-target: /`,
   injected by the template unless overridden (`routes.yaml:11-17`). A
   fourth Route at `/api/v1/sync` inheriting that default would rewrite
   `/api/v1/sync/...` → `/...`, dropping `/v1/sync` and breaking every
   stream it was added to protect.

⚠️ Caveat on prod: overlays are exact (git), but the deployed chart is an
OCI artifact — dev `1.0.1351-dev`, stage `1.0.1347-rc`, prod **`1.0.1046`**.
`routes.yaml` has been untouched since 2026-04-01, so prod's build almost
certainly matches, but that was not verified against the artifact.

**C4 — `pipeline_duration_seconds` by kind.** A 201 s pipeline is a product
fact and belongs on a business dashboard with its own threshold, not in an
HTTP latency histogram. Purely additive as a metric — but emitting it means
hooking pipeline completion in `backend/app/tasks/runner.py` / `_chain.py` /
`_pipeline_reconciler.py` (correction 9 — `app/tasks/`, not
`app/workflows/`), which is recalculation internals. Same gate.
Cheapest hook point: `recompute_pipeline_status` is already called on
every job terminal (`runner.py`, post-`finish_job`) and already owns the
last-child oracle, so the completion edge is detected there today — the
metric needs a counter at that edge, not new traversal logic. Label by
`pipelines.kind`, and add `job_count` so a 10-child `purchase` pipeline is
distinguishable from a 1-child `process_emissions` one (see A3).

### D. After A and B land

**D1 — Re-measure, then triage the slow routes** (T8b). 14 of 22 non-stream
routes exceed 200 ms on p50 or mean, but every one of them includes the
shared floor (pre-ping RTT + the uncached user lookup, C1). Fix the floor
once, re-export traces, regenerate the table, _then_ triage what survives.
Triage signal is `mean − p50`, not p50: mean ≫ p50 means a slow tail
(contention, cold cache, size-dependent); mean ≈ p50 means uniformly slow,
usually one fixable query. Drop anything with n < 10.

**D3 — Migrate observability off `http.target`.** `#2265` enables
`OTEL_SEMCONV_STABILITY_OPT_IN=http/dup`, which dual-writes a second metric
carrying a correct, collision-free `http.route`. Once that's confirmed
flowing, the ops-repo `route_class` transform and every alert built on
tail-matching can move onto it and stop being fragile.
Both of that PR's open items are now closed: the flag is **not** a
chart-wide default (it would have reached prod — see ops `#13`, dev-backend
only), and confirming the Prometheus-rendered metric name is the whole
reason it was landed on dev first. **That confirmation is the next step**,
and it is what unblocks the migration.

## Open questions

- `SHOW max_connections` on the DBaaS, and whether a pgbouncer sits in
  front of it. With N replicas the real ceiling is `N × (pool_size +
overflow)`; dev runs 3 backend + 1 worker.
- Is 201 s an acceptable pipeline runtime for the product? If yes, say so
  and set the SLO. If no, it's a separate ticket with its own traces —
  see [#2276](https://github.com/EPFL-ENAC/co2-calculator/issues/2276),
  which proposes the one structural change A3 identified.
- The per-job timing query in A3, for pipeline
  `8aff966d-b4eb-4d64-ae56-68e16e0d8154`. Settles whether the recalc
  siblings serialise. **This is now the blocking unknown for A3.**
- What is `ROUTER_DEFAULT_SERVER_TIMEOUT` on the cluster's
  `IngressController`? Only affects how much headroom stage/prod have
  today; C3's conclusion holds either way, since `timeout server` is an
  inactivity timeout.
- A prod Tempo export during real concurrency. Everything measured so far
  is stage at an **average of 0.5 concurrent streams** — a quiet
  environment.
- The unexplained 335 ms gap at t+1.424 in the upload trace, with zero
  spans. `SpooledTemporaryFile` rollover? GC pause? Still unresolved.
- Whether probe _traces_ currently reach Tempo (correction 6 predicts yes).
  One Tempo query settles it.

## Appendix A — measured evidence

Source: Tempo table export, 200 traces, `svc1751t-co2-calculator-stage`,
~39.5 min window, plus 5 full OTLP traces. ⚠️ The export is **capped at 200
rows, so counts are shape, not rates**. Peak 6 concurrent streams, average
0.5. Traces span ≥3 pods across 2 ReplicaSets — a redeploy happened
mid-window, so don't compare absolute timings across them too closely.

**Total request-time 1249 s.** `pipelines/stream` 71.8%, `jobs/stream`
23.1%, everything else 5.1%.

| Route                                           |   n |    p50 |    mean |         max |
| ----------------------------------------------- | --: | -----: | ------: | ----------: |
| `GET /v1/sync/pipelines/{pid}/stream`           |  23 | 8.16 s | 38.97 s | **201.6 s** |
| `GET /v1/sync/jobs/{jid}/stream`                |  25 | 6.19 s | 11.55 s |      36.1 s |
| `GET /v1/taxonomies/module/{m}/{de}`            |  16 | 948 ms |  893 ms |     2064 ms |
| `POST /v1/files/temp-upload`                    |  22 | 408 ms |  636 ms |     3036 ms |
| `GET /v1/carbon-reports/{id}/modules/{m}/{sub}` |  29 | 249 ms |  379 ms |     1004 ms |
| `POST /v1/sync/dispatch`                        |  23 | 261 ms |  301 ms |      814 ms |
| `GET /v1/auth/callback`                         |   4 | 867 ms |  832 ms |      880 ms |
| `GET /v1/factors/{t}/class-subclass-map`        |  11 | 254 ms |  263 ms |      396 ms |
| `GET /v1/backoffice/units`                      |   3 | 394 ms |  390 ms |      395 ms |

**The two taxonomy traces, same endpoint, same 4-span structure (no N+1):**

| phase                       | `buildings/building` (846 rows) | `purchase/other_purchases` (20,915 rows) | ratio |
| --------------------------- | ------------------------------: | ---------------------------------------: | ----: |
| `connect`                   |                          5.9 ms |                                  29.1 ms |  4.9× |
| auth `SELECT users`         |                         15.2 ms |                                  71.7 ms |  4.7× |
| `SELECT factors`            |                         69.7 ms |                                1338.4 ms | 19.2× |
| tail (Python serialisation) |                         51.4 ms |                                 683.6 ms | 13.3× |
| **total**                   |                    **134.5 ms** |                            **2064.0 ms** | 15.3× |

Two effects at once: a uniform ~5× on work that is _identical_ in both
traces (database under load), and a further ~19× that scales with result
size (row count, since confirmed).

**Streams:** poll interval 2.015 s p50 (min 0.006, max 2.059); 2 queries
per poll at ~2.5 ms each. The 201.6 s stream did 103 polls, emitted 61
events continuously to t+201.62, then closed cleanly with 200 — **not a
zombie** (v2 claimed otherwise by comparing a single-job stream against a
whole-pipeline stream; that pairing was meaningless). Disconnect detection
and event de-duplication both work correctly and **should not be
"fixed"**. Silent gaps of 16.1 s and 16.2 s are what the keepalive
addresses.

**Upload** (trace `a7cfb477…`, 3.037 s, 816 spans — slowest of 22, p50 is
408 ms; generalise the structure, never the duration): 805 `http receive`
spans, auth at t+2.343 _after_ the whole body, then 4 S3 round-trips
(`PutObject` 286.4 → `HeadObject` 18.4 → `PutObject` 68.9 → `HeadObject`
9.6). Object written twice — since traced to the vendored
`enacit4r-files` writing a JSON metadata sidecar alongside the file, not a
bug in this repo.

**Frontend fan-out:** 31 requests in 1.5 s — 11 `taxonomies` + 18
`modules/{m}/{sub}`. Same endpoint measured **1254 ms p50 inside the burst
vs 237 ms outside** (5.3×). ⚠️ That comparison is confounded — the two
samples differ in payload as well as concurrency — so treat it as a symptom
map, not a causal claim. The mechanism turned out to be Postgres load and
query cost (correction 3), not event-loop queueing.

**Instrumentation tax:** redundant spans as a share of each trace —
pipeline stream 39%, job stream 37%, taxonomies 33%, upload 99% (dominated
by the 805 per-chunk ASGI spans).

## Appendix B — history

- **v1/v2** — inference-only, before traces. Claimed zombie streams and
  event-loop queueing. Both wrong.
- **v3** (2026-08-21) — rebuilt on 200 Tempo + 5 OTLP traces. Retracted
  both v2 claims; wrongly claimed there was no connection pooling.
- **v3.1** — retracted the pooling claim from the Grafana dashboard.
- **This rewrite** (2026-08-22) — after ~15 PRs. Corrects seven more v3
  claims (above), splits the alerting half out to #1402, and reduces the
  document to what is actually still open.
- **A3/C3 investigation** (2026-08-22) — code + ops-config reading, no new
  traces. Adds corrections 8–9, replaces A3 with the execution model and
  the one query that settles it, and **withdraws C3's proposed
  path-scoped Route** in favour of mirroring one annotation to stage/prod.
  Files [#2276](https://github.com/EPFL-ENAC/co2-calculator/issues/2276)
  for the one structural finding.

Pattern worth noticing: **every round of this document has been corrected
by the next one, and every correction came from measurement, not
argument.** Five confident, wrong conclusions so far — zombie streams,
event-loop queueing, no pooling, "the matcher is a no-op", and "streams
are probably being cut at 30 s". Treat anything here not backed by a cited
measurement as a hypothesis, and say so loudly when the evidence disagrees.
Note that #5 was refuted by a config file and a timeout definition — the
cheapest check in the list, and the one nobody ran for three revisions.
