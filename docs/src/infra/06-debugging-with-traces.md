# Debugging With Traces

Six recipes for turning a symptom into a cause with Tempo, the per-env
Grafana "specific graphs" dashboard, GlitchTip and the OpenShift console
log view. Every step below is reconstructed from a plan or an issue where
it was actually done; the steps nobody has done yet are marked
**UNVERIFIED** so you know which part you are testing for the first time.
Links to the tools are in [Operations](04-operations.md#links-per-environment).
This is a multi-procedure runbook and runs past the usual page budget.

## What the signals can and cannot do

- **Tempo** ([enac-k8s-grafana](https://enac-k8s-grafana.epfl.ch/), Explore,
  Tempo data source). Services are `backend` and `worker`; every span
  carries `k8s.pod.name` and `k8s.namespace.name`. The collector stamps
  `route_class` (`api`, `probe`, `stream`, `upload`, `job`) on server
  spans, so `{ span.route_class = "api" }` works. Sampling is `always_on`
  in all three environments; prod's is temporary, revert by 2026-09-17.
  Backend traces carry psycopg query spans with `db.statement` in all
  three environments. Worker traces carry them on **dev and stage only**:
  the prod worker runs the chart default, so a prod job trace is the job
  span with nothing under it. Reproduce a slow prod job on stage to see
  its SQL.
- **Trace duration is not request duration.** Since #2372 the browser
  keeps one trace id per navigation, so a "trace" spans the whole page
  session. Read **server-span** durations, table type _spans_, never the
  trace total ([plan 2449](../implementation-plans/2449-plan-cascade-jobs.md)).
- **Logs and traces do not join by id.** The backend puts no trace id in
  its JSON logs or response headers. The pivot is `k8s.pod.name` plus the
  timestamp: read them off the span, then filter the console log view to
  that pod and minute.
- **GlitchTip** events carry `contexts.trace.trace_id`. Copy the
  `trace_id`, never the `span_id`, which matches no backend span. Whether
  that `trace_id` finds its backend spans in Tempo is **UNVERIFIED**
  end to end. Last attempt, 2026-09-07: an id from a 2026-08-25 event
  (before #2372 shipped) returned `Not Found`, which proves nothing. Test
  with an event less than a day old.
- **Background jobs** are one span named `job <type>` with `job.id`,
  `job.type`, `pipeline.id` ([plan 2371](../implementation-plans/2371-job-runner-otel-span.md)).
  Job types: `aggregation`, `reference_ingest`, `emission_recalc`,
  `module_emission_recalc`, `simulator_plan_prefill`, `csv_ingest`,
  `api_ingest`, `factor_ingest`, `unit_sync`.

The TraceQL that was actually typed during #2049, verbatim:

```text
{ duration > 30s && resource.k8s.namespace.name = "svc1751d-co2-calculator-dev" }
```

with table type _spans_ and limit 200. Swap the namespace and the
threshold; that query is the backbone of recipes 1, 2 and 5.

## 1. A user reports a slow page

Trigger: "the page hangs" or a ky timeout toast. ky gives up at 10 s; the
backend keeps running, so the span still lands in Tempo later.

1. Tempo, last 24 h, spans table, sorted by duration:

   ```text
   { resource.service.name = "backend" && span.route_class = "api" && duration > 5s }
   ```

   Without the `route_class` filter the result fills with
   `GET /v1/sync/pipelines/{id}/stream` spans that run 6 to 170 s by
   design ([plan 2449](../implementation-plans/2449-plan-cascade-jobs.md)).

2. Open the slowest server span and compare it with its children. Two
   shapes seen so far:
   - **One SQL span is the request.** #2404: a 14 192 ms `GET
.../modules/purchase/it_equipment?page=1&limit=20` had 23 spans, the
     `data_entries` SELECT took 14 149 ms and the `count(*)` on the same
     filter 3 ms. Copy `db.statement`, run `EXPLAIN (ANALYZE, BUFFERS)`
     on it, look for a correlated subquery or a planner estimate that is
     off by orders of magnitude (2 vs 4 000 rows there). Fix was indexes
     plus page-first querying.
   - **Many cheap spans, one page.** #2360: GlitchTip breadcrumbs showed
     about 12 failed GETs in one burst, 7 of them the identical
     `.../simulator/explore/unit/455/reference-year/2025/` lookup. A HAR
     from the browser confirmed 48 API calls on one load, 35 unique, with
     server TTFB summing to 15.1 s and client queueing to 0.3 s. That is
     a frontend stampede, fixed by an in-flight promise cache. Confirm
     with the Network tab, not with Tempo.
3. If the request is a job or a stream, use `{ span.job.type = "..." }` or
   `route_class = "stream"` instead; latency alerts exclude those on
   purpose.

## 2. A 5xx alert fires

Trigger: `HighErrorRate` or `ErrorRateSustainedElevated` mail, or
`HaproxyHighErrorRatePerRoute`.

1. Grafana "specific graphs", panel **Backend responses by exact status
   code (OTel)**, then **Backend route - HTTP responses by status class
   (HAProxy)**. If HAProxy shows 5xx and OTel shows none, the backend
   never saw the request: pods or Route, go to
   [Operations](04-operations.md#ours-symptom-cause-action).
2. Tempo, same window, spans table:

   ```text
   { resource.service.name = "backend" && span.http.status_code >= 500 }
   ```

   **UNVERIFIED**: the attribute name `http.status_code` follows the
   same old semantic-convention set the collector already matches on
   (`http.target`, `http.route`); confirm once on a live 500 and delete
   this note.

3. Read the exception on the span's events. For a Pydantic response
   validation error, GlitchTip is faster: #2226 arrived as a GlitchTip
   event whose body already held the URL, method, status 500 and
   `ValidationError ... standby_power_w ... got a number with a
fractional part`. The fix was a type widening; no trace needed.
4. `{ resource.k8s.namespace.name = "..." && span.http.status_code >= 500 }`
   over 6 h tells you whether it is one route or everything. Everything
   at once with `FATAL: remaining connection slots` in the message is
   recipe 4.

## 3. A 403 wave

Trigger: several users lose access at once, `RoleSyncSuspiciousEmpty`
or `RoleSyncProviderUnavailable` fires.

This one is diagnosed from **logs, not traces**: the request that did
the damage returned 200, and the 403s come later on other requests
([plan 2531](../implementation-plans/2531-role-sync-empty-response-wipe.md)).

1. OpenShift console log view, application logs, search the message
   `Fetched roles from Accred API` for the affected user. Read
   `total_authorizations` and `co2_roles` on that line.
   - `total_authorizations > 0` and `co2_roles == 0`: the mapping dropped
     every authorization. Look for the neighbouring warnings
     `Authorization missing accredunitid, skipping` or
     `Authorization missing cf, skipping`: they name the field that moved
     on the provider side.
   - Both zero: the provider returned nothing. Since #2531 the guard
     refuses to persist that, and #2623 counts it as
     `role_sync_skipped_total{outcome=...}`, which is what the two alerts
     watch.
2. `backend/scripts/diagnose_accred_roles.py <sciper>` reproduces the
   mapping for one user from a pod.
3. Tempo adds nothing here except confirming the user's earlier requests
   returned 200: filter `{ span.user.id = "<id>" }` (the attribute is set
   on the current span at auth time).

## 4. `DbPoolCheckoutTimeout` fires

Trigger: `DbPoolCheckoutTimeout`, `DbServerConnectionsHigh`,
`DbServerConnectionSlotsExhausted`, or every request failing with
`FATAL: remaining connection slots are reserved`.

1. Grafana "specific graphs", panels **DB Pool Usage** and **Total DB
   connections vs Postgres max_connections (100)**. Read the _total
   open_ series against the 100 line, not the pod ceiling: on
   2026-08-31 `checked_out` peaked at a healthy 13 fleet-wide while the
   server was full, because 53 of 85 connections belonged to pods that no
   longer existed ([plan 2566](../implementation-plans/2566-db-pool-disposal-and-visibility.md),
   "Why no dashboard caught it").
2. If total open is near the ceiling and pool usage is low, orphans. From
   psql:

   ```sql
   select client_addr, backend_start, state, count(*)
   from pg_stat_activity where datname = current_database()
   group by 1, 2, 3 order by 2;
   ```

   Clusters of `backend_start` older than the newest ReplicaSet are pods
   that died without `engine.dispose()`. That path is fixed; if you see it
   again the fix regressed.

3. If pool usage is high and total open is fine, real saturation: Tempo,
   `{ resource.service.name = "backend" && duration > 5s }` in the
   window. On 2026-09-03 Tempo listed 26
   `GET /v1/sync/pipelines/{id}/stream` requests all ending at 5.0x s
   with `QueuePool limit ... timeout 5.00` ([plan 2654](../implementation-plans/2654-csv-sync-connection-lost-toast.md)).
   Long streams holding connections during a recalculation is the known
   shape; read [plan 1723](../implementation-plans/1723-job-concurrency-and-db-pool.md)
   before changing pool sizes.

## 5. Timeout with no trace

Trigger: a 504 or a client timeout, and the Tempo search for that route
and minute returns nothing.

Five known reasons, in the order to eliminate them:

1. **Client gave up, server finished later.** ky times out at 10 s, the
   backend route timeout is 10 min. Widen the time window to +5 min and
   search `{ duration > 10s }` again.
2. **The pod restarted mid-request.** In-flight spans die unexported.
   Grafana panels **Container restarts (15m increase)** and **OOM kills**,
   or `increase(kube_pod_container_status_restarts_total{namespace="..."}[15m])`
   in Explore. This was the 2026-08-25 stage incident (#2360).
3. **Early spans dropped on export.** #2050 saw a `PATCH
/v1/project-plans/8011/years/2025` 504 after 91.5 s with about 70 s
   before the first captured span, and a 31.8 s hole with zero spans in
   another. The gap is real time; the trace is just missing it. Fall back
   to the pod's logs for that minute.
4. **The work is invisible to instrumentation.** `COPY FROM STDIN` is not
   traced by psycopg instrumentation (#2050 Track F0: an 18.5 s gap with
   zero DB spans). Worker traces on prod have no DB spans at all.
5. **The worker's exporter timed out.** #2449 found `DEADLINE_EXCEEDED`
   to `otel-collector:4317` on the worker pod; its traces were partial.
   `oc logs deploy/co2-calculator-worker -n <ns> | grep DEADLINE`.

A 504 at exactly 30 s used to mean the HAProxy router default; the
backend route now carries a 10-minute timeout. Server-side signals can
still log a success for a request the client already abandoned
(half-closed socket, #2147), so a clean trace does not prove the user
got a response.

## 6. A frontend error lands in GlitchTip

Trigger: GlitchTip mail or the Teams channel.

1. Read the event first. It has the failing URL, method, status, the
   response body, `componentName` and `propsData`, and breadcrumbs of the
   requests before it. #2226 (a 500) and #2360 (a burst of identical
   GETs) were both solved from the event alone.
2. Copy `contexts.trace.trace_id`. In Tempo, paste the bare 32-hex id as
   the TraceQL query, or use the spans table with:

   ```text
   { trace:id = "<trace_id>" && resource.service.name = "backend" }
   ```

   **UNVERIFIED**: expected to return the backend spans of that
   navigation since #2372. Report the result on the issue either way.

3. No hit and a status 5xx in the event: fall back to the route and
   timestamp, recipe 2 step 2.
4. Stack traces are minified: source maps are not uploaded (#1101). Match
   the `componentName` to the component instead.

## When you learn something new

Add the recipe here in the same PR as the fix, with the trace id or
GlitchTip issue number that proves it. A recipe without a citation is a
guess; this page holds none.
