---
status: in-progress
issue: 2529
title: "Concurrent-users gauge + reconcile job-latency alerting with measured load"
last_updated: 2026-08-30
summary: "Add a co2_active_users_5m gauge wired to the capacity tiers from #2529 §2, and reconcile JobLatencySLOBreach with the #2295 load-test numbers — including the finding that the 42 s / 184 s figures are client-side flow times the alert's histogram never sees."
---

# Concurrent-users gauge + reconcile job-latency alerting with measured load

Covers the two observability items in [#2529 §3](https://github.com/EPFL-ENAC/co2-calculator/issues/2529).
Item A is new backend code plus a dashboard panel; Item B is entirely a
threshold/design decision in the ops repo, plus one correction to the
premise it was filed on.

Dashboards and alert rules live in
[`openshift-app-config`](https://github.com/EPFL-ENAC/openshift-app-config)
under `epfl/co2-calculator/overlays/{dev,stage,prod}/`. Nothing in this
plan edits that repo — the changes are specified here so the ops PR is a
transcription, not a redesign.

---

## Item A — `co2_active_users_5m`

### What exists today

`http.server.active_requests` is already exported by the OTel ASGI
auto-instrumentation (`backend/Dockerfile` runs the app under
`opentelemetry-instrument`). It is a fine load proxy and stays. It is not
a user count: one user pulling a 40-request page and forty users idling
on a rendered page look identical.

Two custom metrics already exist and set the pattern to copy:

| Metric | Where | Shape |
| --- | --- | --- |
| `db.pool.connections` | `backend/app/db.py:102` | observable gauge + callback |
| `event_loop_lag_seconds` | `backend/app/tasks/_event_loop_lag.py:28` | histogram, recorded from a lifespan task |

No `MeterProvider` is constructed in app code — `opentelemetry-instrument`
configures it, and `get_meter(__name__)` is a no-op under plain
`uv run uvicorn` / pytest. So the new gauge needs **no** wiring in
`main.py`, no lifespan task and no `Settings` field. Import-time
registration in the module that owns it, exactly like `db.py`.

### Where the hook goes: not a middleware

The issue proposes a middleware. Recommendation: **don't add one.**

`app/core/security.py:112` already has `tag_span_with_user(user)`, called
from `resolve_user_by_jwt_payload` — the single function every
authenticated request passes through, which has already decoded and
verified the JWT and already loaded the `User`. Recording `last_seen`
there is one call next to an existing observability side effect.

A raw-ASGI middleware (the `RequestOriginMiddleware` shape) would have to
re-decode and re-verify the auth cookie itself — duplicating the trust
boundary in `security.py`, paying a second JWT verification per request,
and counting requests that then 401. Rejected for those reasons, recorded
here so the road not taken is visible.

Consequence to accept: unauthenticated traffic (`/healthz`, `/ready`, the
OAuth callback, 401s) is never counted. That is the correct behaviour for
a *user* gauge.

### Design

```
backend/app/core/active_users.py     # new, ~40 lines
backend/app/core/security.py         # +1 call in resolve_user_by_jwt_payload
backend/tests/unit/core/test_active_users.py   # new
```

- Module-level `dict[int, float]` mapping `User.id → monotonic last-seen`,
  guarded by a `threading.Lock`.
- `touch(user_id)` — called from `resolve_user_by_jwt_payload`, next to
  `tag_span_with_user`.
- Observable-gauge callback prunes entries older than the window, then
  yields `len(map)` as a single `Observation` with **no attributes**.

```python
get_meter(__name__).create_observable_gauge(
    "co2.active_users_5m",
    callbacks=[_active_users_callback],
    unit="{user}",
    description="Distinct authenticated users seen by this pod in the last 5 minutes",
)
```

Four constraints that are load-bearing, not stylistic:

1. **The lock is required.** The gauge callback runs on the SDK's metric-
   reader thread while `touch()` mutates from the event loop. Iterating a
   dict another thread is resizing raises
   `RuntimeError: dictionary changed size during iteration`.
   `read_pool_state` in `db.py` gets away without a lock only because it
   reads scalars off `QueuePool`.
2. **Pruning happens in the callback**, so memory is bounded by
   distinct-users-in-the-window, not distinct-users-since-pod-start. With
   the dev DB now holding 4800 fake users (#2529 §5) an unpruned map is a
   real leak, not a theoretical one.
3. **`user_id` never becomes a metric attribute.** It stays in process
   memory; the exported series carries only the resource attributes the
   collector adds (`namespace`, `k8s_pod_name`, `service_name`). This is
   the entire cardinality argument, and it is also the privacy stance
   `tag_span_with_user`'s docstring already settled — our own `User.id`,
   never the sciper, and here not even that leaves the process.
4. **Unit `{user}` gives the exact Prometheus name.** The exporter
   appends a unit suffix for real units (`http.server.duration` + `ms` →
   `http_server_duration_milliseconds`) but not for annotation units
   (`db.pool.connections` + `{connection}` → `db_pool_connections`). So
   `co2.active_users_5m` + `{user}` → `co2_active_users_5m`.

Window: 5 minutes, a module constant. Not a `Settings` field — nothing
tunes it per environment, and the value is baked into the metric name.

### One-series-per-pod: verified, and how it would break

Checked: no overlay in `openshift-app-config` sets `WORKERS`, so the
`backend/Dockerfile` default `WORKERS=1` applies in dev, stage and prod —
one uvicorn process per pod, one series per pod, as the issue assumes.

If anyone ever sets `WORKERS > 1`, uvicorn forks and each worker gets its
own heap: the same user's requests round-robin across workers, so nearly
every active user appears in *every* worker's map and the sum inflates by
roughly the worker count. This does not fail silently — it shows up as N
series sharing one `k8s_pod_name`. The panel legend is
`{{k8s_pod_name}}` for exactly that reason, and the panel description
must say so.

The `worker` deployment (`OTEL_SERVICE_NAME: worker`) runs the same image
but serves no user traffic, so it reports a constant 0. Harmless under
`sum()`; scope the per-pod breakdown to `service_name="backend"` to keep
the legend clean.

### Known bias: state it on the panel

`sum()` across pods counts a user once per pod that served them within
the window. With 2–3 backend pods and no session affinity, a browsing
user is likely to hit more than one. **The number is an upper bound.** It
is still the right signal — the tiers below are about *when to act*, and
an over-counting load signal errs toward acting early.

The lower bound is `max()` over pods. Chart both: `sum()` as the headline
stat, `max()` as a second series, and the true value sits between them.
That is one extra query, and it removes the only real objection to the
metric.

### Grafana panel (ops repo — do not edit here)

`overlays/{env}/grafana/cm-specific-dashboard.yaml`, next to the existing
"DB Pool Usage" panel. Copy that panel's JSON shape:
`"type": "timeseries"`, the same `datasource.uid`, `"editorMode": "code"`,
`"range": true`, and bump the dashboard `version`.

Title: **Active users (5m) — capacity tier**

| refId | Query (`$ns` = the env's namespace) | Legend |
| --- | --- | --- |
| A | `sum(co2_active_users_5m{namespace="$ns", service_name="backend"})` | `active users (upper bound)` |
| B | `max(co2_active_users_5m{namespace="$ns", service_name="backend"})` | `active users (lower bound)` |
| C | `sum(co2_active_users_5m{namespace="$ns", service_name="backend"}) by (k8s_pod_name)` | `{{k8s_pod_name}}` |

Threshold steps wired to the capacity tiers in #2529 §2, so the panel
answers "do I need to do something" without a lookup:

| Value | Colour | What it means / what to do |
| ---: | --- | --- |
| < 100 | green | Within today's 2 pods × 1 CPU / 512 Mi. No action. |
| 100 | yellow | At the tested-OK ceiling. Raise the backend memory limit to 768 Mi (~380 MB/worker observed under load). |
| 200 | orange | **Add a third pod**, and check the merged report-stats p95 on the latency panel — that endpoint hit 1.3 s at 200 users on the dev DB. Connections, not CPU, are the binding constraint: `replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` must stay under the DB's `max_connections`. Blocked on #2527 items 4–5. |
| 600 | red | Not supported today. Needs HPA + pgbouncer (#2527 items 1–5). |

Panel description (verbatim, so the bias is never lost):

> Distinct authenticated users seen in the last 5 minutes.
> `sum()` across pods is an **upper bound** — a user served by two pods is
> counted twice; `max()` is the lower bound. Sourced from
> `co2_active_users_5m`, one series per backend pod. Unauthenticated
> traffic (probes, the OAuth callback, 401s) is not counted. Thresholds
> follow the capacity tiers in
> [#2529 §2](https://github.com/EPFL-ENAC/co2-calculator/issues/2529).

**No alert on this panel.** "Many users" is not a fault, and a
user-count alert would fire on a successful launch. It is a capacity
signal for a human reading the dashboard; the faults are already covered
by the latency and error-rate rules.

### Test

One unit test in `backend/tests/unit/core/`, no framework beyond pytest:
touch three ids, assert the callback yields 3; monkeypatch the clock past
the window, touch one, assert it yields 1 and the map has been pruned to
1 entry. That is the whole contract.

---

## Item B — reconcile `JobLatencySLOBreach` with measured reality

### Correction to the premise, first

#2529 §3 reads: "`JobLatencySLOBreach` fires on a 10 s bucket, but
measured plan prefill is 42 s median at 40 users and uploads reach 184 s."
Those two numbers cannot move this alert, because the alert never sees
them.

`JobLatencySLOBreach` is a proportion over
`http_server_duration_milliseconds{route_class="job"}` — the duration of
**individual HTTP requests**. The 42 s and 184 s figures are locust
`FLOW` metrics: client-side wall time across a whole multi-request flow.
`PlanUser.plan_lifecycle` (`backend/tests/performance/locustfile.py:393`)
is `POST` → `PATCH` → ~21 poll `GET`s at `PERF_POLL_INTERVAL=2` →
3 reads → `DELETE`, and `fire_flow_metric` records the wall time of all
of it. Every constituent request is fast; the flow is slow because it
waits. `CsvUploadUser` is the same shape.

Two consequences:

- Reconciling 42 s / 184 s against a request-duration histogram is a
  category error. They belong to a **job-duration** metric that does not
  exist yet (see "The long-term answer" below).
- Those numbers are quantized to the 2 s poll interval and are upper
  bounds — the job finished somewhere in the preceding 2 s. Do not set
  any SLO to finer precision than ±2 s off them.

This does not make the issue's concern wrong. It makes it **more**
urgent, for a different reason.

### The real defect: the threshold was set at its own baseline

[1402-trim-down-alerting.md](1402-trim-down-alerting.md) recorded, from
4 weeks of stage traffic: `route_class="job"` p50 60.8 ms, **p95 and p99
both saturated at 10000 ms**.

`histogram_quantile` returns the highest finite bucket boundary when the
quantile lands in the `+Inf` bucket. So p95 = 10000 means **more than 5%
of job-class requests already exceed 10 s in normal stage traffic** —
which is verbatim the alert's own firing condition (`> 0.05` over
`le="10000"`).

The alert is not mis-thresholded by some margin. It is set *at* its
observed baseline. It has stayed quiet only because of `for: 15m`
combined with the `> 0.02 req/s` traffic floor: stage is rarely busy
enough for 15 continuous minutes to clear the floor. Sustained real load
clears it, and then the alert is a coin flip that resolves to "firing".

**Confirm before changing anything.** This is a hypothesis derived from a
recorded quantile, and #1402's own working rule is "pull real numbers
instead of guessing". Step 1 of the work below is running this in each
env's Grafana:

```promql
# What fraction of job-class requests exceed 10s, over 7 days?
1 - (
  sum(rate(http_server_duration_milliseconds_bucket{namespace="$ns", route_class="job", le="10000"}[7d]))
  /
  sum(rate(http_server_duration_milliseconds_count{namespace="$ns", route_class="job"}[7d]))
)
```

If that is materially below 0.05, the alert is fine as written and Item B
reduces to the classification fix below. If it is at or above 0.05,
proceed.

### The constraint that kills the obvious fix

**10 s cannot be raised to 60 s.** `http_server_duration_milliseconds`
uses the OTel SDK's default explicit bucket boundaries, whose last finite
bucket is `10000`. There is no `le="60000"` to query. The alert's own
annotation already says this ("10s is this histogram's last resolvable
bucket"); it is easy to miss when reading the threshold as a tunable
number.

That leaves three real knobs, and the third is the one that matters:

1. **Move the proportion** (5% → higher). Cheapest, and the weakest: it
   says "more of our requests may be slow" without saying how slow.
2. **Split `route_class="job"`** so the number means something. Collector
   change only, no backend code.
3. **Measure job duration directly**, which is what the 42 s / 184 s
   numbers are actually about. Backend code, and gated — see below.

### A classification bug found while writing this

Derived from the collector's metrics `transform` block
(`overlays/{env}/kustomization.yaml`, the `route_class` rules), which
matches on `http.target` tails:

`/v1/project-plans/*` matches **none** of the `job` patterns
(`dispatch|jobs|workers|active-pipelines|recalculation-status|pipelines|
health/stale-stats|admin/recompute-stats`). So it falls through to the
final `set(... "api")` rule. That means the prefill trigger `PATCH` and
all ~21 prefill poll `GET`s per plan lifecycle land in
`route_class="api"` — the class with the **tight** `LatencyP50/95/99High`
thresholds.

If plan prefill ever gets slow, it will page `LatencyP95High`, not
`JobLatencySLOBreach`. This is the same failure mode #1402 caught twice
already (`/healthz` and `/dispatch` landing in `api`; `GET /v1/units`
landing in `job`).

Fix: add `project-plans` prefill routes to the `job` classification.
**But confirm the live label shape first** — #1402 explicitly records
that where the `/v1/<router-prefix>` collapse happens is *still
unconfirmed*, so the tail these routes actually produce must be observed,
not predicted:

```promql
count by (route_class, http_target, http_method) (
  http_server_duration_milliseconds_count{namespace="$ns"}
)
```

### Proposed job classes and thresholds

The single `job` class mixes two populations with nothing in common: fast
polls that should never be slow, and trigger requests that legitimately
do work. Averaging them is why the current number is uninterpretable.
Split them in the collector transform:

| Class | Routes | Should be | Proposed alert |
| --- | --- | --- | --- |
| `job_poll` | `GET /sync/jobs/*`, `/sync/pipelines/*`, `/workers`, `/active-pipelines*`, `/recalculation-status`, and the `project-plans/*/prefill/*` polls once reclassified | Sub-second. A status read is one indexed row. | > 5% over **1 s** (`le="1000"`), `for: 15m`. A slow poll is a genuine, actionable signal — it is the frontend's progress bar stalling. |
| `job_trigger` | `POST /sync/dispatch`, `POST /sync/units`, `POST /year-configuration/{year}` recalc, the prefill-enqueueing `PATCH` | Enqueue + commit, then return. Slow means the enqueue path itself is doing work it shouldn't. | > 5% over **10 s** — keep the existing threshold; on a trigger it is a real bound, not a saturated one. |
| `upload` | `POST /files` | Unchanged. | `UploadLatencySLOBreach` unchanged (> 2% over 5 s). Confirm against real data — #2529 §1 measured upload-to-ingested at 8 s dev median, but that is again the *flow*, not the POST. |
| `stream` | SSE | Excluded from latency alerting entirely (#1402). | none |

Deliberately **no** raise of a threshold above what the histogram can
resolve, because there is no such threshold to set. If the confirming
query shows `job_poll` genuinely cannot meet 1 s today, the intermediate
target goes in as a time-boxed exception, not as a permanent number —
see below.

### Intermediate targets while #2527 lands

Any threshold that is looser than where it should end up carries its
expiry **in `annotations.description`**, which is the one place the
on-call actually reads. Mirroring how the existing rules already carry
their rationale there:

```yaml
description: >
  TIME-BOXED to 2026-11-30, tracked by #2527 (items 1-3) and #2529.
  Interim threshold: <N>% over <M>s. Target on expiry: 5% over 1s.
  Baseline when set: <value from the 7d query>, measured <date>.
  If this date passes with the threshold unchanged, the raise has
  become a mute -- reopen #2529.
```

Rules, so this cannot rot into a permanent mute:

- Every interim threshold names a **date**, a **target value**, and the
  **measured baseline it was set from**. No bare numbers.
- The interim value is set from the confirming query, not copied between
  environments. #1402 already applied this rule once for stage and is
  currently blocked on prod for exactly this reason.
- A threshold raise ships **together** with the compensating coverage
  below, never alone.

### How not to mute a real signal

Three compensations, all repo precedent rather than invention:

1. **A sustained low-threshold companion**, copying
   `ErrorRateSustainedElevated`: same ratio, evaluated over a rolling 6h
   `increase()` window at the *target* threshold (not the interim one),
   `for: 30m`, `severity: info`. A raised fast alert structurally cannot
   see a persistent low-grade regression; this one can. `info` because
   the alertmanager here is a single flat email route with no
   severity-based sub-routing — it does not page differently, it just
   does not get lost as another `warning`.
2. **Keep `BackendMetricsAbsent`.** Every one of these rules silently
   depends on the metric existing; splitting `route_class` is exactly the
   kind of change that can make a series disappear.
3. **Re-verify classification against real traffic**, with the
   `count by (route_class, http_target, http_method)` query above, run
   *while a real import is running*. This is still an open step in #1402
   for the same reason: a wrong regex silently mis-classifies requests,
   and every threshold downstream becomes meaningless without failing.

### The long-term answer is #2527, not a threshold

To be explicit: the correct fix for "plan prefill takes 42 s and
upload-to-ingested takes 184 s" is **making those jobs faster** —
[#2527](https://github.com/EPFL-ENAC/co2-calculator/issues/2527) items
1–3. Nothing in this plan improves either number. Every threshold change
proposed here is a change to what we *observe*, and each one is time-boxed
against those issues landing.

The metric that should eventually carry the 42 s and 184 s numbers is a
job-duration business metric (`pipeline_duration_seconds` / the
`PipelineSlow` alert), which is an open step in
[1402](1402-trim-down-alerting.md) and tracked as C4 in
[2049-optimize-pipeline-performance.md](2049-optimize-pipeline-performance.md).

**That work is out of scope here and stays gated.** It requires hooking
job completion in `backend/app/tasks/runner.py` / `_chain.py` /
`_pipeline_reconciler.py` — recalculation internals, which the
[guardrails](../contributing/guardrails.md) put behind a written plan
reviewed by both maintainers, however additive the metric itself looks.
This plan does not propose editing those files. It only records that
until that metric exists, **no alert in this system can see how long a
job takes** — which is the actual gap #2529 §3 identified, and the
strongest argument for unblocking 2049-C4.

---

## Steps

### Item A

- [ ] `backend/app/core/active_users.py` — locked map, `touch()`, pruning
      observable-gauge callback, unit `{user}`.
- [ ] One call in `resolve_user_by_jwt_payload`
      (`backend/app/core/security.py`), beside `tag_span_with_user`.
- [ ] Unit test in `backend/tests/unit/core/test_active_users.py`.
- [ ] Deploy to dev; confirm `co2_active_users_5m` appears with one series
      per backend pod and a plausible value.
- [ ] **Ops repo PR** (separate): the "Active users (5m) — capacity tier"
      panel in all three overlays, with the threshold steps and the
      description above; bump the dashboard `version`.

### Item B

- [ ] Run the 7-day `le="10000"` proportion query in dev, stage and prod.
      Record the numbers in this plan. **Everything below is gated on
      this** — if the proportion is comfortably under 5%, close Item B as
      "premise corrected, no change needed" and keep only the
      classification fix.
- [ ] Run `count by (route_class, http_target, http_method)` and record
      the real tail for `/v1/project-plans/*`.
- [ ] **Ops repo PR**: split `route_class="job"` into `job_poll` /
      `job_trigger` in the collector transform; add the project-plans
      prefill routes to the right class.
- [ ] **Ops repo PR**: replace `JobLatencySLOBreach` with the two
      class-specific rules, thresholds from the measured baselines, each
      carrying the time-box annotation.
- [ ] **Ops repo PR**: `JobLatencySustainedElevated` — 6h window, target
      threshold, `severity: info`.
- [ ] Split the "Latency percentile (by route_class)" panel legend to show
      the new classes (it already groups `by (le, route_class)`, so this
      is free once the transform ships).
- [ ] Re-verify classification during a real import, per #1402's open
      step.
- [ ] On the time-box date: either the thresholds tighten to target, or
      #2529 reopens. No third outcome.

## Open questions for the maintainer

1. **Is 2049-C4 (`pipeline_duration_seconds`) unblocked by this?** It is
   the only way to alert on the 42 s / 184 s numbers at all, and it needs
   two-maintainer review because it touches pipeline internals. Item B
   can ship without it, but it will keep measuring the wrong thing.
2. **`sum()` or `max()` as the panel's headline stat?** Proposed `sum()`
   (upper bound, errs toward acting early), with `max()` charted
   alongside. Say if you would rather the headline read low.
3. **One PR or two in the ops repo?** The classification split and the
   threshold change are separable and the split is independently correct;
   shipping the split first would give a week of clean per-class data to
   set thresholds from. Slower, but it is the "pull real numbers" rule
   applied one more time.
