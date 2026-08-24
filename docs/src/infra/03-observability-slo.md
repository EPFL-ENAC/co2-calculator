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

## Per-environment status

| Signal                                               | Dev                                 | Stage | Prod                                        |
| ---------------------------------------------------- | ----------------------------------- | ----- | ------------------------------------------- |
| `route_class` label (collector transform)            | ✅                                  | ✅    | ✅                                          |
| Grafana: Latency percentile, split by `route_class`  | ✅                                  | ✅    | ✅                                          |
| Grafana: probe / DB pool panels                      | ✅                                  | ✅    | ✅                                          |
| `LatencyP50/95/99High` scoped to `route_class="api"` | ✅                                  | ✅    | ✅                                          |
| `BackendMetricsAbsent` (deadman's switch)            | ✅                                  | ✅    | ✅                                          |
| `HighErrorRate` — 5xx only, 2% floor + traffic floor | ✅                                  | ✅    | ⬜ still 4xx+5xx, 50% threshold (pre-#1402) |
| `UploadLatencySLOBreach` / `JobLatencySLOBreach`     | ✅ (thresholds from 4wk stage data) | ✅    | ⬜ blocked — see below                      |

Prod's `route_class` transform only just shipped. The SLO-breach alerts need
real `route_class="upload"`/`"job"` traffic history to set a threshold from
— the same rule this repo already applied once (1402's own thresholds came
from 4 weeks of stage data, not a guess). Copying stage's numbers over
verbatim would silently assume prod's traffic shape matches stage's, which
we have no evidence for. Once the transform has run in prod for a few weeks,
pull `route_class="upload"`/`"job"` history and set real thresholds, the
same way 1402 did for stage.

Tightening prod's `HighErrorRate` (4xx+5xx@50% → 5xx-only@2%, matching
dev/stage) is a real sensitivity increase on prod paging, not a scope fix —
it needs a deliberate decision, not a silent carry-over from a dashboard
parity pass.

## Alert catalog (dev/stage; prod matches except where noted above)

| Alert                          | Fires when                                            | Why                                                                                                                                                           |
| ------------------------------ | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HaproxyRouteHighLatency`      | avg HAProxy latency > 1s for 5m, per route            | Edge-level slowness, independent of app metrics                                                                                                               |
| `HaproxyHighErrorRatePerRoute` | HAProxy non-2xx rate > 5% for 5m, per route           | Edge-level errors (includes upstream-down cases the app never sees)                                                                                           |
| `LatencyP50/95/99High`         | app P50/95/99 (route_class=api) over threshold for 5m | Normal-API latency only — streams/uploads/jobs excluded so they can't skew it                                                                                 |
| `HighErrorRate`                | 5xx rate > 2% for 5m, with a traffic floor            | App-level failures; 4xx excluded (client errors, not backend health)                                                                                          |
| `BackendMetricsAbsent`         | no `http_server_duration_milliseconds_count` for 10m  | Deadman's switch — every alert above depends on this metric existing                                                                                          |
| `UploadLatencySLOBreach`       | >2% of uploads slower than 5s over 15m                | Proportion-of-slow-requests, not a raw quantile — the 1402 job-class p95/p99 saturated at the histogram's last bucket, making raw quantiles meaningless there |
| `JobLatencySLOBreach`          | >5% of job-class requests slower than 10s over 15m    | Same reasoning; 10s is this histogram's last resolvable bucket                                                                                                |

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
