---
status: proposed
issue: 2049
last_updated: 2026-08-21
title: "Optimize Pipeline/Report Performance — Pool, Factors Query, Streams, Uploads"
summary: "v3 investigation (200 Tempo traces + 5 OTLP traces) into why stage runs 5x slower than local: connection pool pre-ping cost, the 1338ms factors query, 2s stream polling, duplicate OTel instrumentation, and the upload path. Split out of the #1402 alerting plan, which only covered the alerting half of this investigation (now done — see docs/src/implementation-plans/1402-trim-down-alerting.md)."
---

# Optimize Pipeline/Report Performance — Pool, Factors Query, Streams, Uploads

## Where this came from

This is the backend-performance half of a combined investigation that
originally lived in `1402-trim-down-alerting.md` (issue #1402, "TRIM DOWN
ALERTING"). #1402's actual scope — splitting Grafana alerting by endpoint
class, adding a `route_class` label, GlitchTip alerting — is done and
stays in that file. Everything below is the wider performance
investigation the same trace analysis surfaced, filed against #2049
("Optimize Perf — 5x worse in stage than in local") instead, since it's a
different scope: pipeline/query/instrumentation performance, not
alerting.

## Already spun out as their own issues (don't duplicate here)

- **T2** (the 1338ms `factors` query — confirmed a large-result-set
  problem via real row counts, `building`=846 vs `other_purchases`=20,915)
  → [co2-calculator#2258](https://github.com/EPFL-ENAC/co2-calculator/issues/2258)
- **The `/api` route-collision problem** found while building `route_class`
  → [co2-calculator#2260](https://github.com/EPFL-ENAC/co2-calculator/issues/2260)
- **T8/T10** (upload: double S3 write, auth-after-body DoS surface, no
  size limit) → [co2-calculator#2261](https://github.com/EPFL-ENAC/co2-calculator/issues/2261)

## What's still open here

- **T1** — pool_pre_ping keep/drop decision, real pool params vs DBaaS
  `max_connections`. **Touches pipeline/DB-connection internals — needs a
  written plan reviewed by both maintainers before implementation**, per
  the repo guardrails. Data needed: `SHOW max_connections` + current
  connection count on the DBaaS, which needs direct DB access.
- **T5** — `event_loop_lag_seconds` probe + probe latency visibility.
  Additive, no design decision, safe to implement directly.
- **T6** — batch/bound the frontend's 31-request page-load fan-out.
  Frontend track, do after T1/T2 land (may shrink the problem for free).
- **T7** — stream hardening (keepalive comments, `Last-Event-ID`, a
  path-scoped `/v1/sync` Route with its own HAProxy timeout). **The Route
  change is an infra/routing change to production traffic paths — needs a
  written plan reviewed by both maintainers.**
- **T8** — drop the duplicate psycopg OTel instrumentor, suppress
  per-chunk ASGI spans. Sequence *after* T1 is verified (the `connect`
  span is what proves the pooling fix).
- **T8b** — triage every route over 200ms, after T1+T2 land (the shared
  ~21–101ms floor may make several of these non-issues on their own).
- **T9** — alerting fixes. Done, via #1402 (see that plan doc).
- **T11** — why does a pipeline take 201.6s? Needs `pipelines.job_count`
  and per-job `started_at`/`finished_at` from the DB — direct DB access
  required. **Investigation of pipeline execution itself — treat any
  resulting code change as pipeline internals, same review gate as T1.**
- The `route_class="probe"` Grafana panel and a `pipeline_duration_seconds`
  business metric (§4.9.6/§4.7.7 below) — needs the new backend metric
  from T5 first, then wiring, not itself gated the same way as T1/T7/T11.

---

# CO2-Calculator — p99, SSE streams, upload path & alerting

**Investigation & remediation plan — v3**, built on 200 Tempo traces + 5 full OTLP traces.
Related: issue [#1402 `[PERF]: TRIM DOWN ALERTING`](https://github.com/EPFL-ENAC/co2-calculator/issues/1402), PR #1740.

Audience: an agent or engineer **with repository access**. The AGENT BRIEF below is a compact,
machine-readable summary — an agent can work from it alone. The prose sections after it carry the
derivations, the alternative explanations considered, and the YAML for the alerting work.

Reading order for an agent: **AGENT BRIEF → §1.8 (what the traces settled) → §0.5 (ranked TODO) →
the specific § linked from your task.** Sections 1.1–1.7 are provenance; read them only if you need
to challenge a number.

---

# AGENT BRIEF — read this first

```yaml
role: >
  You are investigating a performance + alerting problem in the EPFL-ENAC/co2-calculator
  backend. A human has already analysed 200 Tempo traces and 5 full OTLP traces. Your job is
  to find the CODE that explains the confirmed observations below, and report it. You have
  repository access; the analyst did not.

repo: EPFL-ENAC/co2-calculator
issue: "#1402 [PERF]: TRIM DOWN ALERTING"   # PR #1740 open
stack:
  backend:  FastAPI + SQLAlchemy + psycopg v3 + PostgreSQL (managed DBaaS)
  frontend: Vue.js SPA
  infra:    OpenShift, HAProxy router, Prometheus + Alertmanager + Grafana + Tempo
  telemetry: opentelemetry auto-instrumentation 0.65b0, SDK 1.44.0
environments:
  stage: {ns: svc1751t-co2-calculator-stage, host: co2-calculator-stage.epfl.ch}
  dev:   {ns: svc1751d-co2-calculator-dev}   # all PrometheusRules hardcode this one
  db:    co2-test.postgresql.dbaas.intranet.epfl.ch:5432 (db "app", user "app")
  s3:    s3.epfl.ch

operating_rules:
  - REPORT BEFORE FIXING. Deliver findings with file:line first. Do not open a PR in the
    same pass unless the human asks.
  - Distinguish CONFIRMED (measured, cited below) from HYPOTHESIS (this document's guess).
    Every "likely / probably / check whether" is a hypothesis. Verify or refute it; do not
    inherit it as fact.
  - If evidence contradicts this document, SAY SO LOUDLY. Two findings in v2 were already
    retracted by v3 after real traces arrived (see retracted_claims). That will likely
    happen again. Being right matters more than being consistent with this file.
  - Quote real code. Do not paraphrase what a function "probably" does.
  - Do not refactor opportunistically. Scope is the ranked_tasks list.

focus_areas:                       # all three need work, for three DIFFERENT reasons
  taxonomies_and_crud:
    share_of_request_time: 0.011
    verdict: "GENUINELY SLOW — fix the code"
    tasks: [T2, T8b]
    detail: "1338 ms query + 684 ms CPU serialisation, ~11x per page load. No N+1."
  streams:
    share_of_request_time: 0.950
    verdict: "NOT SLOW — mis-measured AND operationally fragile. TWO separate jobs."
    tasks: [T3, T7, T11]
    job_1_measurement: "get stream duration out of the API latency histogram (this is #1402)"
    job_2_real_defects:
      - "36.1 s job streams and 201.6 s pipeline streams vs a 30 s HAProxy default -> some are
         probably being cut today and nobody has looked"
      - "16-second stretches with zero bytes sent -> no keepalive comment"
      - "no lifetime cap, no Last-Event-ID (a dropped stream restarts from scratch)"
      - "why does a pipeline take 201.6 s? are jobs sequential? (T11)"
    failure_mode_to_avoid: >
      Shipping job 1, watching the alert emails stop, and closing #1402. The emails stopping is
      the MEASUREMENT working. Job 2 is still open at that point.
    do_not_change: "2.015 s poll interval, per-poll pool checkout, disconnect detection,
                    event de-duplication (61 sends / 103 polls) — all correct"
  uploads:
    share_of_request_time: 0.011
    verdict: "NOT a latency problem — a CORRECTNESS and SAFETY one"
    tasks: [T8, T10]
    detail: >
      p50 is 408 ms; the 3.037 s trace is the slowest of 22. Low priority by time-saved, NOT by
      importance. Auth runs after the full body is ingested and no size limit was found ->
      that is a DoS surface, arguably a security ticket found by a perf investigation.
      Also: the object is written TWICE (4 S3 round trips where 1 would do), 805 spans per
      request, and no http.request_content_length anywhere.

confirmed_observations:            # measured; treat as ground truth
  connection_pool:
    evidence: "5/5 OTLP traces + Grafana dashboard uid ndr79mm panel id 7"
    severity: medium
    status: "CORRECTED — v3 of this doc wrongly claimed there was no pooling. There is."
    detail: >
      A pool exists: DB_POOL_SIZE=15, and db_pool_connections{state="checked_out"|"size"} is
      already exported. The SQLAlchemy `connect` span wraps Engine.connect() = POOL CHECKOUT,
      not a new TCP connection. The `;` span is a CHILD of `connect` in 103/103 cases and is
      pool_pre_ping doing a network round trip.
      connect minus its `;` child (true checkout): 0.44 - 1.32 ms. That is a pool checkout.
    pre_ping_cost:
      pipeline_stream_201s: "103 pre-pings, 220.7 ms total, 80% of all connect time"
      idle_ms: 4.62
      under_burst_ms: 28.70    # identical trivial statement => pure round-trip probe
      inference: "6x RTT increase to Postgres under the 31-request burst => pressure is on the
                  DB/network, NOT on the Python event loop"
    open_question: >
      pool_size=15 (+ SQLAlchemy default max_overflow=10 = 25 usable) versus a ~31-request
      page-load fan-out where each request holds a connection for a 1338 ms query. Likely
      pool queueing. CHECK THE EXISTING PANEL FIRST before changing any config.
  slow_factors_query:
    evidence: "trace c68e5936 vs cba57ecd, same endpoint"
    severity: critical
    query: "SELECT factors.* FROM factors WHERE data_entry_type_id = %s::INTEGER AND year = %s::INTEGER"
    detail: >
      1338.4 ms in Postgres for data_entry purchase/other_purchases, vs 69.7 ms for
      buildings/building. Followed by 683.6 ms of CPU-bound Python (serialisation) vs
      51.4 ms. No N+1 — identical 4-span structure in both.
  load_amplification:
    evidence: "same two traces"
    detail: >
      Work that is IDENTICAL in both traces is ~5x slower in the slow one:
      connect 5.9 -> 29.1 ms, auth SELECT users 15.2 -> 71.7 ms. Payload cannot explain
      this; database load can. Consistent with no_connection_pooling under a request burst.
  poll_interval_2s:
    evidence: "trace cd7e8875, 103 polls"
    detail: "2.015 s p50 (min 0.006, max 2.059). 2 queries/poll, p50 2.5 ms each."
  frontend_fanout:
    evidence: "200-trace table, burst analysis"
    detail: >
      A page load fires 31 requests in 1.5 s — 11x GET /v1/taxonomies/module/{module}/{data_entry}
      and 18x GET /v1/carbon-reports/{id}/modules/{m}/{sub}.
  streams_dominate_time:
    evidence: "200-trace table"
    detail: >
      pipelines/stream = 71.8% and jobs/stream = 23.1% of all request-time (1249 s total),
      while being 24% of traces. They share one histogram with CRUD latency.
  shared_request_floor:
    evidence: "all 5 OTLP traces"
    severity: high
    detail: >
      EVERY request pays this before any route-specific work: a NEW PG connection plus an
      uncached `SELECT users WHERE institutional_id = %s AND provider = %s`.
      fast trace: connect 5.9 + auth 15.2 = 21.1 ms
      slow trace: connect 29.1 + auth 71.7 = 100.8 ms
      Consequence: 14 of 22 non-stream routes exceed 200 ms on p50 or mean, and a share of
      every one of those numbers is this floor. Fix it once (T1 + caching the user lookup)
      before triaging individual routes. See T8b.
  duplicate_instrumentation:
    evidence: "all 5 OTLP traces"
    severity: medium
    detail: >
      Two OTel DB instrumentors are active at once. SQLAlchemy emits `connect` and
      `SELECT app`; psycopg emits `SELECT` and `;`. Every query is therefore counted twice
      and every connection twice.
    redundant_span_share: {pipeline_stream: 0.39, job_stream: 0.37, taxonomies: 0.33}
    sqlalchemy_minus_psycopg_ms:   # the delta is real ORM row materialisation, not overhead
      auth_select_users: [0.3, 0.2]
      select_factors:    [11.9, 62.8]
    recommendation: >
      Drop the PSYCOPG instrumentor, KEEP SQLAlchemy. Reason: `connect` is a SQLAlchemy span
      and it is the evidence that verifies the T1 pooling fix — dropping SQLAlchemy would
      delete the signal for the top-priority task. SQLAlchemy also preserves ORM time.
    sequencing: >
      Do this AFTER T1 is fixed and verified. You want `connect` spans present while proving
      pooling works, and a clean before/after needs a constant span set.
  upload_structure:
    evidence: "trace a7cfb477 (3.037 s, 816 spans) — slowest of 22; p50 is 408 ms"
    detail: >
      805 `http receive` spans (one per body chunk). Auth SELECT runs AFTER the full body is
      read (t+2.343 of 3.037). Then 4 S3 round-trips totalling 476 ms:
      PutObject 286.4 -> HeadObject 18.4 -> PutObject 68.9 -> HeadObject 9.6, all 200,
      retry_attempts=0, rpc.system=aws-api (botocore). The object is written TWICE.
      One unexplained 335 ms gap at t+1.424 with zero spans.
  dead_alert_rule:
    evidence: "specific-namespace-alerts PrometheusRule"
    detail: >
      PodHighCPU divides by container_spec_cpu_quota (microseconds per CFS period, ~100000)
      instead of quota/period (cores). Ratio ~1e-5, threshold 0.9. Has never fired.

retracted_claims:                  # v2 said these; real traces disproved them. Do NOT revive.
  - claim: "pipelines/{id}/stream keeps polling after its job finishes (zombie connection)"
    why_wrong: >
      The pairing compared jobs/{id}/stream (watches ONE job) against pipelines/{id}/stream
      (watches a WHOLE pipeline and all its jobs). Different scopes. The 201.6 s stream
      emitted events continuously and closed cleanly with 200. The pipeline really took 201.6 s.
  - claim: "the slow taxonomies endpoint is pure event-loop queueing"
    why_wrong: >
      1338 ms of it is inside Postgres, a separate process. Event-loop contention cannot
      cause that. It is query cost + database load.
  - claim: "the upload path blocks the event loop and slows down health checks"
    status: UNTESTED, not disproven
    why: >
      Zero non-stream non-upload requests overlapped an upload in the sample, so the
      comparison was never possible. No /healthz trace exists in any export. Do not assume
      it either way; task T5 makes it measurable.

ranked_tasks:
  - id: T1
    priority: P0
    title: Confirm pool configuration and whether it is being exhausted
    status_note: "NOT 'enable pooling' — pooling exists. See connection_pool above."
    grep_hints:
      - "pool_size|max_overflow|pool_timeout|pool_recycle|pool_pre_ping|DB_POOL_SIZE"
      - "create_engine|create_async_engine"
      - "db_pool_connections"        # the metric already exists; find where it is emitted
    questions:
      - "Actual values of pool_size / max_overflow / pool_timeout / pool_recycle / pool_pre_ping?"
      - "Is DB_POOL_SIZE=15 per pod? With N replicas the ceiling is N*(15+overflow) against
         the DBaaS max_connections. What IS max_connections?"
      - "Is pool_pre_ping needed? It costs one round trip per checkout (220 ms across one
         201 s stream). Removing it requires pool_recycle below the DBaaS idle timeout plus
         retry-on-disconnect. Decide deliberately; do not remove it just because it is visible."
      - "Do stream handlers check out per poll (trace says yes, ~2 s apart, short) or hold one
         for the stream's life? Per poll is CORRECT — keep it."
    do_not: >
      Do not raise pool_size as a first move. Fix T2 so queries finish in tens of ms and the
      burst stops needing 31 simultaneous connections. Pool sizing is a symptom knob.
    acceptance: "pool params documented in the issue; checked_out no longer pins to size during a page load"
  - id: T2
    priority: P0
    title: Make SELECT factors fast (or cached)   # <-- START HERE
    grep_hints: ["factors", "data_entry_type_id", "taxonom", "emission_taxonomy", "EmissionType"]
    steps:
      - Run EXPLAIN (ANALYZE, BUFFERS) for both data_entry_type_id values, year=2025.
      - Check for a composite index on factors (data_entry_type_id, year).
      - Report row counts. If tens of thousands, an index will not save it — consider
        narrowing the column list (factors.values is likely a large JSON blob and probably
        dominates both transfer and the 684 ms of serialisation), aggregating in SQL, or caching.
      - Factors change when an ingestion job runs, not per request => cacheable with ETag.
    acceptance: "under 100 ms for every data_entry_type_id, or served from cache"
  - id: T3
    priority: P0
    title: Get stream duration out of the API latency histogram
    files: ["specific-namespace-alerts PrometheusRule", "OTel Collector / Prometheus scrape config"]
    detail: >
      This is the literal ask in #1402. A pipeline that CORRECTLY takes 201 s currently trips
      LatencyP50High, P95High and P99High. See sections 4.3, 4.4, 4.7 of this document for the
      route_class mapping and the replacement rules.
    acceptance: "a full import session produces zero alert emails"
  - id: T4
    priority: P0
    title: Verify whether http_target exists on http_server_duration_milliseconds
    detail: >
      Run: count by (http_target, http_route, http_method) (http_server_duration_milliseconds_count{namespace="svc1751d-co2-calculator-dev"})
      In PromQL an absent label is "", and "" !~ "^.*upload.*$" is TRUE, so if the label is
      missing the existing exclusion has never excluded anything. Post the result to #1402.
    acceptance: "answer posted; exclusion rewritten on http_route or route_class"
  - id: T5
    priority: P0
    title: Add event_loop_lag_seconds; make probe latency visible
    detail: >
      684 ms of CPU-bound serialisation per slow taxonomies call DOES block the loop, so this
      is now worth measuring for real. Also: no /healthz trace exists in any export — find out
      whether probes are in OTEL_PYTHON_EXCLUDED_URLS.
    acceptance: "both metrics scraped and charted"
  - id: T6
    priority: P1
    title: Batch or bound the 31-request page-load fan-out
    grep_hints: ["Promise.all", "taxonomies", "onMounted", "useQuery", "modules/"]
    note: "Do T1 and T2 first — they may make this unnecessary. Do not start with client-side rate limits."
  - id: T7
    priority: P1
    title: Stream hardening
    checklist:
      - "keepalive comment every ~15 s (trace shows 16 s gaps with zero bytes sent)"
      - "Cache-Control: no-cache; X-Accel-Buffering: no; Last-Event-ID support"
      - "path-scoped OpenShift Route for /v1/sync with haproxy timeout 600s (default is 30 s;
         jobs/stream reaches 36.1 s, pipelines 201.6 s). Also splits HAProxy metrics."
  - id: T8
    priority: P1
    title: Remove the duplicate DB instrumentation and the per-chunk ASGI spans
    depends_on: T1        # keep `connect` spans until pooling is verified
    grep_hints:
      - "SQLAlchemyInstrumentor|PsycopgInstrumentor|Psycopg2Instrumentor"
      - "FastAPIInstrumentor|instrument_app"
      - "opentelemetry-instrument|OTEL_PYTHON_DISABLED_INSTRUMENTATIONS|OTEL_PYTHON_EXCLUDED_URLS"
      - "exclude_receive_span|exclude_send_span"
    detail: >
      33-39% of every DB-touching trace is redundant spans. Two likely causes: both
      instrumentors called explicitly in the telemetry setup module, or the
      opentelemetry-instrument auto-loader is enabled AND something also calls .instrument()
      manually. If it is the auto-loader, OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=psycopg is a
      one-line env fix with no code change.
      Separately: the ASGI middleware emits one span per body chunk (805 for one upload).
      Check whether 0.65b0 supports exclude_receive_span / exclude_send_span; if not, add a
      SpanProcessor dropping spans named "* http receive" / "* http send".
      Also add http.request_content_length — no payload size exists anywhere in any trace,
      which makes slow-client vs large-file undecidable.
    acceptance: >
      One query produces one span. A stream trace of N polls has ~N connect + ~2N select
      spans, not ~2N + N semicolons. Upload traces are under ~20 spans.
  - id: T8b
    priority: P1
    title: Triage every route with p50 or mean > 200 ms (14 of 22 non-stream routes)
    depends_on: [T1, T2]
    detail: >
      Do NOT triage before T1 and T2 land — every request currently pays a shared floor of
      ~21 ms (fast) to ~101 ms (slow) consisting of a NEW PG connection plus an uncached
      per-request `SELECT users WHERE institutional_id AND provider`. Fix the floor once,
      re-export traces, regenerate the table, then triage what remains.
      Triage signal: prefer (mean - p50) over p50 alone. mean >> p50 => a slow tail
      (contention / cold cache / size-dependent path). mean ~= p50 => uniformly slow,
      usually one fixable query.
      Drop any route with n < 10 until a bigger sample confirms it.
    sub_questions:
      - "Why does every request do a DB lookup for the user? Cacheable on (institutional_id, provider)?"
      - "Is users (institutional_id, provider) indexed? 15 ms for a single-row lookup is high; 71.7 ms is very high."
      - "GET /v1/backoffice/units is suspiciously flat at ~390 ms across 3 samples -> fixed-cost full-table read? cacheable?"
      - "POST /v1/sync/dispatch at p50 261 ms only enqueues -- why is it not near-trivial?"
      - "GET /v1/factors/{t}/class-subclass-map hits the same `factors` table as T2 -- same index question?"
    routes_over_bar:   # [n, p50_ms, mean_ms, max_ms]
      "GET /v1/taxonomies/module/{module}/{data_entry}":        [16, 948, 893, 2064]
      "GET /v1/auth/callback":                                  [ 4, 867, 832,  880]
      "POST /v1/files/temp-upload":                             [22, 408, 636, 3036]
      "POST /v1/carbon-reports/{id}/modules/{m}/{sub}":         [ 4, 396, 407,  481]
      "GET /v1/backoffice/units":                               [ 3, 394, 390,  395]
      "GET /v1/carbon-reports/{id}/modules/{m}/{sub}":          [29, 249, 379, 1004]
      "GET /v1/carbon-reports/simulator/explore/...":           [ 3, 262, 368,  703]
      "POST /v1/sync/dispatch":                                 [23, 261, 301,  814]
      "GET /v1/modules-stats/{id}/report-stats":                [ 1, 298, 298,  298]
      "GET /v1/factors/{t}/class-subclass-map":                 [11, 254, 263,  396]
      "GET /v1/carbon-reports/{id}/modules/{m}":                [13, 199, 255,  517]
      "GET /v1/carbon-reports/{id}/modules/headcount/members":  [ 3, 156, 224,  415]
      "GET /v1/modules-stats/{id}/validated-totals":            [ 1, 219, 219,  219]
      "GET /v1/carbon-reports/unit/{uid}/year/{year}/":         [ 1, 217, 217,  217]
    acceptance: "every route_class=api route under 200 ms p50, or an explicit accepted-cost note in the issue"

  - id: T8c
    priority: P1
    title: Grafana dashboard "Specific graphs" (uid ndr79mm)
    fixes:
      - "panel id 3 'Latency percentile': no route filter -> split by route_class; set unit: ms;
         TURN ON EXEMPLARS (target A has exemplar:false) so a p99 spike is one click to the trace;
         delete or fix the leftover green:0/red:80 thresholds"
      - "panel id 2 'Backend HTTP Error Rate': splits nothing — 4..|5.. lumped. Split; unit: percentunit"
      - "panel id 1 'HaproxyRouteHighLatency': avg includes 201 s streams; exclude the /v1/sync route"
      - "panel id 7 'DB Pool Usage': KEEP, it is the best panel here. Add state=overflow and a
         pool wait-time histogram"
      - "$pod variable: label_values({namespace=...}, k8s_pod_name) has NO metric name -> matches
         every series in the namespace. Scope it to http_server_duration_milliseconds_count"
      - "namespace hardcoded in all 5 panels -> add a $namespace variable"
    add_panels: [per_route_p50_mean_table, http_server_active_requests, probe_latency,
                 event_loop_lag, db_round_trip, sse_connections_active,
                 pipeline_duration_by_kind, upload_throughput, slo_burn]
    also: "deploy annotations; row grouping; version the dashboard JSON in GitOps (it is at version 11,
           suggesting UI editing)"

  - id: T9
    priority: P1
    title: Fix the broken/missing alert rules
    detail: "PodHighCPU unit bug; HighErrorRate 0.5 -> 0.02 on 5xx only; uncomment Watchdog; add absent() deadman; de-hardcode the dev namespace (7 occurrences). See 4.7."
  - id: T10
    priority: P2
    title: Upload path audit
    grep_hints: ["temp-upload", "UploadFile", "boto3|aioboto3|aiobotocore", "put_object|head_object", "run_in_threadpool"]
    questions:
      - "S3 client sync or async? Handler `async def` or plain `def`?"
      - "Why two PutObject and two HeadObject per upload?"
      - "Why does auth run after the body is fully ingested? Is there any size limit?"
      - "Does the handler do `contents = await file.read()`? Any hashing / pandas on the payload?"
    note: >
      Uploads are 1.1% of request-time — low priority by TIME SAVED, not by importance.
      Do not start here, but do not skip it either. The auth-after-body item plus the missing
      size limit is a DoS surface and should be reported even if nothing else in T10 is actioned.
  - id: T11
    priority: P2
    title: Why does a pipeline take 201.6 s?
    detail: >
      Legitimate open question now that it is not a stream bug. Get pipelines.job_count and
      per-job started_at/finished_at for 8aff966d-b4eb-4d64-ae56-68e16e0d8154. Are jobs
      sequential? Does the ingestion worker also lack pooling (T1)?

output_contract:
  format: markdown
  sections:
    - "Findings: one block per task id, each with file:line, the relevant code quoted, and a
       CONFIRMED / REFUTED / INCONCLUSIVE verdict against this document's hypothesis."
    - "Contradictions: anything here that the code disproves. Put this first if non-empty."
    - "Proposed changes: diff-level description, smallest first, with risk notes."
    - "Still unknown: what you could not determine and what would settle it."
```


> **v3 — rebuilt after the four requested traces arrived. Two findings from v2 are retracted.**
> 1. The long streams are **not zombies**. The 201.6 s pipeline stream emitted events to the end and
>    closed cleanly; v2's pairing compared a *single-job* stream against a *whole-pipeline* stream.
>    The pipeline really did take 201.6 s. See [§1.8](#18-what-the-four-traces-settled--including-two-corrections).
> 2. The slow `taxonomies` call is **not queueing on the event loop**. 1338 ms of it is inside
>    Postgres, which no amount of event-loop contention can cause.
>
> What replaced them is more actionable: **there is no database connection pooling anywhere.** One
> 201-second stream opened **103 PostgreSQL connections** — one per 2-second poll. Every ordinary
> request opens its own too. That single defect explains the burst behaviour, the 5× slowdown of
> identical queries under load, and a large share of the tail.
>
> **v3.1 — a third retraction, from the Grafana dashboard.** There *is* connection pooling
> (`DB_POOL_SIZE=15`, and `db_pool_connections` is already exported). The `connect` span is a pool
> *checkout*, and the `;` span nested inside it is `pool_pre_ping` doing a network round trip.
> True checkout cost is **0.4–1.3 ms**. What survives is better: that pre-ping is an accidental
> pure network probe, and it goes **4.6 ms idle → 28.7 ms during the burst** — the cleanest evidence
> that burst pressure lands on Postgres, not on the Python event loop. And **pool_size 15 against a
> 31-request fan-out** is a live exhaustion question you can answer from an existing panel.
> See [§3.2](#32-p0--the-pool-exists-pool_pre_ping-costs-a-round-trip-per-checkout).
>
> Earlier upload findings stand but remain P2: uploads are 1.1 % of request-time.

---

## 0. Executive summary

| # | Problem | Evidence | Workstream |
|---|---|---|---|
| **A** | Pool exists and works (checkout 0.4–1.3 ms). But **`pool_pre_ping` costs a round trip per checkout** — 220 ms across one stream — and **size 15 vs a 31-request fan-out** may be exhausting it | **Confirmed**, 5/5 traces + dashboard | [§3.2](#32-p0--the-pool-exists-pool_pre_ping-costs-a-round-trip-per-checkout) |
| **B** | `SELECT factors … WHERE data_entry_type_id AND year` takes **1338 ms**, and serialising it burns **684 ms of CPU** | **Confirmed**, trace | [§3.4](#34-p0--the-factors-query-and-its-serialisation) |
| **C** | Streams poll every **2.015 s**, each poll opening a fresh connection | **Confirmed**, trace | [§3.3](#33-p1--the-2-second-poll-loop) |
| **D** | Pipelines legitimately run up to **201 s**, and that trips HTTP latency alerts | **Confirmed** | [§4](#4-workstream-b--alerting--observability) |
| **E** | Upload path: 4 S3 round-trips, 805 spans, auth-after-body | Structure confirmed; blast radius unmeasured | [§5](#5-workstream-c--upload--storage) |

**The headline for #1402:** a pipeline that correctly takes 3.4 minutes must not be able to trip an
HTTP latency alert. Streams are **95.0 % of all request-time** while being 24 % of the traces, and
they are session duration, not latency. Getting them out of the histogram is now the *primary* fix,
not a parallel nicety — because there is no longer a stream bug hiding behind the alert noise.

**The headline for engineering:** the `SELECT factors` query takes **1338 ms** and its serialisation
burns **684 ms of CPU**, and the page fires it ~11× in parallel against a pool of 15. Start there.
Meanwhile the pre-ping round trip — identical work every time — goes from 4.6 ms idle to 28.7 ms
during that burst, which says the pressure is on Postgres, not on the event loop.


## 0.4 The three areas, and what each actually needs

The document is organised by defect, which makes it easy to lose the product view. Restated by
area — because all three do need work, but for **three different reasons**, and only one of them is
"make it faster".

| | share of request-time | verdict | what it needs |
|---|--:|---|---|
| **Taxonomies** (and the wider CRUD API) | 1.1 % | **Genuinely slow. Fix the code.** | A 1338 ms query and 684 ms of CPU serialisation, fired ~11× per page load. Index / narrow / cache / batch. |
| **Streams** | **95.0 %** | **Not slow — mis-measured, and operationally fragile.** | Get them out of the latency histogram *and* fix the timeout, keepalive and lifetime gaps. Two separate jobs; do not do only the first. |
| **Uploads** | 1.1 % | **Not a latency problem. A correctness and safety one.** | Duplicate S3 writes, auth after the body is accepted, no size limit, 805 spans. Small blast radius, real defects. |

### Taxonomies — the real performance bug

The one place where "the endpoint is slow" is literally true. `SELECT factors … WHERE
data_entry_type_id AND year` takes **1338 ms** in Postgres for `purchase/other_purchases` versus
69.7 ms for `buildings/building`, then **683.6 ms of CPU** serialising the result. No N+1 — the span
structure is identical in both traces. The page fires it ~11× in parallel against a pool of 15.
→ **P0-1**, [§3.4](#34-p0--the-factors-query-and-its-serialisation).

Same table backs `GET /v1/factors/{t}/class-subclass-map` (254 ms p50), so the fix likely helps
twice. And 14 of 22 non-stream routes are over 200 ms — [§3.5b](#35b-p1--every-route-over-200-ms-the-shared-floor-first-then-the-outliers)
has the list, plus the ~21–101 ms floor they all share.

### Streams — two jobs, and the risk of doing only the easy one

**Job 1 — measurement (P0-4, P1-2).** A pipeline that correctly takes 201 s must not be able to
trip an HTTP latency alert. Streams are session duration, not latency. This is #1402.

**Job 2 — the actual defects (P1-5).** Moving them out of the histogram makes the alert honest; it
does not make the streams good. Still outstanding:

- **Route timeout.** `jobs/stream` reaches **36.1 s** and pipelines **201.6 s** against an
  OpenShift HAProxy default of **30 s**. Some of these are probably being cut today and nobody has
  looked. Needs a path-scoped Route for `/v1/sync`.
- **No keepalive.** The trace shows **16-second stretches with zero bytes sent** (t+68.5 → t+84.6,
  t+157.2 → t+173.4). Any intermediary with a shorter idle timeout drops the connection silently.
- **No lifetime cap** and no `Last-Event-ID`, so a dropped stream restarts from scratch rather than
  resuming.
- **The 201 s pipeline itself** is now a legitimate open question (**T11**,
  [§3.5](#35-p1--why-does-a-pipeline-take-2016-seconds)) — are jobs running sequentially?

⚠️ **The failure mode to avoid:** shipping the alerting fix, watching the emails stop, and closing
#1402. The emails stopping is the *measurement* working. Job 2 is still open at that point.

What is genuinely fine and should not be "fixed": the 2.015 s poll, the per-poll pool checkout,
disconnect detection, and event de-duplication (61 sends for 103 polls). All correct.

### Uploads — small, but the defects are real

p50 is **408 ms**; the 3.037 s trace is the slowest of 22. Uploads are not why your alerts fire, and
the "upload blocks the event loop" hypothesis remains **untested, not disproven** — no `/healthz`
trace exists and no ordinary request overlapped an upload in the sample.

But the trace shows four things worth a ticket regardless of latency:

- **The object is written twice** — `PutObject` → `HeadObject` → `PutObject` → `HeadObject`,
  476 ms, four round trips where one would do.
- **Auth runs after the entire body is ingested** (t+2.343 of 3.037). An unauthenticated caller can
  make the server accept an arbitrary payload before being rejected. Combined with **no size limit
  found anywhere**, that is a denial-of-service surface, not a performance note.
- **805 spans** for one request, on the event loop.
- **No `http.request_content_length`** anywhere, so slow client vs large file stays undecidable.

→ **P1-7** (spans, content-length) and **P2-1** ([§3.7](#37-p1--upload-path-structure)). Low
priority by *time saved*, not by importance — the auth-ordering item is arguably a security ticket
that happens to have been found by a performance investigation.

---

## 0.5 TODO — in priority order

One list, ranked. Everything below is cross-referenced to its detail section. **P0-1 is a blocker:
four exports, ten minutes, and it unlocks the rest.**

### P0 — this week

| # | Task | Why it is first | Owner | Effort | § |
|---|---|---|---|---|---|
| ~~P0-1~~ | ~~Export 4 traces~~ | **Done.** Results in [§1.8](#18-what-the-four-traces-settled--including-two-corrections) — and they retracted two v2 findings. | — | — | — |
| **P0-1** | `EXPLAIN (ANALYZE, BUFFERS)` the `factors` query; add the composite index if missing; cache the response | 1338 ms in Postgres + 684 ms of CPU serialising, ~11× per page load, against a pool of 15. Now the clear top item. | backend | S | [§3.4](#34-p0--the-factors-query-and-its-serialisation) |
| **P0-1b** | **Open the existing "DB Pool Usage" panel during a report-page load.** Is `checked_out` pinned to `size` (15)? | Answers pool exhaustion in one screenshot, with a panel you already have. Do it before touching any config. | anyone | 5 min | [§3.2](#32-p0--the-pool-exists-pool_pre_ping-costs-a-round-trip-per-checkout) |
| **P0-2** | Decide deliberately on `pool_pre_ping`; record `pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle` and the DBaaS `max_connections` | Pre-ping is 220 ms across one stream and 80 % of all `connect` time — but removing it has a real correctness cost. Decide, don't drift. | backend | S | [§3.2](#32-p0--the-pool-exists-pool_pre_ping-costs-a-round-trip-per-checkout) |
| **P0-3** | Run the `http_target` no-op check; paste result into #1402 | One query. Decides whether months of "we filtered uploads and it didn't help" measured anything. | obs | 5 min | [§4.1](#41-first--is-the-current-exclusion-a-no-op) |
| **P0-4** | Get stream duration out of the API latency histogram | A correct 201-second pipeline currently fires P50, P95 and P99. This is the literal ask in #1402. | obs | M | [§4.4](#44-stop-measuring-streams-as-latency) |
| **P0-5** | Add `event_loop_lag_seconds` probe | 684 ms of CPU-bound serialisation *does* block the loop. Now worth measuring for real. | backend | S | [§3.1](#31-p0--measure-the-two-things-we-have-never-measured) |
| **P0-6** | Determine whether probes are instrumented; get probe latency into metrics | No `/healthz` trace exists in any export. We have never measured the thing everyone is worried about. | backend + infra | S | [§3.1](#31-p0--measure-the-two-things-we-have-never-measured) |
| **P0-7** | Fix `PodHighCPU` (**it can never fire** — wrong unit), drop `HighErrorRate` 0.5 → 0.02 on `5..` only, uncomment `Watchdog`, add `absent()` deadman | Three silent gaps. Nothing currently detects the backend going quiet. Ten lines of YAML. | obs | S | [§4.7](#47-the-current-prometheusrules--why-they-fire-and-what-to-change) |

### P1 — next

| # | Task | Why | Owner | Effort | § |
|---|---|---|---|---|---|
| **P1-1** | Derive `route_class` in the collector | Prerequisite for every alert below. Config-only, no redeploy. | obs | M | [§4.3](#43-add-a-route_class-label--in-the-collector-not-the-app) |
| **P1-2** | Move stream duration out of the API histogram; add TTFB + termination-reason metrics | 95 % of request-time is in the wrong metric. | obs | M | [§4.4](#44-stop-measuring-streams-as-latency) |
| **P1-3** | Add `pipeline_duration_seconds` by kind, on a business dashboard | A 201 s pipeline is a product fact. Track it where it belongs, not in an HTTP alert. | obs + backend | S | [§4.4](#44-stop-measuring-streams-as-latency) |
| **P1-3b** | Investigate **why a pipeline takes 201 s** | Now a legitimate open question rather than a stream bug. Needs `job_count` and per-job timings. | backend | M | [§3.5](#35-p1--why-does-a-pipeline-take-2016-seconds) |
| **P1-4** | Switch the alert from p99 to proportion-of-fast-requests, `for: 10m` | p99 over `[5m]` on dev is arithmetically meaningless with a 201 s tail. | obs | S | [§4.2](#42-p99-over-5m-on-dev-is-not-a-usable-statistic) |
| **P1-5** | Keepalive comment, `Last-Event-ID`, path-scoped Route timeout for `/v1/sync` | `jobs/stream` maxes at 36.1 s against a 30 s HAProxy default; pipelines reach 201 s. Also splits HAProxy metrics, fixing §4.7.2 for free. | backend + infra | M | [§3.3](#33-p1--the-2-second-poll-loop) |
| **P1-6** | Enable `uvloop`; confirm replica count (traces show **≥3 pods**, so this is not single-process) | More workers will not help if the bottleneck is Postgres connections — do P0-1 first or it makes things worse. | infra | S | [§3.9](#310-p2--process-topology) |
| **P1-7** | Suppress per-chunk ASGI spans; add `http.request_content_length` | 805 spans per upload. And without payload size, slow client vs large file stays undecidable. | backend | S | [§3.6](#36-p1--805-spans-per-upload) |
| **P1-6b** | **Triage every route with p50 or mean > 200 ms** — 14 of 22 qualify. Re-measure *after* P0-1/P0-2 first; several will fall under the bar on their own | Every request pays a ~21–101 ms floor (new connection + uncached per-request user lookup) before any route work. Fix the floor once instead of 14 routes. | backend | M | [§3.5b](#35b-p1--every-route-over-200-ms-the-shared-floor-first-then-the-outliers) |
| **P1-7b** | **Drop the psycopg instrumentor, keep SQLAlchemy** | Two DB instrumentors are active: every query emits two spans, every connect two more. **33–39 % of every DB trace is redundant.** Possibly a one-line env var. ⚠️ **After P0-1 is verified** — `connect` is a SQLAlchemy span and it is what proves the pooling fix. | backend | S | [§3.8](#38-p1--the-double-instrumentation-tax-and-the-syncasync-question) |
| **P1-8** | Replace `LatencyP50/P95/P99High` with `ApiLatencySLOBreach` + `ProbeLatencyDegraded`; exclude the stream Route from `HaproxyRouteHighLatency` | **This is the literal ask in #1402.** Half of all import-workflow requests are streams, so the median request *is* a stream — p50>1s fires by construction. | obs | M | [§4.7.7](#477-the-replacement-latency-rules) |
| **P1-8b** | **Grafana dashboard**: split "Latency percentile" by `route_class`, set `unit: ms`, **turn on exemplars**, split 4xx/5xx, fix the `$pod` variable, add `$namespace` | Exemplars alone turn "p99 spiked" into one click to the trace. The dashboard currently mixes 201 s pipelines with 120 ms CRUD, same as the alerts. | obs | M | [§4.9](#49-the-grafana-dashboard-specific-graphs-uid-ndr79mm) |
| **P1-8c** | Add the missing panels: per-route p50/mean table, requests-in-flight, probe latency, event-loop lag, DB round-trip, active streams, pipeline duration, SLO burn | Requests-in-flight alone would have shown the 31-request fan-out immediately. | obs | M | [§4.9.6](#496-add-the-panels-that-were-missing) |
| **P1-9** | Alertmanager: severity routing, inhibit rules, `repeatInterval` 4h → 24h for warnings, deadman receiver | `severity` is set on every rule and used by nothing; a stuck warning sends 6 emails/day. | obs | S | [§4.8](#48-alertmanager-routing) |
| **P1-10** | De-hardcode `namespace="…-dev"` (7 occurrences) into an overlay variable | Stage and prod are currently uncovered or maintained as copies. | obs | S | [§4.7.6](#476-smaller-items) |

### P2 — after the above lands

| # | Task | Why | Owner | Effort | § |
|---|---|---|---|---|---|
| **P2-1** | Upload path audit: S3 client sync/async, double `PutObject`, auth-after-body, size limit | Real findings, but 1.1 % of request-time. | backend | M | [§3.6](#37-p1--upload-path-structure) |
| **P2-2** | Confirm whether psycopg v3 is used **sync or async** | A sync driver makes every 1338 ms `factors` query a full event-loop stall. | backend | S | [§3.8](#38-p1--the-double-instrumentation-tax-and-the-syncasync-question) |
| **P2-3** | `auth/callback` at 712–880 ms — synchronous Keycloak call? | Sub-second, but on every login. | backend | S | [§3.8](#39-p2--get-v1authcallback-at-712880-ms) |
| **P2-4** | Storage: `aioboto3` → staging + job → presigned direct-to-S3 | Do not start before P0-3 and P0-4 report. | backend | S→L | [§5](#5-workstream-c--upload--storage) |
| **P2-5** | Separate Deployment for stream endpoints | Isolates 95 % of request-time from the main API with no code change. | infra | M | [§8](#8-other-pistes) |
| **P2-6** | k6/Locust scenario: 31-request burst + N streams + 1 upload | Without it, none of this is regression-testable. | backend | M | [§8](#8-other-pistes) |

**Not yet scheduled:** a 15-minute Tempo export from **prod** during real concurrency. Everything in
§1.5–§1.6 was measured at an average of 0.5 concurrent streams on stage.

---

## 1. Evidence

Source: Tempo table export, 200 traces, service `backend`, ns `svc1751t-co2-calculator-stage`,
window ≈ 39.5 minutes. Plus one full OTLP trace (`a7cfb477…`, §1.7).

⚠️ The export is capped at 200 rows, so **counts are not rates** — treat them as a sample of shape,
not of volume.

### 1.1 Every distinct route

| Route | n | min | **p50** | mean | p95 | **max** | Σ time |
|---|--:|--:|--:|--:|--:|--:|--:|
| `GET /v1/sync/pipelines/{pid}/stream` | 23 | 4.07 s | **8.16 s** | 38.97 s | 189.8 s | **201.6 s** | **896 s** |
| `GET /v1/sync/jobs/{jid}/stream` | 25 | 4.06 s | **6.19 s** | 11.55 s | 32.3 s | **36.1 s** | **289 s** |
| `GET /v1/taxonomies/module/{module}/{data_entry}` | 16 | 134 ms | **948 ms** | 893 ms | 2064 ms | 2064 ms | 14.3 s |
| `POST /v1/files/temp-upload` | 22 | 301 ms | 408 ms | 636 ms | 1142 ms | 3036 ms | 14.0 s |
| `GET /v1/carbon-reports/{id}/modules/{m}/{sub}` | 29 | 119 ms | 249 ms | 379 ms | 936 ms | 1004 ms | 11.0 s |
| `POST /v1/sync/dispatch` | 23 | 198 ms | 261 ms | 301 ms | 557 ms | 814 ms | 6.9 s |
| `GET /v1/auth/callback` | 4 | 712 ms | 867 ms | 832 ms | 880 ms | 880 ms | 3.3 s |
| `GET /v1/carbon-reports/{id}/modules/{m}` | 13 | 110 ms | 199 ms | 255 ms | 517 ms | 517 ms | 3.3 s |
| `GET /v1/factors/{t}/class-subclass-map` | 11 | 132 ms | 254 ms | 263 ms | 396 ms | 396 ms | 2.9 s |
| `POST /v1/carbon-reports/{id}/modules/{m}/{sub}` | 4 | 354 ms | 396 ms | 407 ms | 481 ms | 481 ms | 1.6 s |
| `GET /v1/backoffice/units` | 3 | 380 ms | 394 ms | 390 ms | — | 395 ms | 1.2 s |
| `GET /v1/carbon-reports/simulator/explore/...` | 3 | 139 ms | 262 ms | 368 ms | — | 703 ms | 1.1 s |
| `GET /v1/sync/active-pipelines` | 6 | 130 ms | 154 ms | 155 ms | 193 ms | 193 ms | 0.9 s |
| `GET /v1/year-configuration/{year}` | 5 | 122 ms | 155 ms | 181 ms | 252 ms | 252 ms | 0.9 s |
| `GET /v1/carbon-reports/{id}/modules/headcount/members` | 3 | 102 ms | 156 ms | 224 ms | — | 415 ms | 0.7 s |
| `GET /v1/modules-stats/{id}/report-stats` | 1 | — | 298 ms | — | — | 298 ms | 0.3 s |
| `PATCH /v1/year-configuration/{year}` | 2 | 102 ms | 127 ms | 127 ms | — | 152 ms | 0.3 s |
| `GET /v1/modules-stats/{id}/validated-totals` | 1 | — | 219 ms | — | — | 219 ms | 0.2 s |
| `GET /v1/carbon-reports/unit/{uid}/year/{year}/` | 1 | — | 217 ms | — | — | 217 ms | 0.2 s |
| `GET /v1/factors/{t}/list` | 1 | — | 164 ms | — | — | 164 ms | 0.2 s |
| `GET /v1/sync/pipelines` | 1 | — | 156 ms | — | — | 156 ms | 0.2 s |
| `GET /v1/auth/login` | 1 | — | 153 ms | — | — | 153 ms | 0.2 s |
| `PATCH /v1/project-plans/{plan_id}` | 1 | — | 149 ms | — | — | 149 ms | 0.1 s |
| `GET /v1/connectors` | 1 | — | 122 ms | — | — | 122 ms | 0.1 s |

**Total request-time: 1249 s.** `pipelines/stream` = **71.8 %**, `jobs/stream` = **23.1 %**.
Everything else combined = **5.1 %**.

### 1.2 The workflow

Counts line up almost 1:1 — this is one user journey repeated ~22 times:

```
POST /v1/files/temp-upload   (22)   drop a file        p50   408 ms
POST /v1/sync/dispatch       (23)   enqueue pipeline   p50   261 ms   ← correctly async
GET  …/jobs/{id}/stream      (25)   watch the job      p50  6.19 s
GET  …/pipelines/{id}/stream (23)   watch the pipeline p50  8.16 s   max 201.6 s
```

### 1.3 Streams are 2-second poll loops

Taking each stream duration modulo 2000 ms:

| duration mod 2 s | 0–100 ms | 100–200 | 200–300 | >1000 |
|---|--:|--:|--:|--:|
| count | 32 | 8 | 4 | 4 |

**44 of 48 stream durations land within 300 ms of an exact multiple of 2 seconds.** Durations are
4.06, 6.07, 8.09, 12.10, 14.24, 16.14, 22.16, 28.26, 30.05, 32.26, 36.08 s — a quantised ladder.
`6.07 s` alone occurs ~15 times.

That is the signature of `while ...: check(); await asyncio.sleep(2)`. These are **not** event-driven
(no pub/sub, no `LISTEN/NOTIFY`). Every open stream runs a status check every 2 s for its whole life.
The 201.6 s stream did roughly **100 polls**. If each poll touches Postgres, that is 100 queries to
tell one browser that nothing changed.

### 1.4 The zombie streams — the single most important finding

Pairing each `pipelines/stream` with the `jobs/stream` that started within 500 ms of it:

| pairs | pipeline ÷ job | reading |
|---|---|---|
| 15 of 22 | **1.00** | both end together — correct |
| 7 of 22 | **1.98 – 12.48** | job finished, pipeline stream kept polling |

The seven divergent pairs:

| job stream ends | pipeline stream ends | wasted |
|--:|--:|--:|
| 16.16 s | **201.62 s** | **185 s** |
| 36.08 s | **189.83 s** | **154 s** |
| 16.14 s | **156.11 s** | **140 s** |
| 30.05 s | **115.32 s** | **85 s** |
| 22.16 s | 47.17 s | 25 s |
| 6.07 s | 28.26 s | 22 s |
| 6.13 s | 12.13 s | 6 s |

**All four traces above 100 s are zombies.** The p99 of your entire API is not a slow pipeline —
it is a connection that forgot to hang up, polling the database every 2 seconds for three minutes
after the work was done.

This kills the v1 interpretation ("201 s stream = 201 s pipeline, possibly correct"). It is a bug.

### 1.5 The real driver of normal-endpoint p99: a frontend fan-out

Latency of non-stream requests against total requests in flight at their start:

| in flight | n | p50 | mean | max |
|--:|--:|--:|--:|--:|
| 1 | 60 | 312 ms | 403 ms | 3036 ms |
| 2–5 | 47 | ~200 ms | ~300 ms | 1402 ms |
| 6–9 | 20 | ~220 ms | ~290 ms | 865 ms |
| 10 | 5 | 254 ms | 502 ms | 1390 ms |
| 11 | 4 | 492 ms | 616 ms | 1254 ms |
| **12+** | **16** | **851 ms** | **916 ms** | **2064 ms** |

Five bursts of ≥5 requests within one second appear in the window; the largest fires **31 requests
in 1.5 seconds** (11 of them `taxonomies`, 18 of them `modules/{m}/{sub}`).

The clean natural experiment — same endpoint, inside vs outside that burst:

| `GET /v1/taxonomies/module/{module}/{data_entry}` | n | p50 | max |
|---|--:|--:|--:|
| inside the 31-request burst | 11 | **1254 ms** | 2064 ms |
| outside it | 5 | **237 ms** | 962 ms |

**5.3× slower, same endpoint, same code path.** The endpoint is not slow; it is queued behind
30 siblings on one event loop. Its headline "948 ms median" in §1.1 is an artefact of the burst.

All seven `taxonomies` calls over 1 s occurred at **zero** concurrent streams and **zero**
concurrent uploads. This is self-inflicted, and it is the thing actually moving your p99.

### 1.6 What the data does *not* show — read this before acting

The DevOps hypothesis was: an upload blocks the event loop, so everything including health checks
goes slow. **This sample does not support that, and the honest position is "not proven here":**

- **Zero** non-stream, non-upload requests overlapped an upload at all (22 uploads, all short and
  clustered while the browser was otherwise idle). The comparison could not be made.
- Latency against concurrent *streams* shows no trend (p50 is 256 ms at 0 streams, 178 ms at 1,
  252 ms at 2 — noise).
- Peak concurrency was 6 streams; average **0.5**. This is a quiet stage environment.
- No `/healthz` or `/readyz` traces are in the export at all — probes are either excluded from
  instrumentation or filtered out of this query. **We have never actually measured probe latency.**

So: the hypothesis is untested, not disproven. §3.1 is how to test it properly. But it should not
be the basis for a sprint of work, and `aioboto3` should not be the first commit.

### 1.7 Deep dive: trace `a7cfb4771770744d748a82a12561b51f`

The one full OTLP trace — and note it is the **upload from the same workflow instance as the
201.6 s zombie**, fired 3.4 s earlier. 816 spans, 3.037 s, HTTP 200.

| Phase | Window | Duration | Share |
|---|---|---|---|
| Body ingestion (805 × `http receive`) | t+0.001 → t+2.330 | 2.330 s | 77 % |
| Auth DB (`connect` + `SELECT users …`) | t+2.343 → t+2.351 | 8 ms | 0.3 % |
| S3 (4 round-trips) | t+2.556 → t+3.032 | 476 ms | 16 % |
| Untraced | scattered | ~220 ms | 7 % |

- **805 `http receive` spans** — one per body chunk. Inside `await receive()`: 1548 ms; in gaps: 781 ms.
  Per chunk p50 0.236 ms / p90 6.08 / p99 12.67 / max 29.1. One unexplained **335 ms gap at t+1.424**.
- S3: `PutObject` 286.4 ms → `HeadObject` 18.4 → `PutObject` 68.9 → `HeadObject` 9.6, all 200,
  `retry_attempts=0`, `rpc.system=aws-api` (botocore). **The object is written twice.**
- DB: four spans for one query (`connect`, `;`, `SELECT app`, `SELECT`) — looks like double
  instrumentation. Pyformat placeholders. Runs **after** the whole body is read.

⚠️ At 3.037 s this is the **slowest of 22 uploads**; p50 is 408 ms. Generalise the *structure*,
never the duration.

### 1.8 What the four traces settled — including two corrections

Traces received: `cd7e8875…` (pipeline stream, 201.6 s, 779 spans), `d3b58370…` (job stream, 16.2 s,
86 spans), `c68e5936…` (taxonomies, 2064 ms), `cba57ecd…` (taxonomies, 134 ms).

#### ❌ Correction 1 — the "zombie stream" finding in v2 was wrong

The 201.6 s stream emitted **61 events, the last two at t+201.62 s**, then closed cleanly with 200.
Events flow continuously the whole time, thinning as work completes:

```
t(s)     polls  events
  0        12      10
 60        10       5
120        10       8
180        10       2
200         1       2   ← final events, then clean close
```

The pairing in §1.4 compared `jobs/{id}/stream` — which watches **one job** (`/v1/sync/jobs/75/stream`)
— against `pipelines/{id}/stream`, which watches **a whole pipeline** and its `job_count` jobs
(`/v1/sync/pipelines/8aff966d-…/stream`). Different scopes. The ratio was meaningless and the
"185 s wasted" table should be disregarded.

**The pipeline genuinely took 201.6 seconds.** The stream reported it faithfully and terminated
correctly. This is a pipeline-performance question, not a stream bug — and it makes Workstream B
(§4) the primary fix rather than a parallel nicety: a correct 3.4-minute pipeline **must not** be
able to trip an HTTP latency alert.

#### ❌ Correction 2 — the taxonomies slowness is not queueing either

| phase | fast (`buildings/building`) | slow (`purchase/other_purchases`) | ratio |
|---|--:|--:|--:|
| `connect` | 5.9 ms | 29.1 ms | 4.9× |
| `SELECT users` (auth) | 15.2 ms | 71.7 ms | 4.7× |
| **`SELECT factors`** | **69.7 ms** | **1338.4 ms** | **19.2×** |
| tail (Python, post-query) | 51.4 ms | 683.6 ms | 13.3× |
| **total** | **134.5 ms** | **2064.0 ms** | 15.3× |

Both traces have the **identical four-span structure — there is no N+1.**

And the decisive point: **1338 ms of it is spent inside Postgres**, a different process on a
different host. A busy FastAPI event loop cannot slow down a Postgres query. So the §3.4 claim that
this was "pure queueing on the event loop" is disproven.

What the numbers do say is more interesting, because it is two effects at once:

- **A uniform ~5× slowdown on work that is identical in both traces** — `connect` and the auth
  `SELECT users` do the same thing regardless of which taxonomy is requested. Five times slower
  means the *database* was under load, not the app.
- **A further 19× on the `factors` query** and 13× on serialisation, which scale with result size —
  `purchase/other_purchases` returns far more rows than `buildings/building`.

#### ✅ What was confirmed, and it is worse than expected

**There is no database connection pooling.** A `connect` span appears inside every single request,
in all five traces now examined. In the streams it is one connection **per poll**:

| trace | duration | polls | **`connect` spans** | queries |
|---|--:|--:|--:|--:|
| `cd7e8875…` pipeline stream | 201.6 s | 103 | **103** | 204 |
| `d3b58370…` job stream | 16.2 s | 11 | **11** | 21 |
| `c68e5936…` taxonomies | 2.06 s | — | 1 | 2 |
| `cba57ecd…` taxonomies | 0.13 s | — | 1 | 2 |
| `a7cfb477…` upload | 3.04 s | — | 1 | 1 |

**One HTTP request opened 103 PostgreSQL connections.** Each poll: `connect` → `;` → two `SELECT`s
→ presumably close. Across the 48 streams in the 200-trace sample that is on the order of a
thousand connection setups, plus one per ordinary request.

This is the mechanism that ties everything together. A 31-request page-load burst is not 31 tasks
queueing on an event loop — it is **31 new PostgreSQL connections plus 31 heavy `factors` queries
arriving at once**, which is exactly what makes `connect` and the auth query 5× slower in the
trace above. The head-of-line blocking is in Postgres, not in Python.

#### ✅ Also confirmed

- **Poll interval is exactly 2.015 s** (p50; min 0.006, max 2.059). §1.3's arithmetic was right.
- **Per-poll DB cost is small**: 2 queries, p50 2.5 ms each. Total DB work in the 201 s stream is
  846 ms — 276 ms of it just opening connections. The queries are fine; the churn is not.
- **Disconnect detection exists**: one `http receive` per poll, 103 of them. Good.
- **Event de-duplication exists**: 61 sends for 103 polls — it only emits on change. Good design.
- The pipeline stream polls **both** `data_ingestion_jobs` and `pipelines` each tick; the job
  stream polls only `data_ingestion_jobs`.
- **Duplicate instrumentation confirmed**: every query produces both a `SELECT` span
  (`opentelemetry.instrumentation.psycopg`) and a `SELECT app` span (SQLAlchemy). The driver is
  **psycopg v3**, so §3.7's sync-vs-async question is still open, but the double-counting is settled.
- **683 ms of CPU-bound Python** serialising the slow taxonomy response. *That* does block the
  event loop — the blocking is real, it just comes from taxonomy serialisation rather than uploads.

---

## 2. Diagnosis — why filtering never worked

Current query:

```promql
histogram_quantile(0.99, sum by (le) (
  rate(http_server_duration_milliseconds_bucket{
    namespace="svc1751d-co2-calculator-dev",
    http_target!~"^.*upload.*$",
    k8s_pod_name=~"$pod"}[5m])
))
```

Three independent reasons it does not do what it looks like. Check in order.

**1 — the matcher is probably a no-op.** `http.target` is attached to *spans* (it is in the OTLP
trace) but the OTel ASGI **duration metric** attribute set is deliberately narrower. In PromQL an
absent label is the empty string, and `"" !~ "^.*upload.*$"` is **true**, so every series is kept.
Verify with §4.1 before believing any conclusion drawn from this query.

**2 — it filters the wrong endpoint.** Uploads are 1.1 % of request-time. Streams are **95 %**.
Excluding `.*upload.*` removes almost nothing from the tail.

**3 — even a correct filter leaves the real cause.** For normal endpoints the p99 is driven by the
frontend's own 31-request burst (§1.5), which is *inside* whatever set you keep. You cannot filter
away requests queued behind each other.

---

## 3. Workstream A — Performance

### 3.1 P0 — Measure the two things we have never measured

Everything else is hypothesis until these exist. Both are small.

**(a) Event-loop lag.** A background task, one histogram:

```python
async def loop_lag_probe():
    while True:
        t0 = time.perf_counter()
        await asyncio.sleep(0.1)
        EVENT_LOOP_LAG.observe(time.perf_counter() - t0 - 0.1)
```

Immune to traffic volume, client speed and payload size — everything that makes p99 useless here.
This is the only clean test of the blocking hypothesis (§1.6).

**(b) Probe latency.** No `/healthz` trace exists in the export. Find out whether probes are in
`OTEL_PYTHON_EXCLUDED_URLS`, or simply were not sampled. If excluded: **keep them excluded from the
SLO but get them into the metrics**, because probe latency during a burst is the direct picture of
head-of-line blocking. Also check pod restart counts — if probes fail during bursts, every open SSE
stream dies and all browsers reconnect at once.

Then, once: `oc exec -it <pod> -- py-spy dump --pid 1` during a large upload. Needs `SYS_PTRACE`
(check the SCC). Ten minutes, definitive answer.

### 3.2 P0 — The pool exists. `pool_pre_ping` costs a round trip per checkout

> **⚠️ This section corrects the v3 claim that there is no connection pooling. There is.**
> The Grafana dashboard exports `db_pool_connections{state="checked_out"|"size"}` with
> `DB_POOL_SIZE=15`, and the span structure confirms it. See the reconciliation below.

#### What the `connect` span actually is

`opentelemetry-instrumentation-sqlalchemy` wraps `Engine.connect()`, which is **pool checkout**,
not a new TCP connection. And the `;` span is a **child of `connect` in 103/103 cases** — it is
`pool_pre_ping` executing a no-op statement against Postgres to verify the pooled connection is
still alive.

Subtracting the child gives the true checkout cost:

| trace | `connect` | of which `;` (pre-ping) | **true checkout** |
|---|--:|--:|--:|
| taxonomies 134 ms | 5.94 ms | 4.62 ms (78 %) | **1.32 ms** |
| taxonomies 2064 ms | 29.14 ms | 28.70 ms (99 %) | **0.44 ms** |
| pipeline stream (p50 of 103) | 2.20 ms | 1.67 ms (80 %) | **0.51 ms** |

**0.4–1.3 ms is a pool checkout.** A real handshake to a remote DBaaS — TCP, TLS, auth — would be
tens of milliseconds. The pool is working. v3 read `connect` as "new connection" and was wrong.

#### What is actually worth fixing

**1. The pre-ping is a network round trip on every checkout.** In the 201.6 s stream that is
**103 pre-pings costing 220.7 ms** — 80 % of all `connect` time. Options:

- Keep it and accept the cost. It is genuinely cheap when the database is healthy, and it is what
  makes a stale-connection error impossible after a DBaaS failover. This is a defensible choice.
- Or drop `pool_pre_ping` and rely on `pool_recycle` (set it below the DBaaS idle timeout) plus
  retry-on-disconnect. Faster, but you must handle the stale-connection case somewhere.

Decide deliberately and write the reason down. Do **not** remove it just because it appears in
every trace.

**2. The pre-ping is an accidental network probe — use it.** It is a fixed, trivial statement, so
its duration measures nothing but round-trip time to Postgres:

| | idle | during the 31-request burst |
|---|--:|--:|
| `;` pre-ping | 4.62 ms | **28.70 ms** |

**A 6× increase in raw round-trip time to the database.** Identical work, no payload, no ORM. This
is the cleanest evidence in the whole investigation that the burst pressure lands on **Postgres or
the network**, not on the Python event loop.

**3. Pool size 15 against a 31-request fan-out — check for exhaustion.** This is the live question,
and you already have the panel for it.

- `pool_size=15`, plus SQLAlchemy's default `max_overflow=10`, gives 25 usable connections.
- The page-load burst is ~31 concurrent requests (§1.5), each holding a connection for the length
  of its query — and `SELECT factors` takes **1338 ms** (§3.4).
- 31 requests × ~1.3 s each against ≤25 slots means the last arrivals **queue on the pool**.

**Action: open the "DB Pool Usage" panel during a page load on the report view.** If
`checked_out` pins to the `size` line, that is the mechanism, and it is visible in one screenshot.
Then check `max_overflow` and whether `pool_timeout` is producing silent waits.

Note the ordering: raising `pool_size` is the wrong first move. Fix §3.4 so the queries finish in
tens of milliseconds and the burst stops needing 31 simultaneous connections. Pool sizing is a
symptom knob.

#### Still to confirm in code

- `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping` — actual values, and
  whether `DB_POOL_SIZE=15` is per pod. With N replicas the real ceiling is `N × (15 + overflow)`
  against the DBaaS `max_connections`.
- Is the engine created once at startup? (Almost certainly yes, given the pool works.)
- Do the stream handlers check out per poll (correct — the trace shows a short checkout every
  2.015 s) or hold one for the stream's life? The trace says per poll. Good; keep it that way.

### 3.3 P1 — The 2-second poll loop

Confirmed at 2.015 s (p50), with correct disconnect detection and correct event de-duplication.
The loop itself is reasonable; only its connection behaviour is not, and §3.2 fixes that.

Remaining work, in descending value:

- **Route timeouts.** `jobs/stream` reaches 36.1 s and pipelines 201.6 s against an OpenShift
  HAProxy default of **30 s**. Add a second, path-scoped Route rather than raising the global
  timeout, so a hung CRUD request still fails fast — and as a bonus it splits the HAProxy metrics
  and fixes §4.7.2:

  ```yaml
  metadata:
    annotations:
      haproxy.router.openshift.io/timeout: 600s
  spec:
    path: /v1/sync
  ```

- **Keepalive.** A `: keepalive\n\n` comment every ~15 s. With a 2 s poll and de-duplicated
  events, the trace shows **16-second gaps with no bytes sent** (t+68.5 → t+84.6, t+157.2 → t+173.4).
  Any intermediary with a shorter idle timeout will cut those connections.
- `Cache-Control: no-cache`, `X-Accel-Buffering: no`, and `Last-Event-ID` so a dropped stream
  resumes instead of restarting from scratch.
- **Consider event-driven** (Redis pub/sub, `LISTEN/NOTIFY`) — but only after §3.2. With pooling
  fixed, 2 indexed queries every 2 s is cheap, and polling is far simpler to operate.

### 3.4 P0 — The `factors` query and its serialisation

```sql
SELECT factors.emission_type_id, factors.data_entry_type_id, factors.classification,
       factors.values, factors.year, factors.id, factors.last_seen_job_id
FROM factors
WHERE factors.data_entry_type_id = %(data_entry_type_id_1)s::INTEGER
  AND factors.year = %(year_1)s::INTEGER
```

**1338 ms in Postgres, then 684 ms of CPU in Python.** For `buildings/building` the same code path
is 69.7 ms + 51.4 ms. And the page fires this ~11 times in parallel.

Do, in order:

1. **`EXPLAIN (ANALYZE, BUFFERS)`** for both `data_entry_type_id` values (`buildings/building` vs
   `purchase/other_purchases`), year 2025. Seq scan, or index scan returning a very large set?
2. **Check for a composite index** on `factors (data_entry_type_id, year)`. If it is missing, add
   it — this exact class of fix has been needed in this codebase before.
3. **How many rows does `purchase/other_purchases` return?** If it is tens of thousands, no index
   will save you and the answer is pagination, aggregation in SQL, or narrowing the column list —
   `factors.values` is likely a JSON blob and probably the bulk of both the transfer and the 684 ms
   of serialisation.
4. **Cache it.** Factors for a given `(data_entry_type_id, year)` are reference data that changes
   when an ingestion job runs, not per request. In-process TTL cache or Redis, plus `ETag` /
   `Cache-Control` so the browser stops asking. This is the highest value-per-line change available.
5. **Batch the frontend.** The report view fires ~11 `taxonomies` calls and ~18 `modules/{m}/{sub}`
   calls in 1.5 s. One `GET /v1/taxonomies/module/{module}?entries=a,b,c` would collapse the first
   group — and backend ownership of computation is already the house style.

Note the ordering: with §3.2 fixed and this cached, the 31-request burst stops being 31 connections
and 31 heavy queries. Do not start with client-side concurrency limits; they treat the symptom.

### 3.5 P1 — Why does a pipeline take 201.6 seconds?

A genuine open question now that it is no longer dismissed as a stream bug. The stream polled 103
times and reported real state changes throughout, thinning towards the end.

- What is `pipelines.job_count` for `8aff966d-b4eb-4d64-ae56-68e16e0d8154`, and what are the
  per-job `started_at` / `finished_at`?
- Are jobs executed **sequentially**? 201.6 s across N jobs, with the event stream thinning, looks
  like serial execution.
- The worker doing the ingestion — does it also lack connection pooling (§3.2)? If it opens a
  connection per row batch, that alone could dominate.
- Is 201 s acceptable for the product? If yes, say so in #1402 and set the SLO accordingly. If no,
  it is a separate performance ticket with its own traces.

### 3.5b P1 — Every route over 200 ms: the shared floor first, then the outliers

**14 of 22 non-stream routes** exceed 200 ms on p50 or mean. Before opening 14 tickets, note that
they share a floor.

#### The shared floor — fix this once, not fourteen times

Every request in every trace pays, before any route-specific work happens:

| | fast trace | slow trace |
|---|--:|--:|
| `connect` (a **new** PG connection, §3.2) | 5.9 ms | 29.1 ms |
| `SELECT users … WHERE institutional_id AND provider` (auth) | 15.2 ms | 71.7 ms |
| **floor** | **~21 ms** | **~101 ms** |

So a chunk of every number in the table below is P0-1 and an uncached per-request user lookup.
**Re-measure after P0-1 before triaging any individual route** — several will drop under the bar on
their own.

Two questions that fall out of this and are worth their own answers:

- **Why is there a DB lookup for the user on every request?** If a session or token already carries
  the identity, this is cacheable (in-process TTL, or Redis, keyed on
  `institutional_id + provider`). It is the single most-executed query in the application.
- Is `users (institutional_id, provider)` indexed? 15 ms for a single-row lookup on an indexed
  column is high; 71.7 ms is very high.

#### The list

Bar: **p50 > 200 ms or mean > 200 ms**, streams excluded (they are session duration, §4.4).
"Weak" means too few samples to act on — confirm before investing.

| Route | n | p50 | mean | max | Note |
|---|--:|--:|--:|--:|---|
| `GET /v1/taxonomies/module/{module}/{data_entry}` | 16 | **948** | 893 | 2064 | **§3.4** — root cause known: `factors` query + serialisation |
| `GET /v1/auth/callback` | 4 | **867** | 832 | 880 | **§3.9** — synchronous Keycloak token exchange? On every login |
| `POST /v1/files/temp-upload` | 22 | 408 | 636 | 3036 | **§3.7** — body transfer + 4 S3 round-trips |
| `POST /v1/carbon-reports/{id}/modules/{m}/{sub}` | 4 | 396 | 407 | 481 | weak. A write path — check for per-row commits |
| `GET /v1/backoffice/units` | 3 | 394 | 390 | 395 | weak. Suspiciously flat — probably a fixed-cost full-table read; cacheable |
| `GET /v1/carbon-reports/{id}/modules/{m}/{sub}` | 29 | 249 | 379 | 1004 | **Best sample in the set.** mean ≫ p50 ⇒ a slow tail worth a trace |
| `GET /v1/carbon-reports/simulator/explore/...` | 3 | 262 | 368 | 703 | weak |
| `POST /v1/sync/dispatch` | 23 | 261 | 301 | 814 | Good sample. Should be near-trivial — it only enqueues |
| `GET /v1/modules-stats/{id}/report-stats` | 1 | 298 | — | 298 | weak |
| `GET /v1/factors/{t}/class-subclass-map` | 11 | 254 | 263 | 396 | Same `factors` table as §3.4 — likely the same index question |
| `GET /v1/carbon-reports/{id}/modules/{m}` | 13 | 199 | 255 | 517 | Just over on mean |
| `GET /v1/carbon-reports/{id}/modules/headcount/members` | 3 | 156 | 224 | 415 | weak |
| `GET /v1/modules-stats/{id}/validated-totals` | 1 | 219 | — | 219 | weak |
| `GET /v1/carbon-reports/unit/{uid}/year/{year}/` | 1 | 217 | — | 217 | weak |

Under the bar and fine for now: `year-configuration` (155), `factors/{t}/list` (164),
`sync/pipelines` (156), `sync/active-pipelines` (154), `auth/login` (153),
`PATCH project-plans` (149), `PATCH year-configuration` (127), `connectors` (122).

#### How to work the list

1. **P0-1 and P0-2 first.** Then re-export and regenerate this table. Do not triage stale numbers.
2. **Prefer `mean − p50` as the triage signal**, not p50 alone. Where mean ≫ p50 there is a slow
   tail hiding in an otherwise healthy route — `modules/{m}/{sub}` (249 → 379) and
   `temp-upload` (408 → 636) are the two clear cases. A route where mean ≈ p50 is *uniformly*
   slow, which usually means one fixable query; a route where mean ≫ p50 is *sometimes* slow,
   which usually means contention, a cold cache, or a size-dependent path.
3. **Drop anything with n < 10** until a bigger sample confirms it.
4. Then pull one trace per surviving route and look for the §3.4 pattern: how much is Postgres,
   how much is Python after the last query.

Add this table to the dashboard as a recurring review rather than a one-off — a per-route p50/mean
panel filtered to `route_class="api"`, sorted descending, is the cheapest way to keep it honest.

### 3.6 P1 — 805 spans per upload

`OpenTelemetryMiddleware` emits a span per ASGI `http.receive`/`http.send`. One per body chunk:
creation, context propagation, serialisation, export — ~800 times, on the event loop, per upload.

- Check whether the pinned version (`0.65b0`) supports `exclude_receive_span` / `exclude_send_span`.
  If not: upgrade, or add a `SpanProcessor`/sampler dropping `* http receive` / `* http send`.
- **Add `http.request_content_length`.** There is no payload size anywhere in the trace, so slow
  client vs large file is currently undecidable. Fix early — it unblocks interpreting everything else.

### 3.7 P1 — Upload path structure

Confirm and report with file:line:

- **S3 client type**: `boto3` vs `aioboto3`/`aiobotocore`; handler `async def` or plain `def`;
  any `run_in_threadpool` wrapper. Sync client inside `async def` ⇒ 476 ms of blocking per upload.
  (Real, but 1.1 % of request-time — hence P1, not P0.)
- **Why two `PutObject`?** Temp key then copy to final? A second artefact? And are the two
  `HeadObject` calls verification after a `PutObject` that already returned 200 + ETag?
- **Auth after body.** `SELECT users …` fires at t+2.343, after 2.3 s of body was accepted. An
  unauthenticated caller can make the server ingest an arbitrary payload before being rejected.
  Is there *any* size limit, in the app or on the Route?
- **The 335 ms gap at t+1.424.** `SpooledTemporaryFile` rollover (Starlette buffers to `max_size`,
  default 1 MB, then flushes — check the version, older ones write synchronously)? GC pause? Another
  request? Check what `/tmp` is backed by in the Deployment. Also: does the handler do
  `contents = await file.read()`, and is there any hashing / `pandas.read_csv` on the payload
  (CPU-bound blocks regardless of threadpool, thanks to the GIL)?

### 3.8 P1 — The double instrumentation tax, and the sync/async question

#### Which instrumentor emits what — settled by the traces

Every query produces **two** spans, and every connection produces two more:

| span name | emitted by | carries |
|---|---|---|
| `connect` | **SQLAlchemy** | the pooling signal — this is the span that proves §3.2 |
| `SELECT app` | **SQLAlchemy** | `db.operation`, wraps ORM row materialisation |
| `SELECT` | **psycopg** | raw driver time only |
| `;` | **psycopg** | connection-setup statement; 4.6 ms fast, **28.7 ms** under load |

The SQLAlchemy span is a strict superset of the psycopg one, and the difference is real ORM work:

| query | SQLAlchemy | psycopg | ORM materialisation |
|---|--:|--:|--:|
| `SELECT users` (auth, fast trace) | 15.2 ms | 14.9 ms | 0.3 ms |
| `SELECT users` (auth, slow trace) | 71.7 ms | 71.5 ms | 0.2 ms |
| `SELECT factors` (fast) | 69.7 ms | 57.8 ms | **11.9 ms** |
| `SELECT factors` (slow) | 1338.4 ms | 1275.7 ms | **62.8 ms** |

#### What it costs

Redundant spans as a share of each trace:

| trace | spans | duplicate `SELECT` | `;` | **redundant** |
|---|--:|--:|--:|--:|
| pipeline stream 201.6 s | 779 | 204 | 103 | **307 (39 %)** |
| job stream 16.2 s | 86 | 21 | 11 | **32 (37 %)** |
| taxonomies (either) | 9 | 2 | 1 | **3 (33 %)** |
| upload 3.037 s | 816 | 1 | 1 | 2 (+805 per-chunk ASGI spans → 99 %, see §3.6) |

**Roughly a third to 40 % of every DB-touching trace is redundant** — paid on the event loop at
span-creation time, again at export, and again in Tempo storage. On the upload path the ASGI
per-chunk spans (§3.6) dominate instead, but the same fix applies: stop emitting spans nobody reads.

#### Recommendation: drop **psycopg**, keep **SQLAlchemy**

Not arbitrary. `connect` is a SQLAlchemy span, and it is the metric that will verify the §3.2
fix — dropping SQLAlchemy would delete the evidence for the highest-priority piece of work in this
document. Keeping SQLAlchemy also preserves ORM materialisation time, which is 62.8 ms on the slow
`factors` query and is genuine signal for §3.4. What you lose is pure-driver-vs-ORM attribution,
which is worth re-enabling temporarily if you ever need it.

Find where both are registered and remove one:

```
grep -rn "SQLAlchemyInstrumentor\|PsycopgInstrumentor\|Psycopg2Instrumentor" .
grep -rn "opentelemetry-instrument\|OTEL_PYTHON_DISABLED_INSTRUMENTATIONS" . Dockerfile* *.yaml
```

Two likely causes: both called explicitly in the telemetry setup module, or the
`opentelemetry-instrument` auto-loader is enabled **and** something calls `.instrument()` manually.
If it is the auto-loader, `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=psycopg` is a one-line env fix with
no code change.

⚠️ Do this **after** §3.2 is fixed and verified, not before — you want the `connect` spans present
while you are proving that pooling works, and a clean before/after comparison needs the span set to
stay constant.

#### Still open: sync or async

The driver is **psycopg v3**, confirmed by the instrumentation library name. But v3 supports both
sync and async and both use pyformat placeholders, so the statement text cannot settle it. Check
`create_async_engine` vs `create_engine`, and the DSN scheme. This matters for §3.10: a sync driver
on a single event loop makes every one of those 1338 ms `factors` queries a full stall.

### 3.9 P2 — `GET /v1/auth/callback` at 712–880 ms

Four samples, all sub-second but all slow, and it is on every login. Likely an outbound OIDC
token exchange to Keycloak (`enac-it-sso2`) inside the request. If that call is synchronous it
blocks the loop for ~800 ms — the same class of problem as the S3 calls but on a path every user
hits. Worth one trace to confirm.

### 3.10 P2 — Process topology

Bounds the blast radius of everything above.

- `replicas`, and uvicorn/gunicorn `--workers`. **One process ⇒ one event loop ⇒ 31 concurrent
  requests queue behind each other**, which is exactly §1.5. More workers do not fix the fan-out
  but divide the damage, and it ships today.
- `uvloop` + `httptools` — free throughput for an I/O-bound loop.
- Probe `timeoutSeconds` / `failureThreshold`; liveness should be trivially cheap and never touch
  the DB, so a slow query never triggers a restart.

---

## 4. Workstream B — Alerting & observability

Owner: #1402 / PR #1740. **Config and dashboards only.** Fully parallel with §3.

### 4.1 FIRST — is the current exclusion a no-op?

```promql
count by (http_target, http_route, http_method) (
  http_server_duration_milliseconds_count{namespace="svc1751d-co2-calculator-dev"}
)
```

- One series with empty `http_target` → the matcher excludes nothing, and has never done so. Use
  `http_route`.
- `http_route` absent too → nothing can be filtered by path; go straight to §4.3.

Paste the result into #1402. One query, and it decides whether months of "we filtered uploads and it
didn't help" measured anything at all.

### 4.2 p99 over `[5m]` on `dev` is not a usable statistic

- A few hundred requests per window ⇒ p99 is literally the slowest one or two requests. It will
  flap forever whatever you fix.
- `histogram_quantile` interpolates *inside* the matched bucket. Your tail reaches **201 s**;
  unless a finite `le` exceeds that, the number is arithmetically meaningless at the top end.
- `k8s_pod_name=~"$pod"` breaks across rollouts.

Use **proportion of fast requests** — no interpolation, no top-bucket problem, degrades gracefully
at low volume:

```promql
1 - (
  sum(rate(http_server_duration_milliseconds_bucket{
        namespace="svc1751d-co2-calculator-dev", route_class="api", le="1000"}[10m]))
  /
  sum(rate(http_server_duration_milliseconds_count{
        namespace="svc1751d-co2-calculator-dev", route_class="api"}[10m]))
)
```

Fire above ~2 % with `for: 10m`. Keep p99 on the dashboard as a diagnostic; do not alert on it.

### 4.3 Add a `route_class` label — in the collector, not the app

Negative regex on a free-form path is fragile. The ASGI instrumentation gives no hook for metric
attributes, so derive it downstream: a `transform` processor in the OTel Collector, or
`metric_relabel_configs` in the Prometheus scrape config. Config-only, no backend redeploy.

| `http_route` matches | `route_class` | Judged by |
|---|---|---|
| `/healthz`, `/readyz`, `/metrics` | `probe` | **canary for blocking** |
| `.*/stream$` | `stream` | session duration, TTFB |
| `.*upload.*`, `/v1/files/.*` | `upload` | throughput (MB/s) |
| `/v1/sync/(dispatch\|pipelines)$` | `job` | job runtime |
| everything else | `api` | **actual latency — the only SLO** |

Alert on `route_class="api"` only. Give `probe` **its own panel**: probe latency during a burst is
the single most valuable chart to come out of this work.

### 4.4 Stop measuring streams as latency

95 % of your request-time is in the wrong metric. Move it:

- `sse_stream_duration_seconds` — separate metric, buckets to 600 s. Never in the API histogram.
- `sse_time_to_first_event_seconds` — **this** is the real latency signal for a stream; sub-second.
  Alert on its p95.
- `sse_stream_terminations_total{reason="completed|client_disconnect|proxy_timeout|error"}` —
  a rise in `proxy_timeout` directly tests §3.3.
- `sse_connections_active` (gauge) — capacity signal.
- **`pipeline_duration_seconds`, labelled by `kind`** — a pipeline that legitimately takes 201 s is
  a product fact and belongs on a business dashboard with its own threshold. This is the metric that
  should carry the number currently landing in `LatencyP99High`.
- `db_connections_created_total` and `db_pool_checked_out` — §3.2 made visible. If pooling is fixed,
  the first should collapse from ~1-per-poll to near zero.

### 4.5 Also add

- `event_loop_lag_seconds` (§3.1) — the best single alert signal available here.
- `upload_duration_seconds` + `upload_bytes` → **throughput**. A 3 s upload is fine; a 3 s upload of
  200 kB is not.
- `db_pool_checked_out` / `db_pool_overflow` — tests the §3.2 pool-holding hypothesis directly.
- **`http_server_active_requests`** — would have shown the 31-request burst immediately.
- `http.request_content_length` on spans (§3.5).

### 4.6 The Sentry half of #1402

Say plainly in the issue that these cover different failure modes and neither replaces the other.
**Sentry catches errors; Prometheus catches degradation.** The 3.037 s upload and the 201.6 s zombie
stream both returned **HTTP 200** — Sentry would never have seen either.

---

## 4.7 The current PrometheusRules — why they fire, and what to change

Source: `standard-namespace-alerts` and `specific-namespace-alerts` in GitOps.

### 4.7.1 The three latency alerts fire on every import session, by construction

`LatencyP50High` / `P95High` / `P99High` all compute `histogram_quantile` over
`http_server_duration_milliseconds_bucket{namespace=…}` with **no route filter at all**.

The import workflow emits, per file:

```
POST /v1/files/temp-upload      normal
POST /v1/sync/dispatch          normal
GET  …/jobs/{id}/stream         6–36 s
GET  …/pipelines/{id}/stream    6–202 s
```

**Half the requests generated by an import are streams** — 48 stream vs 45 normal across the
sample. So during an import session the *median request is a stream*. `LatencyP50High > 1000ms`
is not detecting a problem; it is detecting that someone is using the product.

Replaying the sample in 5-minute windows exactly as the alerts compute it:

| window | n | p50 | p95 | p99 | fires |
|--:|--:|--:|--:|--:|---|
| 0–5 min | 75 | **1142 ms** | **36.1 s** | **201.6 s** | **P50 + P95 + P99** |
| 5–10 | 10 | 490 ms | 115.3 s | 115.3 s | P95 + P99 |
| 10–15 | 6 | **4066 ms** | 12.1 s | 12.1 s | **P50 + P95 + P99** |
| 20–25 | 9 | 298 ms | 869 ms | 869 ms | — |
| 25–30 | 11 | 156 ms | 394 ms | 394 ms | — |
| 30–35 | 15 | 283 ms | 431 ms | 431 ms | — |
| 35–40 | 73 | 261 ms | 12.1 s | 47.2 s | P95 + P99 |

Three alerts, one email group, `repeatInterval: 4h`, `sendResolved: true`. That is #1402.

Note also that when the p50 alert fires the value is **4066 ms** — the "value" in the email is a
quantile of a bimodal population (200 ms CRUD and 6 s streams). It is not a number anyone can act on.

### 4.7.2 `HaproxyRouteHighLatency` has the same defect, one layer down

```promql
avg by (route) (haproxy_backend_http_average_response_latency_milliseconds{...}) > 1000
```

An `avg` that includes a 201-second response. One zombie stream drags the route average over
1000 ms for the whole 5-minute window regardless of what else happened.

**This one is fixed for free by §3.3.** Creating the second, path-scoped Route for `/v1/sync`
(needed anyway for the HAProxy timeout) also splits the HAProxy metrics by route — after which this
alert can simply exclude the streaming route and start being meaningful.

### 4.7.3 `PodHighCPU` can never fire

```promql
rate(container_cpu_usage_seconds_total[5m]) / container_spec_cpu_quota > 0.9
```

`container_spec_cpu_quota` is the CFS quota **in microseconds per period** (typically 100000), not
a core count. The numerator is 0–N cores. The ratio is on the order of `1e-5` and will never exceed
0.9. **This alert has never fired and never will.** Correct form:

```promql
rate(container_cpu_usage_seconds_total{namespace="…"}[5m])
  / (container_spec_cpu_quota{namespace="…"} / container_spec_cpu_period{namespace="…"})
  > 0.9
```

Worth checking the same way whether the commented-out `PodMemoryNearLimit` was disabled because it
was noisy or because it was broken.

### 4.7.4 `HighErrorRate > 0.5` is set where it cannot help

A 50 % error rate is a total outage. By the time it fires, users have been failing for five minutes
and something else has already alerted. The HAProxy sibling rule in the same file uses **0.05** —
they should agree. Also: it lumps `4..` with `5..`, so a burst of 401s during an SSO redirect
counts as errors. Split them:

```yaml
- alert: BackendServerErrorRate
  expr: |
    sum(rate(http_server_duration_milliseconds_count{namespace="…", http_status_code=~"5.."}[5m]))
      / sum(rate(http_server_duration_milliseconds_count{namespace="…"}[5m])) > 0.02
  for: 5m
  labels: { severity: critical }
```

Keep a separate, higher-threshold `4xx` rule if client errors are worth watching at all.

### 4.7.5 Nothing detects silence

`Watchdog` is commented out and there is no `absent()` rule. **If the backend stops serving
requests entirely — or the OTel exporter dies — every one of these alerts goes quiet and that is
indistinguishable from health.** Add both:

```yaml
- alert: BackendNoTraffic
  expr: absent(http_server_duration_milliseconds_count{namespace="…"})
  for: 10m
  labels: { severity: critical }
  annotations:
    summary: "No request metrics from backend — app or OTel exporter down"

- alert: Watchdog          # uncomment the existing one
  expr: vector(1)
  labels: { severity: none }
```

Route `Watchdog` to a dead-man's-switch (healthchecks.io, Cronitor) that alerts when it *stops*
arriving. Without it, a broken Alertmanager is silent.

### 4.7.6 Smaller items

- **`namespace="svc1751d-co2-calculator-dev"` is hardcoded** in seven places in
  `specific-namespace-alerts`. Stage and prod are either uncovered or maintained as copies. Move it
  to a Kustomize overlay variable or an ArgoCD parameter.
- **`KubeJobNotCompleted` has no `for:`** — it fires on the first evaluation past 7200 s.
  Harmless here but inconsistent with the rest of the file.
- **`DeploymentUnavailable` for 10m** will fire on any rollout slower than 10 minutes, and during
  HPA scale-up. Consider `for: 15m` and excluding deployments mid-rollout.
- **Every latency and error alert is `severity: warning`.** Nothing in this file is `critical`
  except `PVCAlmostFull` and `ImagePullBackOff`, so severity carries no routing information (§4.8).

### 4.7.7 The replacement latency rules

After §4.3 lands `route_class`. Note `severity: critical` on the SLO breach — deliberate, so §4.8
can route it differently:

```yaml
- alert: ApiLatencySLOBreach
  expr: |
    1 - (
      sum(rate(http_server_duration_milliseconds_bucket{
            namespace="…", route_class="api", le="1000"}[10m]))
      /
      sum(rate(http_server_duration_milliseconds_count{
            namespace="…", route_class="api"}[10m]))
    ) > 0.02
  for: 10m
  labels: { severity: critical }
  annotations:
    summary: "More than 2% of API requests slower than 1s"
    description: "Streams, uploads and jobs are excluded. Value: {{ .Value }}"

- alert: ProbeLatencyDegraded          # the head-of-line-blocking canary (§4.3)
  expr: |
    histogram_quantile(0.95, sum by (le) (
      rate(http_server_duration_milliseconds_bucket{namespace="…", route_class="probe"}[5m])))
      > 500
  for: 5m
  labels: { severity: warning }
  annotations:
    summary: "Health probes are slow — event loop likely blocked"

- alert: EventLoopBlocked              # requires §3.1a
  expr: |
    histogram_quantile(0.99, sum by (le) (
      rate(event_loop_lag_seconds_bucket{namespace="…"}[5m]))) > 0.5
  for: 5m
  labels: { severity: warning }

- alert: DbConnectionChurn             # requires §4.5 — the regression test for §3.2
  expr: |
    rate(db_connections_created_total{namespace="…"}[5m])
      / rate(http_server_duration_milliseconds_count{namespace="…"}[5m]) > 0.5
  for: 10m
  labels: { severity: warning }
  annotations:
    summary: "More than one new DB connection per two requests — pooling regressed"

- alert: PipelineSlow                  # requires §4.4 — the number that used to fire LatencyP99High
  expr: |
    histogram_quantile(0.95, sum by (le, kind) (
      rate(pipeline_duration_seconds_bucket{namespace="…"}[30m]))) > 300
  for: 15m
  labels: { severity: warning }
  annotations:
    summary: "Pipeline p95 above 5 minutes ({{ $labels.kind }})"

- alert: SSEProxyTimeouts              # requires §4.4 — tests §3.3
  expr: rate(sse_stream_terminations_total{reason="proxy_timeout"}[15m]) > 0
  for: 15m
  labels: { severity: warning }
```

**Delete** `LatencyP50High`, `LatencyP95High`, `LatencyP99High`. Keep the percentiles on the
dashboard, split by `route_class`, as diagnostics. Do not alert on them.

⚠️ Ship the replacements **before** deleting the old ones, run both for a week, and compare fire
counts. "The new rules never fired" is a result you want to have measured, not assumed.

---

## 4.8 Alertmanager routing

Current config: one route, one receiver, `groupBy: [alertname]`, `repeatInterval: 4h`,
`sendResolved: true`, everything to `co2-calculator-sysadmins@groupes.epfl.ch`.

Consequences worth naming: a warning that stays firing sends **six emails a day**, and with
`sendResolved` a flapping alert sends two per cycle. `severity` is defined on every rule and used
by nothing. And there are no inhibitions, so a `PodCrashLooping` produces a crash email plus
latency emails plus error-rate emails describing the same event.

```yaml
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: alertmanager-email
spec:
  route:
    groupBy: ["alertname", "namespace"]
    groupWait: 30s
    groupInterval: 5m
    repeatInterval: 24h          # was 4h
    receiver: email-warning
    routes:
      - matchers:
          - name: severity
            value: critical
        receiver: email-critical
        repeatInterval: 4h
        groupWait: 10s
      - matchers:
          - name: alertname
            value: Watchdog
        receiver: deadmanssnitch
        repeatInterval: 5m

  inhibitRules:
    # a crashing or unready pod explains any latency/error alert in the same namespace
    - sourceMatch:
        - name: alertname
          value: PodCrashLooping
      targetMatch:
        - name: namespace
      equal: ["namespace"]
    - sourceMatch:
        - name: severity
          value: critical
      targetMatch:
        - name: severity
          value: warning
      equal: ["alertname", "namespace"]

  receivers:
    - name: email-critical
      emailConfigs:
        - to: "co2-calculator-sysadmins@groupes.epfl.ch"
          from: "noreply+co2-calculator-dev@epfl.ch"
          smarthost: "mail.epfl.ch:25"
          sendResolved: true
    - name: email-warning
      emailConfigs:
        - to: "co2-calculator-sysadmins@groupes.epfl.ch"
          from: "noreply+co2-calculator-dev@epfl.ch"
          smarthost: "mail.epfl.ch:25"
          sendResolved: false      # resolutions on warnings are noise
    - name: deadmanssnitch
      webhookConfigs:
        - url: "<healthchecks.io or Cronitor ping URL>"
```

Verify `inhibitRules` and nested `routes` against the `AlertmanagerConfig` CRD version on the
cluster — `v1alpha1` field support varies by OpenShift release, and a malformed
`AlertmanagerConfig` is **silently dropped**, which means no alerts at all. After applying, confirm
it was accepted (`oc -n openshift-user-workload-monitoring logs alertmanager-…`) and fire a test
alert before trusting it.

Two things to consider beyond email, given the volume this repo generates: a Mattermost/Slack
webhook for `warning` (with email reserved for `critical`), and `mute_time_intervals` for known
maintenance windows.


## 4.9 The Grafana dashboard ("Specific graphs", uid `ndr79mm`)

Five panels today. Two are actively misleading, one is excellent and under-used, and the panels
that would have shortened this investigation are missing.

### 4.9.1 Fix: "Latency percentile" (id 3)

Same defect as the alerts — **no route filter**, so a correct 201-second pipeline sits in the same
series as a 120 ms CRUD call. Split by `route_class` (§4.3) and the panel becomes readable:

```promql
histogram_quantile(0.95, sum by (le, route_class) (
  rate(http_server_duration_milliseconds_bucket{
    namespace="$namespace", route_class=~"$route_class"}[5m])))
```

Also on this panel:
- **Set `unit: ms`.** `fieldConfig.defaults` has no unit, so the axis currently shows bare numbers.
- The `thresholds` steps (`green: 0`, `red: 80`) are leftover defaults — 80 of what? — and
  `thresholdsStyle: off` means they render nothing. Either set a real threshold at your SLO
  (1000 ms) and turn the style on, or delete them.
- **Turn on exemplars.** Target A has `"exemplar": false`. With exemplars enabled and a trace
  datasource linked, a p99 spike becomes one click to the Tempo trace that caused it. Given how
  much of this investigation was manual trace hunting, this is the highest-value line in the file.

### 4.9.2 Fix: "Backend HTTP Error Rate" (id 2)

`http_status_code=~"4..|5.."` lumps client and server errors. A burst of 401s during an SSO
redirect looks identical to the backend failing. Split into two series — `5..` as the alarming one,
`4..` as informational — and set `unit: percentunit` so it reads as a percentage.

### 4.9.3 Fix: "HaproxyRouteHighLatency" (id 1)

An `avg` that includes 201-second responses. It becomes meaningful once `/v1/sync` has its own
Route (§3.3) and this panel excludes it.

### 4.9.4 Keep and extend: "DB Pool Usage" (id 7)

The best panel on the dashboard, and it settled a question this document got wrong twice. Extend it:

- Add `state="overflow"` — checkouts beyond `pool_size` are the early warning before exhaustion.
- Add a `db_pool_wait_seconds` histogram if SQLAlchemy exposes it (`PoolEvents` can feed one).
  `checked_out == size` tells you the pool is full; wait time tells you whether anyone *suffered*.
- The description hardcodes `DB_POOL_SIZE=15` in prose. The `size` series already plots it — trust
  the series, since the prose will drift.
- **Look at this panel during a report-page load.** §3.2 predicts `checked_out` pinning to `size`.

### 4.9.5 Fix the `$pod` variable

```
label_values({namespace="svc1751d-co2-calculator-dev"},k8s_pod_name)
```

Two problems. It has **no metric name**, so Prometheus matches every series in the namespace — an
expensive query that gets slower as cardinality grows. And pod names change on every rollout, so
saved links and dashboard state break.

```
label_values(http_server_duration_milliseconds_count{namespace="$namespace"}, k8s_pod_name)
```

While you are there, add a `$namespace` variable — the namespace is hardcoded in **all five**
panels, so stage and prod need a duplicated dashboard today. Same problem as §4.7.6 in the alert
rules.

### 4.9.6 Add: the panels that were missing

Ordered by how much time each would have saved during this investigation.

| Panel | Query sketch | Answers |
|---|---|---|
| **Per-route p50 / mean table** | `histogram_quantile(0.5, sum by (le, http_route) (rate(…bucket{route_class="api"}[5m])))` next to `rate(…sum)/rate(…count)`, table viz, sorted desc | §3.5b as a live view instead of a one-off export. **mean − p50 is the triage signal** (§3.5b) |
| **Requests in flight** | `http_server_active_requests` | Would have shown the 31-request fan-out (§1.5) instantly |
| **Probe latency, alone** | filtered to `route_class="probe"` | The head-of-line-blocking canary. Currently unmeasurable — no `/healthz` trace exists (§3.1) |
| **Event loop lag** | `histogram_quantile(0.99, …event_loop_lag_seconds_bucket…)` | The only clean test of the blocking hypothesis (§3.1) |
| **DB round-trip** | duration of the `;` pre-ping, as a metric | A pure network/DB-health probe: 4.6 ms idle → 28.7 ms under load (§3.2) |
| **Active SSE streams** | `sse_connections_active` | Capacity signal; also explains latency-panel shape |
| **Pipeline duration by kind** | `histogram_quantile(0.95, …pipeline_duration_seconds_bucket…)` | Where the 201 s belongs — a product metric, not an HTTP one (§4.4) |
| **Upload throughput** | `rate(upload_bytes) / rate(upload_duration_seconds)` | A 3 s upload is fine; a 3 s upload of 200 kB is not |
| **SLO burn** | `1 - (…le="1000", route_class="api" / …count)` | The number the alert fires on (§4.2) — always chart what you alert on |

### 4.9.7 Dashboard hygiene

- **Deploy annotations.** Traces in the 200-sample span two ReplicaSets — a rollout happened
  mid-window and nothing on the dashboard says so. An annotation query on
  `kube_deployment_status_observed_generation` changes makes every "what happened at 14:03" question
  answerable.
- **Row grouping**: `API latency` / `Streams & jobs` / `Database` / `Infrastructure`. Five ungrouped
  full-width panels already require scrolling; the list in §4.9.6 would make it unusable.
- **Chart what you alert on, alert on what you chart.** Right now the alerts use thresholds that
  appear nowhere on the dashboard, and the dashboard shows percentiles that will stop being alerted
  on after §4.7.7. Keep them in sync deliberately — a recording rule used by both is the usual way.
- Version the dashboard JSON in GitOps alongside the PrometheusRules if it is not already. It is at
  `version: 11`, which suggests it is being edited in the UI.

---

## 5. Workstream C — Upload & storage

**Demoted from v1.** Uploads are 1.1 % of request-time and this sample shows no measured impact on
anything else. Do §3.1–§3.4 first. Then:

### 5.1 The right question

Not "boto3 or PVC" but: **how much of the object-store round-trip must happen inside the user's
request?** Ideally none. The user needs to know the bytes are durably accepted — not the final
canonical location, the checksum, or the derived artefacts.

And you already have a job system: `dispatch` returns in 261 ms and pipelines run asynchronously.
Option 3 is mostly *reusing existing machinery*.

### 5.2 Options

| Option | Request latency | Blocking risk | Scaling | Effort |
|---|---|---|---|---|
| **0. Status quo** (sync boto3 in-request) | body + 476 ms | med | poor | — |
| **1. Async S3** (`aioboto3` / threadpool) | body + ~476 ms | **none** | good | **S** |
| **2. Local PVC** | body + disk write | low | ⚠️ see below | M |
| **3. Local staging + background job** | body only | low | good | M |
| **4. Presigned direct-to-S3** | **~0** | **none** | excellent | M–L |

### 5.3 On the PVC idea specifically

- **RWO vs RWX.** A `ReadWriteOnce` PVC binds to one node — the moment you scale past one replica
  (which §3.9 recommends) pods elsewhere cannot see the file. You need `ReadWriteMany`, i.e.
  NFS/CephFS at EPFL. **Confirm which storage classes actually exist** before designing around it.
- NFS write latency is not obviously better than S3, and unlike S3 it is a synchronous filesystem
  call — `aiofiles` moves it to a thread, it does not make it fast.
- You inherit quota, backup and orphan cleanup that S3 lifecycle rules give you free.
- It couples the app to node-local state, complicating rollouts and node drains.

**Verdict:** a fine *staging* area (option 3), a poor *destination*.

### 5.4 Sequencing

1. **Cheap:** option 1 — `aioboto3` or `run_in_threadpool`. Small diff, removes 476 ms of potential
   blocking, no architectural commitment.
2. Drop the redundant `HeadObject` calls and the second `PutObject` if not load-bearing (§3.6).
3. **Option 3:** `temp-upload` persists bytes, returns **202** + resource ID, enqueues the S3 move
   and post-treatment through the existing dispatch pipeline. Needs: idempotency keys, a durability
   decision (pod dies before the job runs?), retry policy, status endpoint.
4. **Target: option 4** — presigned direct-to-S3. The file never transits the app: no event-loop
   exposure, no temp files, no proxy timeouts, no percentile pollution, no memory pressure. Cost is
   a signing endpoint, a completion callback, CORS on the bucket. Given `s3.epfl.ch` is already the
   backend, this is very likely the correct end state.

Open questions before designing 3 or 4:

- Is the file **read again** later by the pipeline, and from where?
- Max accepted size; realistic production size.
- Does anything depend on the file being present **synchronously** after the upload response? If
  the frontend immediately calls `dispatch` with the file ID, a 202 changes that contract.
- Is `temp-upload` genuinely temporary — is there a promotion step, and is *that* the second
  `PutObject`?

---

## 6. Traces — received, and what is still missing

All four requested traces arrived and are analysed in
[§1.8](#18-what-the-four-traces-settled--including-two-corrections). They retracted two v2 findings
and confirmed a worse one. Remaining gaps, in order of value:

| Priority | What | Question it answers |
|---|---|---|
| **1** | `EXPLAIN (ANALYZE, BUFFERS)` on the `factors` query, both `data_entry_type_id` values | Missing index, or genuinely huge result set? Decides whether §3.4 is a one-line fix or a redesign. |
| **2** | A **prod** Tempo export, 15 min, during real concurrency | Everything measured so far is stage at an average of 0.5 concurrent streams. |
| **3** | A trace of `GET /v1/auth/callback` (~880 ms) | Synchronous Keycloak call inside the request? |
| **4** | Any `/healthz` trace, if one exists | Are probes instrumented at all? (§3.1) |
| **5** | A second upload trace nearer the 408 ms median | The one we have is the slowest of 22; its structure generalises, its duration does not. |

Not a trace, but higher value than most of the above: `SHOW max_connections` and the current
connection count on `co2-test.postgresql.dbaas.intranet.epfl.ch`, plus whether a pgbouncer sits in
front of it (§3.2).

---

## 7. Deliverables & definition of done

Ordering lives in [§0.5](#05-todo--in-priority-order). The observability track (P0-2, P1-1…P1-4) is
config and dashboards only and runs fully in parallel with the backend track — different people,
no shared blockers.

### Deliverables from the code agent

1. **Where the SQLAlchemy engine and sessions are created, and why every request opens a new
   connection** — with file:line. Is it `NullPool`, a per-request engine, or something else? This
   is the assignment; everything else is secondary.
2. `EXPLAIN (ANALYZE, BUFFERS)` output for the `factors` query at both `data_entry_type_id` values,
   plus the row counts and whether a `(data_entry_type_id, year)` index exists.
3. Both stream handlers annotated: session lifetime per poll, disconnect check, event
   de-duplication, lifetime cap (if any).
4. `pipelines.job_count` and per-job timings for `8aff966d-b4eb-4d64-ae56-68e16e0d8154`, and whether
   jobs run sequentially.
5. What the report/module view mounts in the Vue app, and why it produces ~31 parallel requests.
6. The full call path of `POST /v1/files/temp-upload`, each hop marked `async def` / `def` /
   threadpool, every blocking call flagged; plus whether the double S3 write is intentional.
7. Whether the psycopg v3 usage is sync or async (`create_async_engine`? DSN scheme?), and where
   the duplicate SQLAlchemy + psycopg instrumentation is registered.

### Done when

- [ ] §4.1 result posted to #1402
- [ ] **Zero `connect` spans inside request spans** — verified on a fresh trace of a stream and of
      an ordinary GET
- [ ] `SELECT factors` under 100 ms for every `data_entry_type_id`, or served from cache
- [ ] A page-load burst no longer amplifies the latency of *identical* queries (the 5× in §1.8)
- [ ] `route_class` deployed on dev; dashboard split; `probe` panel exists
- [ ] `LatencyP50/P95/P99High` deleted; `ApiLatencySLOBreach` running in parallel for a week first
- [ ] `PodHighCPU` unit bug fixed; `Watchdog` + `absent()` deadman live and verified by a test alert
- [ ] Alertmanager routes by `severity`, inhibits warnings under criticals, warnings at 24h repeat
- [ ] A full import session produces **zero** alert emails
- [ ] `event_loop_lag_seconds` exported and charted next to the probe panel
- [ ] Stream duration out of the API histogram
- [ ] Route timeouts reconciled with real stream lifetimes; `proxy_timeout` terminations ≈ 0
- [ ] #1402 updated with the §2 framing, or split in two

---

## 8. Other pistes

**Backend** — `uvloop`/`httptools`; HTTP/2 on the Route; gzip/brotli on the taxonomy payloads;
`orjson`; warm the DB pool at startup; split liveness (trivial, no DB) from readiness.

**Frontend / protocol** — resumable/chunked uploads (tus, or S3 multipart from the browser);
upload progress from the browser's own `XMLHttpRequest.upload` events rather than a server
round-trip; and seriously: **does this need SSE at all?** `GET /v1/sync/jobs/{id}` returning
`{status, progress}` polled every 2 s is *what the server is already doing internally* (§1.3) —
but with no long-lived connections, no proxy timeouts, no zombie risk, and no percentile pollution.
You would be moving the existing poll loop from the server to the client, where it is safe.

**Deployment** — a **separate Deployment for stream endpoints** (same image, own Route, own replica
count) isolates 95 % of request-time from the main API with no code change; HPA on
`sse_connections_active` rather than CPU; PodDisruptionBudget so a drain does not kill every stream.

**Observability** — tail-based sampling (keep 100 % over 1 s, sample the rest — you are paying for
805 spans per upload); exemplars linking histogram buckets to trace IDs; a synthetic canary every
10 s plotted alone; chart `retry_attempts` on the S3 spans.

**Process** — a k6/Locust scenario reproducing "page-load burst of 31 + N open streams + one
upload". Without it none of this is regression-testable and it comes back in six months.

---

## 9. Appendix

### 9.1 Provenance

- §1.1–§1.6: Grafana/Tempo table export, 200 traces, `svc1751t-co2-calculator-stage`, ~39.5 min
  window. Per-route stats, quantisation, pairing and concurrency computed directly from the
  `traceName` / `traceDuration` / `startTime` arrays.
- §1.7: `Trace-61b51f-2026-08-21_11_42_45.json`, OTLP, 816 spans, timings from
  `startTimeUnixNano` / `endTimeUnixNano`.
- §4.1: PromQL empty-label matching is documented behaviour — **verify empirically anyway**.

### 9.2 Known gaps — state these when reporting

- **The 200-row export is capped**, so counts are not rates.
- **Stage, not prod.** Peak 6 concurrent streams, average 0.5. Traces come from at least three
  different pods across two ReplicaSets (`5dbf497445`, `77c54889d5`), so a redeploy happened during
  the window — do not compare absolute timings across them too closely.
- **No probe traces exist** — probe latency has never been measured (§3.1b).
- **No payload size** anywhere — slow client vs large file is undecidable (§3.5).
- ✅ Two `/stream` traces have now been opened, and they **retracted** the v2 zombie-stream finding
  (§1.8). Duration arithmetic across mismatched scopes produced a confident, wrong conclusion —
  worth remembering before the next inference-only claim in this document.
- The upload-blocks-everything hypothesis is **untested, not disproven** (§1.6). No normal request
  in this sample overlapped an upload.
- §1.5's inside-vs-burst `taxonomies` comparison is **confounded**: the two traces differ in both
  concurrency *and* payload (`buildings/building` vs `purchase/other_purchases`). The correlation
  with burst size is real, but the mechanism turned out to be Postgres load and query cost, not
  event-loop queueing (§1.8). Treat the §1.5 table as a symptom map, not a causal claim.
- The 12-in-flight latency bucket (§1.5) is 16 samples largely from one burst, so it is confounded
  by time as well.
- Whether the 335 ms gap is a rollover, a GC pause or contention remains unresolved.

---

## 10. Machine-readable evidence

For an agent that wants the numbers without parsing prose tables.

```yaml
sample:
  source: Grafana/Tempo table export
  namespace: svc1751t-co2-calculator-stage
  traces: 200
  window_seconds: 2369
  total_request_seconds: 1249
  note: "export capped at 200 rows -> counts are shape, not rates"
  concurrency: {peak_streams: 6, avg_streams: 0.5}
  pods_seen: [5dbf497445-wt6pt, 77c54889d5-h5dwh, 77c54889d5-9sl6k]   # >=3 pods, 2 ReplicaSets

routes:            # name: [n, min_ms, p50_ms, mean_ms, p95_ms, max_ms, total_s]
  "GET /v1/sync/pipelines/{pid}/stream":            [23, 4072, 8164, 38971, 189830, 201623, 896.3]
  "GET /v1/sync/jobs/{jid}/stream":                 [25, 4060, 6190, 11552,  32260,  36079, 288.8]
  "GET /v1/taxonomies/module/{module}/{data_entry}": [16,  134,  948,   893,   2064,   2064,  14.3]
  "POST /v1/files/temp-upload":                     [22,  301,  408,   636,   1142,   3036,  14.0]
  "GET /v1/carbon-reports/{id}/modules/{m}/{sub}":  [29,  119,  249,   379,    936,   1004,  11.0]
  "POST /v1/sync/dispatch":                         [23,  198,  261,   301,    557,    814,   6.9]
  "GET /v1/auth/callback":                          [ 4,  712,  867,   832,    880,    880,   3.3]
  "GET /v1/carbon-reports/{id}/modules/{m}":        [13,  110,  199,   255,    517,    517,   3.3]
  "GET /v1/factors/{t}/class-subclass-map":         [11,  132,  254,   263,    396,    396,   2.9]
  "POST /v1/carbon-reports/{id}/modules/{m}/{sub}": [ 4,  354,  396,   407,    481,    481,   1.6]
  "GET /v1/backoffice/units":                       [ 3,  380,  394,   390,   null,    395,   1.2]
  "GET /v1/carbon-reports/simulator/explore/...":   [ 3,  139,  262,   368,   null,    703,   1.1]
  "GET /v1/sync/active-pipelines":                  [ 6,  130,  154,   155,    193,    193,   0.9]
  "GET /v1/year-configuration/{year}":              [ 5,  122,  155,   181,    252,    252,   0.9]
  "GET /v1/carbon-reports/{id}/modules/headcount/members": [3, 102, 156, 224, null, 415, 0.7]
  "GET /v1/modules-stats/{id}/report-stats":        [ 1, null,  298,  null,   null,    298,   0.3]
  "PATCH /v1/year-configuration/{year}":            [ 2,  102,  127,   127,   null,    152,   0.3]
  "GET /v1/modules-stats/{id}/validated-totals":    [ 1, null,  219,  null,   null,    219,   0.2]
  "GET /v1/carbon-reports/unit/{uid}/year/{year}/": [ 1, null,  217,  null,   null,    217,   0.2]
  "GET /v1/factors/{t}/list":                       [ 1, null,  164,  null,   null,    164,   0.2]
  "GET /v1/sync/pipelines":                         [ 1, null,  156,  null,   null,    156,   0.2]
  "GET /v1/auth/login":                             [ 1, null,  153,  null,   null,    153,   0.2]
  "PATCH /v1/project-plans/{plan_id}":              [ 1, null,  149,  null,   null,    149,   0.1]
  "GET /v1/connectors":                             [ 1, null,  122,  null,   null,    122,   0.1]

time_share: {pipelines_stream: 0.718, jobs_stream: 0.231, everything_else: 0.051}

workflow_per_file:      # counts line up ~1:1 => this is one journey repeated ~22x
  steps:
    - {route: "POST /v1/files/temp-upload",    n: 22, p50_ms: 408}
    - {route: "POST /v1/sync/dispatch",        n: 23, p50_ms: 261}   # correctly async
    - {route: "GET .../jobs/{id}/stream",      n: 25, p50_ms: 6190}
    - {route: "GET .../pipelines/{id}/stream", n: 23, p50_ms: 8164}
  stream_share_of_workflow_requests: 0.52
  consequence: "during an import the MEDIAN request is a stream => LatencyP50High > 1000ms fires by construction"

alert_replay:      # sample replayed in 5-min windows exactly as the current rules compute
  - {t: "0-5min",   n: 75, p50: 1142, p95: 36079, p99: 201623, fires: [P50, P95, P99]}
  - {t: "5-10min",  n: 10, p50:  490, p95: 115318, p99: 115318, fires: [P95, P99]}
  - {t: "10-15min", n:  6, p50: 4066, p95: 12130, p99: 12130,  fires: [P50, P95, P99]}
  - {t: "20-25min", n:  9, p50:  298, p95:   869, p99:   869,  fires: []}
  - {t: "25-30min", n: 11, p50:  156, p95:   394, p99:   394,  fires: []}
  - {t: "30-35min", n: 15, p50:  283, p95:   431, p99:   431,  fires: []}
  - {t: "35-40min", n: 73, p50:  261, p95: 12103, p99: 47174,  fires: [P95, P99]}

otlp_traces:
  cd7e88752c962450113f71394426b9ac:
    route: "GET /v1/sync/pipelines/{pipeline_id}/stream"
    target: /v1/sync/pipelines/8aff966d-b4eb-4d64-ae56-68e16e0d8154/stream
    duration_s: 201.623
    status: 200
    spans: {total: 779, connect: 103, semicolon: 103, select: 204, http_receive: 103, http_send: 61}
    poll_interval_s: {p50: 2.015, min: 0.006, max: 2.059}
    db_time_ms: {connect_total: 276, query_total: 570, query_p50: 2.5, query_max: 8.4}
    queries_per_poll: ["SELECT data_ingestion_jobs.* ...", "SELECT pipelines.* WHERE pipelines.id = %(id_1)s::UUID"]
    events_emitted: 61     # continuous to t+201.62, then clean close -> NOT a zombie
    silent_gaps_s: [16.1, 16.2]   # t+68.5->84.6, t+157.2->173.4  => needs keepalive
  d3b583702425af41b4b9b1139e90824:
    route: "GET /v1/sync/jobs/{job_id}/stream"
    target: /v1/sync/jobs/75/stream
    duration_s: 16.161
    spans: {total: 86, connect: 11, select: 21, http_receive: 11, http_send: 10}
    note: "watches ONE job; not comparable in scope to the pipeline stream above"
  c68e5936220188dafe2f2b757cd825b3:
    route: "GET /v1/taxonomies/module/{module}/{data_entry}"
    url: "?module=purchase&data_entry=other_purchases&year=2025"
    duration_ms: 2064.0
    pod: 77c54889d5-9sl6k
    phases_ms: {connect: 29.1, auth_select_users: 71.7, select_factors: 1338.4, tail_python: 683.6}
  cba57ecdd81eea9bed9c786fbd768de4:
    route: "GET /v1/taxonomies/module/{module}/{data_entry}"
    url: "?module=buildings&data_entry=building&year=2025"
    duration_ms: 134.5
    pod: 77c54889d5-h5dwh
    phases_ms: {connect: 5.9, auth_select_users: 15.2, select_factors: 69.7, tail_python: 51.4}
    note: "identical 4-span structure to the slow one => no N+1"
  a7cfb4771770744d748a82a12561b51f:
    route: "POST /v1/files/temp-upload"
    duration_s: 3.037
    status: 200
    caveat: "slowest of 22 uploads; p50 is 408 ms. Structure generalises, duration does not."
    spans: {total: 816, http_receive: 805, s3: 4, db: 4}
    phases: {body_ingest_s: 2.330, auth_db_ms: 8, s3_ms: 476, untraced_ms: 220}
    receive_chunk_ms: {p50: 0.236, p90: 6.08, p95: 8.39, p99: 12.67, max: 29.1}
    s3_calls: [{op: PutObject, ms: 286.4}, {op: HeadObject, ms: 18.4},
               {op: PutObject, ms: 68.9},  {op: HeadObject, ms: 9.6}]
    anomalies: ["object written twice", "auth runs after full body read at t+2.343",
                "unexplained 335 ms gap at t+1.424 with zero spans",
                "no http.request_content_length anywhere"]

instrumentation:
  active_db_instrumentors: [sqlalchemy, psycopg]     # both -> everything double-counted
  span_ownership:
    sqlalchemy: [connect, "SELECT app"]              # `connect` proves the T1 pooling defect
    psycopg:    ["SELECT", ";"]
  redundant_span_counts:     # trace: [total, dup_selects, semicolons, redundant, pct]
    pipeline_stream_201s: [779, 204, 103, 307, 0.39]
    job_stream_16s:       [ 86,  21,  11,  32, 0.37]
    taxonomies_2064ms:    [  9,   2,   1,   3, 0.33]
    taxonomies_134ms:     [  9,   2,   1,   3, 0.33]
    upload_3037ms:        [816,   1,   1, 809, 0.99]   # dominated by 805 per-chunk ASGI spans
  semicolon_span_ms: {fast_trace: 4.6, slow_trace: 28.7}
  recommendation: "drop psycopg instrumentor, keep sqlalchemy; sequence AFTER T1 verification"

alerting_current:
  prometheus_rules: [standard-namespace-alerts, specific-namespace-alerts]
  latency_alerts: {P50: ">1000ms/5m", P95: ">5000ms/5m", P99: ">10000ms/5m"}
  latency_alerts_route_filter: none      # <- the core defect
  haproxy_alert: "avg response latency by route > 1000ms/5m"   # includes 201 s responses
  error_alert_threshold: 0.5             # vs 0.05 on the HAProxy sibling; lumps 4xx with 5xx
  broken: [PodHighCPU]                   # unit bug, can never fire
  missing: [Watchdog, "absent() deadman"]
  alertmanager: {groupBy: [alertname], repeatInterval: 4h, sendResolved: true,
                 receivers: 1, severity_routing: none, inhibit_rules: none}
```
