---
status: in-progress
issue: 2049
last_updated: 2026-08-22
title: "Optimize Pipeline/Report Performance — what remains after the v3 investigation"
summary: "Rewritten 2026-08-22. The v3 trace investigation (200 Tempo traces + 5 OTLP traces) is finished and its alerting half shipped as #1402. This plan carries what's left: the connection-pool decision, the shared per-request floor, the OTel double-instrumentation tax, the remaining request fan-out, and the 201s pipeline. Seven claims from v3 are corrected here — read those first."
---

# Optimize Pipeline/Report Performance — what remains

Rewritten 2026-08-22, replacing the verbatim v3 investigation dump. That
document did its job: it drove ~15 PRs and its alerting half is live. What
it is now is mostly **history plus several claims we've since disproved**,
which makes it actively misleading to work from. The full v3 text is in
this file's git history if you need to challenge a number; the measurements
worth keeping are in [Appendix A](#appendix-a--measured-evidence).

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

## Delivered

| Task      | What shipped                                                                                                                                                        | Where                                 |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| T2        | `factors` root-caused: 846 vs **20,915** rows → result-set size, not a missing index. Cache + cross-pod invalidation                                                | `#2264` (draft), `#2273`              |
| T3/T4     | `route_class` in the collector; streams/uploads/jobs out of the normal-API latency alert                                                                            | ops `#9`–`#11` **merged**             |
| T5        | `event_loop_lag_seconds` probe                                                                                                                                      | `#2263`                               |
| T6 (half) | Taxonomy fan-out batched, 16 → 5 calls per page load                                                                                                                | `#2275`                               |
| T7 (part) | SSE keepalive + `Cache-Control`/`X-Accel-Buffering`; heartbeat gap off-by-one (`>=15` unreachable on a 2 s poll → fired at 16 s, the exact gap it existed to close) | `#2262`, `#2274`                      |
| T9        | Alert rules: 5xx-only error rate + traffic floor, `absent()` deadman, `PodHighCPU` disabled with reasoning, `repeatInterval` 24h                                    | ops `#8` **merged**                   |
| T10       | Auth-before-body (DoS surface closed), size limit enforced, `http.request_content_length`                                                                           | `#2266`                               |
| —         | S3 404s root-caused; storage decision documented (keep S3)                                                                                                          | `#2272`, upstream `enacit4r-files#24` |

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

**A3 — Why does a pipeline take 201.6 s?** (T11) Needs `pipelines.job_count`
and per-job `started_at`/`finished_at` for
`8aff966d-b4eb-4d64-ae56-68e16e0d8154`. The stream reported it faithfully
and closed cleanly — this is a pipeline-execution question, not a stream
bug. Are jobs sequential? Investigation only; any resulting change is
recalculation internals and needs its own reviewed plan.

### B. Ready now

**B1 — Fix the third `/api`-prefix instance** (correction 6). Fix the
trace-side `drop-health` policy; leave the metrics-side exclusion dead. _In
flight._

**B2 — Batch the `modules/{m}/{sub}` fan-out.** The larger, untouched half
of the 31-request burst (~18 of 31). Unlike taxonomies this carries
per-submodule permission checks, so batching must preserve them exactly —
a batch that collapses distinct authorization decisions is worse than 18
fast requests. _In flight._

**B3 — Dashboard remainder** (§4.9): split 4xx/5xx, scope the `$pod`
variable to a metric name, add `$namespace`. _In flight._

**B4 — `ApiLatencySLOBreach`, added in parallel.** Measured live: job-class
p95 **and** p99 both returned exactly `10000` — the histogram's highest
finite bucket. A quantile past the last bucket is a boundary, not a
measurement; 10 s and 200 s are indistinguishable. Proportion-of-slow-
requests has no interpolation and degrades gracefully at low volume.
**Add only — do not delete `LatencyP50/P95/P99High` yet.** Run both a week,
compare fire counts; "the new rule never fired" is a result to measure, not
assume. _In flight._

**B5 — Alertmanager severity routing + inhibit rules, and de-hardcode the
namespace.** `severity` is set on every rule and consumed by nothing; a
`PodCrashLooping` currently emails its own crash _plus_ the latency and
error-rate alerts it caused. ⚠️ A malformed `AlertmanagerConfig` is
**silently dropped** — symptom is no alerts at all, with nothing reporting
an error. Ships with a post-merge verification checklist, not
fire-and-forget. _In flight._

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

**C3 — Path-scoped `/v1/sync` Route with `haproxy.router.openshift.io/timeout: 600s`.**
`jobs/stream` reaches 36.1 s and pipelines 201.6 s against an OpenShift
HAProxy default of 30 s — some streams are probably being cut today and
nobody has looked. Changes production traffic routing. Bonus: it splits the
HAProxy metrics by route, which makes `HaproxyRouteHighLatency` meaningful
for free (its `avg` currently includes 201 s responses).

**C4 — `pipeline_duration_seconds` by kind.** A 201 s pipeline is a product
fact and belongs on a business dashboard with its own threshold, not in an
HTTP latency histogram. Purely additive as a metric — but emitting it means
hooking pipeline completion in `runner.py` / `_chain.py` /
`_pipeline_reconciler.py`, which is recalculation internals. Same gate.

### D. After A and B land

**D1 — Re-measure, then triage the slow routes** (T8b). 14 of 22 non-stream
routes exceed 200 ms on p50 or mean, but every one of them includes the
shared floor (pre-ping RTT + the uncached user lookup, C1). Fix the floor
once, re-export traces, regenerate the table, _then_ triage what survives.
Triage signal is `mean − p50`, not p50: mean ≫ p50 means a slow tail
(contention, cold cache, size-dependent); mean ≈ p50 means uniformly slow,
usually one fixable query. Drop anything with n < 10.

**D2 — Suppress per-chunk ASGI spans.** 805 spans for one upload, one per
body chunk, created and exported on the event loop. Check whether the
pinned `0.65b0` supports `exclude_receive_span`/`exclude_send_span`; if
not, a `SpanProcessor` dropping `* http receive` / `* http send`.

**D3 — Migrate observability off `http.target`.** `#2265` enables
`OTEL_SEMCONV_STABILITY_OPT_IN=http/dup`, which dual-writes a second metric
carrying a correct, collision-free `http.route`. Once that's confirmed
flowing, the ops-repo `route_class` transform and every alert built on
tail-matching can move onto it and stop being fragile.
⚠️ Two open items on that PR before it merges: it currently sets the flag
as a **chart-wide default**, so dev/stage/prod all start double-emitting
HTTP metrics permanently — worth scoping to dev first, given C2 exists to
_reduce_ exactly this kind of volume. And the Prometheus-rendered name of
the new metric is unconfirmed (likely
`http_server_request_duration_seconds`, but exporter-config-dependent).

## Open questions

- `SHOW max_connections` on the DBaaS, and whether a pgbouncer sits in
  front of it. With N replicas the real ceiling is `N × (pool_size +
overflow)`; dev runs 3 backend + 1 worker.
- Is 201 s an acceptable pipeline runtime for the product? If yes, say so
  and set the SLO. If no, it's a separate ticket with its own traces.
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

Pattern worth noticing: **every round of this document has been corrected
by the next one, and every correction came from measurement, not
argument.** Four confident, wrong conclusions so far — zombie streams,
event-loop queueing, no pooling, and "the matcher is a no-op". Treat
anything here not backed by a cited measurement as a hypothesis, and say so
loudly when the evidence disagrees.
