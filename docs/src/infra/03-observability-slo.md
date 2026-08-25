# Observability & SLOs

What we alert on, why, and where the coverage still has gaps. For how the
`route_class` label itself came to exist, see
[1402 — trim down alerting](../implementation-plans/1402-trim-down-alerting.md);
for the pipeline-performance follow-ups, see
[2049 — optimize pipeline performance](../implementation-plans/2049-optimize-pipeline-performance.md).
This page is the durable "what's live now" reference; those plans are the
history of how we got here.

## The `route_class` label

Every backend request produces `http_server_duration_milliseconds` in
Prometheus, labelled by `http_target` and `http_status_code`. On its own
that's not enough to alert on: a 34-minute SSE stream and a 40ms health
check land in the same histogram. The ops-repo OTel Collector adds a
`route_class` attribute (`api` / `probe` / `stream` / `upload` / `job`) via a
`transform` processor, derived from `http.target` pattern-matching — before
the metric ever reaches Prometheus. Alerts and dashboard panels filter or
split on this label instead of guessing per-route regexes.

**`route_class="stream"` is deliberately excluded from all latency
alerting.** Stream duration tracks the underlying job's duration by design —
seconds for a small import, tens of minutes for a large one — so there is no
meaningful "too slow" threshold for the class as a whole. The histogram's
last finite bucket is 10s; anything past that is bucketed as unresolvable
`+Inf`, so a raw quantile on `stream` isn't just unhelpful, it's not
computable in a useful way. If a real stream-specific problem needs
detecting, it needs a different signal than request duration (e.g. a stuck
job, covered by the `job`-class alerts and the pipeline's own health
metrics), not a latency SLO.

## Probe trace sampling

Metrics (`route_class`) and traces (Tempo, via `enac-it-otel`) are separate
signals from the same span data, sampled independently. The collector's
`tail_sampling` `drop-health` policy was meant to cut health-check trace
noise, matching literal `/health`/`/healthz`/`/ready` on `http.target` -- no
`/api` prefix. Every request's `http.target` actually carries that prefix
(same fact 1402 already proved for the metrics side), so the literal match
never fired: with `invert_match: true`, the policy was a total no-op --
every trace was already being kept, health and non-health alike, and none
of the intended noise reduction was happening.

Independent of that bug, a flat allow/deny list could never keep an
anomalous slow probe's trace while dropping the routine fast ones anyway --
found while chasing a ~400ms P99 spike on the probe latency panel with no
matching trace in Tempo. Fixed in **dev only** with a composite policy:
non-health traffic is always kept (unchanged), health/probe traffic is kept
only if a span exceeds 200ms, or by a light 5% sample otherwise. Not yet
promoted to stage/prod -- verify in dev first (a deliberately slow probe
should produce a trace; routine probes should drop to roughly 5% sampled),
then promote. Tracked in
[co2-calculator#2302](https://github.com/EPFL-ENAC/co2-calculator/issues/2302).

## Per-environment status

| Signal                                                   | Dev                                 | Stage                       | Prod                                                      |
| -------------------------------------------------------- | ----------------------------------- | --------------------------- | --------------------------------------------------------- |
| `route_class` label (collector transform)                | ✅                                  | ✅                          | ✅                                                        |
| Grafana: Latency percentile, split by `route_class`      | ✅                                  | ✅                          | ✅                                                        |
| Grafana: probe / DB pool panels                          | ✅                                  | ✅                          | ✅                                                        |
| `LatencyP50/95/99High` scoped to `route_class="api"`     | ✅                                  | ✅                          | ✅                                                        |
| `BackendMetricsAbsent` (deadman's switch)                | ✅                                  | ✅                          | ✅                                                        |
| `HighErrorRate` -- global (not per-pod) 5xx ratio        | ✅ 2%                               | ✅ 2%                       | ✅ 1% (retuned from data)                                 |
| `ErrorRateSustainedElevated` -- 6h window, severity:info | ✅ 0.3%                             | ✅ 0.3%                     | ✅ 0.3%                                                   |
| `UploadLatencySLOBreach` / `JobLatencySLOBreach`         | ✅ (thresholds from 4wk stage data) | ✅                          | 🟡 interim -- stage-derived thresholds, see below (#2301) |
| Probe trace sampling -- latency-aware, not blanket drop  | ✅                                  | ⬜ not yet promoted (#2302) | ⬜ not yet promoted (#2302)                               |

Prod's `route_class` transform only shipped recently. `UploadLatencySLOBreach`/
`JobLatencySLOBreach` are live there now, but running on **stage's**
4-week-derived thresholds (5s@2%, 10s@5%) as an explicit interim value --
prod has no traffic history of its own yet to derive a number from, and
1402's own precedent is "pull real numbers, don't guess." Zero coverage for
the weeks it takes to accumulate that data seemed worse than a
clearly-labeled approximation; both alerts say "interim" in their summary
text. Retune from real prod `route_class="upload"`/`"job"` history once
available -- tracked in
[co2-calculator#2301](https://github.com/EPFL-ENAC/co2-calculator/issues/2301).

**`HighErrorRate` was retuned from real data, not carried over.** Pulled
4-week 5xx/total on 2026-08-24: dev 0.081%, stage 0.0085%, prod 0.0012% (1
in ~83,600 requests) -- all three environments are healthy, and prod's old
4xx+5xx@50% threshold was an outage detector, not an error-rate SLO. Prod is
now 5xx-only@1% (~800x headroom over its own baseline); dev/stage keep their
existing 5xx-only@2%. All three also shared the same per-pod bug as the
latency alerts -- `sum by (k8s_pod_name)` on both sides of the ratio fired
on any single replica breaching -- fixed to a global ratio everywhere.

**`ErrorRateSustainedElevated` is new, all three environments.**
`HighErrorRate`'s 5-minute window structurally can't see a persistent
low-grade error rate -- it never looks anomalous in any single slice, and
the traffic floor keeps suppressing it there. This alert evaluates the same
5xx ratio over a 6-hour `increase()` window at a much lower threshold
(0.3%), `for: 30m`. `severity: info`, not `warning` -- alertmanager here is
a single flat email route with no severity-based sub-routing, so this
doesn't page differently, it just doesn't get lost as another `warning`.

## Alert catalog (dev/stage; prod matches except where noted above)

| Alert                          | Fires when                                                                       | Why                                                                                                                                                                                 |
| ------------------------------ | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HaproxyRouteHighLatency`      | avg HAProxy latency > 1s for 5m, per route                                       | Edge-level slowness, independent of app metrics                                                                                                                                     |
| `HaproxyHighErrorRatePerRoute` | HAProxy non-2xx rate > 5% for 5m, per route                                      | Edge-level errors (includes upstream-down cases the app never sees)                                                                                                                 |
| `LatencyP50/95/99High`         | app P50/95/99 (route_class=api) over threshold for 5m                            | Normal-API latency only -- streams/uploads/jobs excluded so they can't skew it                                                                                                      |
| `HighErrorRate`                | global 5xx rate > threshold for 5m (2% dev/stage, 1% prod), with a traffic floor | Fast incident signal; 4xx excluded (client errors, not backend health); per-pod grouping fixed so one hot replica can't trip it alone                                               |
| `ErrorRateSustainedElevated`   | global 5xx rate > 0.3% over a rolling 6h window, for 30m                         | Slow-burn companion to `HighErrorRate` -- catches a persistent low-grade error rate the 5-minute window and its traffic floor structurally can't see; `severity:info`, doesn't page |
| `BackendMetricsAbsent`         | no `http_server_duration_milliseconds_count` for 10m                             | Deadman's switch -- every alert above depends on this metric existing                                                                                                               |
| `UploadLatencySLOBreach`       | >2% of uploads slower than 5s over 15m                                           | Proportion-of-slow-requests, not a raw quantile -- the 1402 job-class p95/p99 saturated at the histogram's last bucket, making raw quantiles meaningless there                      |
| `JobLatencySLOBreach`          | >5% of job-class requests slower than 10s over 15m                               | Same reasoning; 10s is this histogram's last resolvable bucket                                                                                                                      |

## Known gaps (not yet actioned)

- **Background task failures are invisible.** `workers`-style processing in
  this codebase is in-process FastAPI `BackgroundTasks`, not a separate
  worker fleet. If a task raises after the HTTP response has already been
  sent, the request already recorded `200` — nothing in
  `http_server_duration_milliseconds` reflects the failure. Closing this
  needs a backend-side counter for task outcomes (success/failure), not an
  ops-repo change. Filed as a follow-up, not yet built.
- **No span-status-based alerting.** OTel span status (`status_code=ERROR`,
  set when an exception propagates through instrumented code regardless of
  the HTTP response code) only reaches Tempo/`enac-it-otel` via traces — no
  `spanmetricsconnector` is configured in any overlay to turn that into a
  Prometheus metric. `http_status_code` is therefore the only error
  dimension Prometheus alerting can see. Adding span-status alerting would
  mean adding that connector — a new pipeline component, not a config tweak.
- **Frontend errors aren't in this pipeline at all.** They go to GlitchTip
  (see the `frontend-observability` extraction), a separate system with its
  own alerting surface, not OTel/Prometheus/Grafana.
