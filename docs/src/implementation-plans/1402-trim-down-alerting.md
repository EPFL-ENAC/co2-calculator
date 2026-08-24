---
status: in-progress
issue: 1402
last_updated: 2026-08-24
title: "Split Grafana p99 Latency Alerting by Endpoint Class; Add GlitchTip Alerting"
summary: "Separate p99 latency alert thresholds for upload/job/pipeline endpoints from normal API calls, exclude SSE streams from duration-based alerting, and add error-rate alerting on GlitchTip."
---

# Split Grafana p99 Latency Alerting by Endpoint Class; Add GlitchTip Alerting

## Problem

The current Grafana p99-latency alert evaluates request duration across
**all** backend HTTP traffic with a single threshold. CSV upload
(`POST /api/v1/files`), pipeline dispatch/recalculation
(`POST /api/v1/sync/dispatch`, `/sync/units`, `/sync/units/recalculate*`,
`year-configuration` recalculation triggers), and job/pipeline polling
under `/api/v1/sync/*` are naturally slow (multi-second to multi-minute
ingestion work) and trip the alert on every use — which trains the team to
ignore it. Two SSE endpoints, `GET /sync/jobs/{job_id}/stream` and
`GET /sync/pipelines/{pipeline_id}/stream` (`backend/app/api/v1/data_sync.py:1378,1811`),
are long-lived connections; "duration" for a stream is meaningless and
will dominate any p99 bucket it's counted in.

No alert-rule or dashboard IaC exists in this repository. Grafana
dashboards/alert rules are provisioned in the ops repos
(`enack8s-app-config` / `openshift-app-config`) — referenced only by
comment in `helm/values.yaml:217`. This repo's own observability surface
is: (1) an OTel Collector scaffold in `docker-compose.yml` (OTLP receiver
→ Prometheus exporter on `:9464`, `otel/otel-collector-config.yaml`) with
no OTel SDK instrumentation wired into `backend/app` — the request-duration
histogram driving the current alert is produced by the ingress/router
layer (Traefik in compose, presumably the cluster ingress in prod), keyed
on path/router labels, not by in-process spans; and (2) frontend error
capture only — `@sentry/vue` in `frontend/src/boot/sentry.ts`, wired to
EPFL's self-hosted GlitchTip, `tracesSampleRate: 0.05`. The backend has
**no** Sentry/GlitchTip SDK (grep hits on "sentry" in `backend/app` are
false positives — `StaleStatsEntry`, `RecalculationStatusEntry` substring
matches). No GlitchTip alert rule (new-issue / error-rate notification) is
configured for the existing frontend project.

## Design

Path-based split is sufficient — no new backend instrumentation needed.
Route prefixes are already stable and semantically grouped
(`backend/app/api/router.py`):

- **Job/upload/pipeline group** (slow-by-design, alert on abuse/regression
  only): `POST /api/v1/files` (CSV upload), `/api/v1/sync/*` excluding the
  two stream routes (`dispatch`, `units`, `jobs/*`, `pipelines`, `workers`,
  `active-pipelines*`, `recalculation-status`), `/api/v1/year-configuration`
  recalculation-trigger POSTs.
- **Normal API group** (everything else): CRUD/read endpoints — `/units`,
  `/factors`, `/taxonomies`, `/carbon-reports`, `/modules*`, `/backoffice*`,
  `/locations`, `/audit`, `/workspace`, `/unit`, `/users`, `/auth`,
  `/session`.
- **Excluded from latency alerting entirely**: `GET /sync/jobs/{job_id}/stream`
  and `GET /sync/pipelines/{pipeline_id}/stream` — SSE, unbounded duration
  by design. If connection health needs monitoring later, do it via
  connection-count/error-rate, not duration.

Two alert groups replace the single rule, both defined in the ops repo
against the existing ingress/router-labeled duration histogram (exact
metric name to be confirmed against what the ops repo's current rule
already queries, since this repo doesn't own that config):

| Group                | Path match                                                                       | p99 threshold                                   | Eval window                                                        |
| -------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| Normal API           | not upload/sync/year-configuration-recalc paths, not `*/stream`                  | existing threshold (tight, e.g. 1-2s)           | existing                                                           |
| Jobs/upload/pipeline | `/files`, `/sync/*` (minus `/stream` routes), `/year-configuration/*recalculat*` | looser (e.g. 30-60s, tune from historical data) | longer (e.g. 15m) to smooth over legitimately bursty large uploads |

GlitchTip alerting: add a project alert rule on the existing frontend
GlitchTip project — new-issue notification and an error-rate-spike rule
(e.g. >N new events/5min) routed to the team's existing notification
channel (Slack/email — whatever the ops repo already uses for Grafana
alerts, for consistency). This is a GlitchTip project setting (UI/API on
the hosted instance), not code in this repo — no SDK change needed.
Backend error tracking (no Sentry/GlitchTip SDK exists there today) is out
of scope for this issue; flag as a follow-up if backend 5xx visibility is
needed beyond what's already surfaced via the frontend's HTTP-5xx
`captureMessage` path (`frontend/src/api/http.ts`).

## Contradictions found while executing (2026-08-21)

Per this plan's own output contract ("Contradictions: anything here that the
code disproves. Put this first."):

- **"No OTel SDK instrumentation wired into `backend/app`" (Problem section,
  above) is false.** `backend/Dockerfile:27,72` runs
  `opentelemetry-bootstrap -a requirements | uv pip install ...` and starts
  the app under `opentelemetry-instrument uvicorn ...`. Auto-instrumentation
  is active in every deployed pod (confirmed by the ops repo's own
  `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` / `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`
  env vars and by real SQLAlchemy/psycopg spans in the v3 traces below). The
  local dev `.venv` just doesn't have the bootstrap-installed instrumentors,
  which is why the original problem statement got this wrong.
- **T2's index hypothesis is refuted, and now settled.** `backend/app/models/factor.py:98-103`
  already has `Index("ix_factors_data_entry_type_year", "data_entry_type_id",
"year")`. Row counts (2026-08-21): `building`=846, `other_purchases`=20,915
  — ~25×, tracking the observed ~19× query-time / ~13× serialisation-time
  ratios. Confirmed genuine large-result-set cost, not an indexing gap.
  `values`/`classification` are both consumed by `ModuleHandlerService.get_taxonomy`
  (`backend/app/services/module_handler_service.py:76-124`), so narrowing the
  column list isn't free — the fix is caching with a real invalidation story
  (factors change on ingestion, not per request). Out of #1402's scope and a
  real architecture decision — filed as
  [co2-calculator#2258](https://github.com/EPFL-ENAC/co2-calculator/issues/2258)
  rather than improvised here.
- **P0-3/P0-4 — answered from source, then confirmed live.**
  `opentelemetry-instrumentation-asgi`'s `TraceMiddleware.__call__` records
  the old-semconv duration histogram (`name=MetricInstruments.HTTP_SERVER_DURATION`,
  unit `ms` — this is exactly `http_server_duration_milliseconds`) with
  `duration_attrs_old[HTTP_TARGET] = target` unconditionally set whenever a
  target is resolved. The P0-3 count-by query was then run against both dev
  and stage: **`http_target` is present and populated; `http_route` never
  appears.** The exclusion is written on `http_target`, not a guessed
  `http_route`. No longer blocked on anything.
- **§2's "the matcher is probably a no-op" — REFUTED.** The v3 plan's
  headline diagnosis was that `http_target!~"^.*upload.*$"` matched nothing
  because the label was absent, making every "we filtered uploads and it
  didn't help" conclusion meaningless. The live query disproves it: the
  label exists, and `/api/temp-upload` does contain "upload", so the old
  exclusion **did** exclude uploads. It was never a no-op — it filtered the
  wrong thing. §2's _second_ reason is the real one: uploads are 1.1% of
  request-time and streams were 95%, so excluding uploads removed almost
  nothing from the tail. Worth stating plainly because the no-op theory is
  what justified months of confusion, and it was wrong.
- **P0-6 ("we have never measured probe latency") — REFUTED.**
  `/api/healthz` and `/api/ready` both appear in
  `http_server_duration_milliseconds`. The
  `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS: "/api/health"` override is
  empirically a **no-op** — if it matched, those series would not exist.
  (Probable mechanism: kubelet hits the pod directly at `/healthz`, and the
  `/api` prefix exists only in the _synthesized_ `http.target`.) Probes are
  now `route_class="probe"` with their own panel. ⚠️ That no-op is
  load-bearing — "fixing" it would delete probe metrics and with them the
  head-of-line-blocking canary this whole investigation wanted.
- **The `/api`-prefix bug has a third instance, still open.** The
  collector's `tail_sampling` `drop-health` policy matches `http.target`
  exactly against `/health`, `/healthz`, `/ready`; the real values are
  `/api/healthz`, `/api/ready`. Exact match fails, and with
  `invert_match: true` the trace is **kept** — so probe traces are exported
  to Tempo on every probe interval on every pod, when the intent was to
  drop them. Same bug class as the two already fixed. Being fixed
  separately under #2049; recorded here because it belongs to the same
  root cause as everything else in this plan.

## Done (2026-08-21)

- [x] GlitchTip alert rule (new-issue / error-rate) confirmed configured on
      the hosted instance — done outside this repo.
- [x] `openshift-app-config` `dev`+`stage` overlays (branch
      `fix/1402-alerting-dev-stage`, uncommitted, **not pushed**):
  - Fixed the "DB Pool Usage" Grafana panel on stage — a copy-paste typo
    queried `db_pool_connections{namespace="svc1751d-co2-calculator-stage"}`
    (dev's `d` prefix + stage's suffix, a namespace that doesn't exist).
  - `HighErrorRate`: 0.5 → 0.02, scoped to `5..` only (was lumping `4..`),
    with a traffic-floor guard (`> 0.1 req/s`) so one 5xx in a quiet
    namespace can't read as a 100% error rate.
  - Added `BackendMetricsAbsent` (`absent(http_server_duration_milliseconds_count{...})`)
    as the in-band deadman — fires if the backend stops reporting entirely,
    which every other rule in the file silently depends on.
  - `PodHighCPU` disabled rather than "fixed": the quota/period math was
    wrong (divided by raw microseconds, ratio ~1e-5 vs threshold 0.9, could
    never fire) — but backend/worker set `requests.cpu` with no
    `limits.cpu` here (HPA targets are request-relative, e.g. 1600%), so
    `container_spec_cpu_quota` doesn't exist for these pods either way.
    Left commented out with the reason, rather than shipping a rule that
    still can't fire.
  - `Watchdog` left disabled: only useful wired to an external heartbeat
    consumer that alarms on its _absence_; nobody notices one more email in
    the shared receiver. `BackendMetricsAbsent` above is the alert that
    actually detects something.
  - `alertmanager-email.yaml` `repeatInterval`: 4h → 24h (a stuck `warning`
    was sending 6 emails/day).
  - Prod overlay untouched (scoped to dev/stage per instruction); prod's
    dashboard JSON doesn't even have the DB Pool Usage panel at all.
  - **PR [openshift-app-config#8](https://github.com/EPFL-ENAC/openshift-app-config/pull/8) — merged.**
- [x] Verified `http_target` live (dev + stage, `count by (http_target,
http_route, http_method) (http_server_duration_milliseconds_count{...})`):
      it's populated and already collapsed to a literal `/api/{tail}` (e.g.
      `/v1/sync/dispatch` → `/api/dispatch`, `/v1/year-configuration/{year}` →
      `/api/{year}`). `http_route` never appears. **Retraction (same day):**
      the first pass here claimed "an existing collector-side transform"
      does this collapse — checked the actual `otel-helm-chart` template and
      that's false. The only default processors are `filter` (health-check
      datapoint dropper keyed on `http.route`, which doesn't exist on this
      metric — a silent no-op the whole time, same bug class as #1402's
      original exclusion) and `tail_sampling` (traces only). Where the
      `/api` collapse actually happens is **still unconfirmed** — now
      tracked as its own follow-up, see below.
- [x] Added a `route_class` label per §4.3 — a `transform` processor in the
      collector's metrics pipeline sets `route_class` (`probe`/`stream`/
      `upload`/`job`/`api`) from `http_target`, once, before Prometheus
      export. Replaces the no-op `filter` processor for metrics;
      `tail_sampling` (traces) carried forward unchanged.
      `LatencyP50High`/`P95High`/`P99High` (dev+stage) now filter on
      `route_class="api"` instead of a per-rule suffix regex — this removes
      streams _and_ uploads _and_ jobs from the normal-API latency alert in
      one place, not three. Known fragility: the job/upload/probe
      classification still keys off `http_target` tail patterns (no
      `http_route` to match on), with a `POST`-only guard on the
      `year-configuration/{year}` tail to avoid catching GET/PATCH on the
      same tail.
      **PR [openshift-app-config#9](https://github.com/EPFL-ENAC/openshift-app-config/pull/9) — merged.**
- [x] Fixed a real classification bug in the above, found by querying the
      live label breakdown: `/healthz` and `/dispatch` were both landing in
      `route_class="api"` instead of `probe`/`job`. Root cause:
      `backend/app/main.py:324` sets `root_path=settings.API_DOCS_PREFIX`
      (`"/api"`, never overridden per-env), which the ASGI instrumentation
      prepends to _every_ target — confirmed via `/healthz` itself, which
      bypasses the Route/HAProxy entirely (kubelet hits the pod directly)
      and still showed up as `/api/healthz`, proving the prefix is app-side.
      The `probe`/`job` patterns were anchored assuming no prefix; `stream`/
      `upload` worked by accident (unanchored `.*` absorbed it). Fixed both
      anchored patterns to include `/api`. This landed _after_ #9 had
      already merged, so it's in a new PR:
      [openshift-app-config#10](https://github.com/EPFL-ENAC/openshift-app-config/pull/10) (merged).
- [x] Pulled real numbers instead of guessing:
  - `factors` row counts: `building`=846, `other_purchases`=20,915 — the
    1338 ms query is a genuine large-result-set problem, not a missing
    index — filed as
    [co2-calculator#2258](https://github.com/EPFL-ENAC/co2-calculator/issues/2258)
    (T2, out of #1402's scope, no code changed here).
  - `route_class="upload"` over 4 weeks of stage: p50 421 ms / p95 1807 ms /
    p99 4038 ms — clean, well-resolved.
  - `route_class="job"` over 4 weeks of stage: p50 60.8 ms, but **p95 and
    p99 both saturated at 10000 ms** — the histogram's highest finite
    bucket. Live instance of §4.2's exact warning: the true tail is
    unresolvable past that boundary, so a raw quantile alert there is
    meaningless.
- [x] Added `UploadLatencySLOBreach` (>2% of uploads over 5s) and
      `JobLatencySLOBreach` (>5% of job-class requests over the 10s bucket,
      since that's the last one this histogram can resolve) — proportion-
      of-slow-requests per §4.2, not a raw quantile, with a traffic floor
      on both. PR [openshift-app-config#10](https://github.com/EPFL-ENAC/openshift-app-config/pull/10) (merged).
- [x] Found and fixed a second tail collision, same class as the
      `year-configuration/{year}` one: `GET /v1/units` (plain CRUD list,
      meant to stay `api`) and `POST /v1/sync/units` (recalculation
      trigger, meant to be `job`) both collapse to the identical
      `http.target = "/api/units"` — `GET` was silently landing in
      `route_class="job"`. Same `http.method` guard pattern. PR
      [openshift-app-config#11](https://github.com/EPFL-ENAC/openshift-app-config/pull/11) (merged).
- [x] Filed the general fix as a follow-up rather than patch every
      collision as it's found:
      [co2-calculator#2260](https://github.com/EPFL-ENAC/co2-calculator/issues/2260)
      — two `http.method`-guarded collisions found live in one session is a
      pattern, not a coincidence. Proposes either enabling OTel's new
      semconv (`http.route`, which should carry the real unique template
      instead of the collapsed/collision-prone `http.target`) or
      restructuring router prefixes so no two routers can produce the same
      leaf shape. Root cause of the `/v1/<router-prefix>` disappearing in
      the first place still isn't confirmed — flagged as the first step of
      whichever direction gets picked.
- [x] Split the Grafana "Latency percentile" panel by `route_class` (§4.9.1)
      — done, PR [openshift-app-config#10](https://github.com/EPFL-ENAC/openshift-app-config/pull/10):
      `sum by (le, route_class)`, `unit: ms` (was unset), a real 1000ms
      threshold line (was a leftover unrendered default), exemplars on
      (were off). Dashboard version bumped for both overlays.
- [x] Added the `route_class="probe"` panel — PR
      [openshift-app-config#12](https://github.com/EPFL-ENAC/openshift-app-config/pull/12)
      (merged). The plan expected this to need a new backend metric; it
      didn't, because probes were already instrumented (P0-6 correction
      above). Probe latency during a burst is the direct picture of
      head-of-line blocking, and it is now charted.

## Status

**#1402's functional scope is complete and live in dev + stage.** All four
alerting/dashboard PRs are merged (ops
[#8](https://github.com/EPFL-ENAC/openshift-app-config/pull/8),
[#9](https://github.com/EPFL-ENAC/openshift-app-config/pull/9),
[#10](https://github.com/EPFL-ENAC/openshift-app-config/pull/10),
[#11](https://github.com/EPFL-ENAC/openshift-app-config/pull/11)), plus the
probe panel ([#12](https://github.com/EPFL-ENAC/openshift-app-config/pull/12)).

What remains is **not code** — it is one observation that can only be made
while a real import is running, and a short ops note. Both are listed as
unchecked in Steps below. The issue should not close until the import
verification has actually been done: the whole failure mode this plan warns
about is shipping the measurement fix, watching the emails stop, and
declaring victory.

## Steps

- [x] Confirm in the ops repo which metric/labels the current p99 alert
      queries — **confirmed live**: `http_target` is populated on
      `http_server_duration_milliseconds`; `http_route` is not.
- [x] Add `route_class` in the collector (§4.3), not per-alert regex — done,
      see Done section above.
- [x] Exclude `/sync/jobs/{job_id}/stream` and `/sync/pipelines/{pipeline_id}/stream`
      (and uploads and jobs) from the normal-API latency alerts via
      `route_class="api"` — done, PR
      [openshift-app-config#9](https://github.com/EPFL-ENAC/openshift-app-config/pull/9)
      (merged).
- [x] Pull 2-4 weeks of historical p99 for `route_class="upload"`/`"job"` and
      set a threshold from it — done, see Done section above.
- [x] Add the `route_class="upload"`/`"job"` latency alert — done
      (`UploadLatencySLOBreach`, `JobLatencySLOBreach`), see Done section.
- [x] Split the Grafana "Latency percentile" panel by `route_class` (§4.9.1)
      — done, PR [openshift-app-config#10](https://github.com/EPFL-ENAC/openshift-app-config/pull/10):
      `sum by (le, route_class)`, `unit: ms` (was unset), a real 1000ms
      threshold line (was a leftover unrendered default), exemplars on
      (were off). Dashboard version bumped for both overlays.
- [x] `route_class="probe"` panel (§4.9.6) — done, PR
      [openshift-app-config#12](https://github.com/EPFL-ENAC/openshift-app-config/pull/12)
      (merged). Needed no new metric after all: probes turned out to be
      instrumented already (see the P0-6 correction above), so this is the
      head-of-line-blocking canary the plan asked for, live on both
      overlays. Threshold line at 500ms — a probe should be trivially cheap
      regardless of what else the pod is doing.
- [ ] A `pipeline_duration_seconds` business metric/alert (§4.7.7's
      `PipelineSlow`) — **not done, and gated.** Unlike the probe panel this
      genuinely needs a new backend metric, which means hooking pipeline
      completion in `runner.py` / `_chain.py` / `_pipeline_reconciler.py` —
      recalculation internals, which the guardrails gate on a written plan
      reviewed by both maintainers, however additive the metric itself is.
      Tracked as C4 in
      [2049-optimize-pipeline-performance.md](2049-optimize-pipeline-performance.md).
      This is the metric that should eventually carry the 201s number that
      used to fire `LatencyP99High` — a 3.4-minute pipeline is a product
      fact and belongs on a business dashboard, not in an HTTP histogram.
- [ ] Re-verify the tail-based classification (`dispatch`, `units`,
      `jobs.*`, `workers`, `active-pipelines.*`, `recalculation-status`,
      `pipelines.*`, `health/stale-stats`, `admin/recompute-stats`,
      `temp-upload`) against real traffic once a pipeline actually runs in
      stage — a wrong regex here silently mis-classifies requests, the same
      failure mode this plan already flagged for the old `http_target`
      no-op. (The `/healthz`/`dispatch` and `units` bugs above were exactly
      this failure mode, caught twice, worth checking again with a real
      import.)
- [x] Configure a GlitchTip alert rule on the frontend project — done
      outside this repo.
- [x] Document the two alert groups and thresholds in a short ops note, so
      the split isn't tribal knowledge living only in the ops repo. Done:
      [infra/03-observability-slo.md](../infra/03-observability-slo.md).
- [ ] Verify: trigger a CSV upload and a normal read endpoint in
      stage/prod-like env, confirm only the jobs/upload/pipeline group's
      threshold applies to the upload and the normal-API group stays tight
      for the read call; confirm the SSE stream endpoints never fire either
      alert regardless of connection duration.

## 2026-08-24 update

- [x] **Prod parity.** Prod never got the `route_class` transform (2049
      already noted it as "live in dev+stage" only) — its collector metrics
      pipeline was still on the chart-default `filter` (the same no-op class
      of bug this plan found once already: it matches `http.route`, which
      doesn't exist on this metric). Shipped: the `transform` processor,
      the same route_class-split dashboard panels, `route_class="api"`
      scoping on `LatencyP50/95/99High` (which also fixes a separate bug —
      `sum by (le, k8s_pod_name)` computed a per-pod quantile, firing on any
      single replica), and `BackendMetricsAbsent`. Thresholds left
      untouched: scoping to `api` only removes slower traffic from the
      distribution, so the same threshold is strictly less likely to fire —
      a scope fix, not a sensitivity change.
- [x] **`HighErrorRate` retuned from real data, all three environments.**
      Pulled 4-week 5xx/total on 2026-08-24: dev 0.081%, stage 0.0085%,
      prod 0.0012% (1 in ~83,600 requests). Prod's old 4xx+5xx@50% was an
      outage threshold, never revisited — now 5xx-only@1% (~800x headroom
      over its real baseline); dev/stage keep their existing 5xx-only@2%.
      All three shared the same per-pod bug as the latency alerts —
      `sum by (k8s_pod_name)` on both sides of the ratio fired on any
      single replica breaching — fixed to a global ratio everywhere.
- [x] **New alert: `ErrorRateSustainedElevated`, all three environments.**
      `HighErrorRate`'s 5-minute window and traffic floor structurally
      can't see a persistent low-grade error rate — it never looks
      anomalous in any single slice. Same 5xx ratio, evaluated over a
      rolling 6h `increase()` window at 0.3% (~4x dev's own noisiest
      baseline), `for: 30m`. `severity: info`, not `warning` — the
      alertmanager config here is a single flat email route with no
      severity-based sub-routing, so this doesn't page differently, it
      just doesn't get lost as another `warning`.
- [ ] **Not shipped to prod, blocked on data:** `UploadLatencySLOBreach` /
      `JobLatencySLOBreach`. The transform just started running in prod —
      no `route_class="upload"`/`"job"` history exists yet to set a
      threshold from. Same rule this plan already applied once for stage
      (§ "Pulled real numbers instead of guessing"): pull 2-4 weeks of real
      prod data before setting a number, don't copy stage's.
- [x] **Dev-only visibility gotcha, not a pipeline bug.** The dev
      `route_class` panel appeared blank for `stream`/`job`/`upload` over a
      12h window despite the data existing — confirmed via
      `histogram_quantile` returning `NaN` per class (zero counter increase
      in that specific trailing `[5m]`, not a broken transform). Two
      independent causes stacked: (1) idle 5-minute rate windows are normal
      for dev's low, manual-testing-driven traffic on non-probe classes;
      (2) a `timeseries` panel doesn't render an isolated non-null point
      surrounded by `NaN` unless `showPoints` is `always`. Fixed on the dev
      and stage panel only: `showPoints: "always"`, rate window `[5m]` →
      `[30m]`.
- [ ] **Open question, not yet confirmed:** the `tail_sampling` `drop-health`
      policy (dev/stage) matches literal `/health`/`/healthz`/`/ready` on
      `http.target` — no `/api` prefix. This plan already proved that prefix
      is present on every request's `http.target` for the _metrics_ side,
      but explicitly left `tail_sampling` "carried forward unchanged" and
      never checked it for traces. Surfaced when a 250ms probe-latency spike
      (visible on the `route_class="probe"` panel) had no matching trace in
      Tempo. Whichever way the prefix bug cuts, an unconditional
      string-match allow/deny list can only ever be "always drop" or
      "always keep everything" — it can't keep the anomalous probe trace
      while dropping the routine ones, which is the one case worth having
      the trace for. Recommend replacing it with a latency-conditioned
      composite policy. Not yet implemented — pending confirmation this is
      wanted, since it changes trace volume/cost in prod too.

## Related

The trace investigation behind this plan (200 Tempo traces + 5 OTLP
traces) also surfaced a wider set of backend performance findings —
connection pool `pre_ping` cost, the `factors` query, 2s stream polling,
duplicate OTel instrumentation, the upload path — that are out of #1402's
scope (alerting, not performance). Those are now tracked in
[2049-optimize-pipeline-performance.md](2049-optimize-pipeline-performance.md)
(issue #2049), not duplicated here.
