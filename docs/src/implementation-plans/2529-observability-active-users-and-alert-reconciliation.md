---
status: in-progress
issue: 2529
title: "Concurrent-users gauge + reconcile job-latency alerting with measured load"
last_updated: 2026-08-30
summary: "Item A: a `co2_active_users_5m` observable gauge plus a capacity-tier panel — unimplemented in both repos, unchanged. Item B was written to reconcile `JobLatencySLOBreach`; that alert was deleted in every environment by openshift-app-config #38 on 2026-09-07 ('no alerting on job-class routes at all'), so it is rewritten to keep only what is still true: why a request-duration histogram whose last bucket is 10 s could never have measured a 42 s job, one live classification defect that routes plan prefill into the tightly-alerted `api` class, and a dev-only route_class split that stage and prod never received."
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

| Metric                   | Where                                     | Shape                                    |
| ------------------------ | ----------------------------------------- | ---------------------------------------- |
| `db.pool.connections`    | `backend/app/db.py:102`                   | observable gauge + callback              |
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
a _user_ gauge.

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
every active user appears in _every_ worker's map and the sum inflates by
roughly the worker count. This does not fail silently — it shows up as N
series sharing one `k8s_pod_name`. The panel legend is
`{{k8s_pod_name}}` for exactly that reason, and the panel description
must say so.

The `worker` deployment (`OTEL_SERVICE_NAME: worker`) runs the same image
but serves no user traffic, so it reports a constant 0 — a no-op under
both `sum()` and `max()`, so the queries below deliberately do **not**
filter it out. Filtering on `service_name="backend"` would be the
obvious move, but no existing query in the ops repo uses that label
(every one keys on `namespace` + `k8s_pod_name`), and a label that
doesn't survive to Prometheus renders the panel blank with no error —
the same silent-no-op bug class #1402 caught three times (`http.route`
in the `filter` processor, `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`, the
`tail_sampling` `/health` match). If a filter is wanted later, confirm
the label exists first (query in Steps).

### Known bias: state it on the panel

`sum()` across pods counts a user once per pod that served them within
the window. With 2–3 backend pods and no session affinity, a browsing
user is likely to hit more than one. **The number is an upper bound.** It
is still the right signal — the tiers below are about _when to act_, and
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

| refId | Query (`$ns` = the env's namespace)         | Legend                       |
| ----- | ------------------------------------------- | ---------------------------- |
| A     | `sum(co2_active_users_5m{namespace="$ns"})` | `active users (upper bound)` |
| B     | `max(co2_active_users_5m{namespace="$ns"})` | `active users (lower bound)` |
| C     | `co2_active_users_5m{namespace="$ns"}`      | `{{k8s_pod_name}}`           |

refId C is a **bare selector, not `sum(...) by (k8s_pod_name)`** — that
is the point. Summing by pod name would collapse per-worker series back
into one line and hide exactly the `WORKERS > 1` inflation described
above, while refId A silently doubled. Unaggregated, N workers render as
N lines sharing a pod name, which is visible.

Threshold steps wired to the capacity tiers in #2529 §2, so the panel
answers "do I need to do something" without a lookup:

| Value | Colour | What it means / what to do                                                                                                                                                                                                                                                                                    |
| ----: | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| < 100 | green  | Within today's 2 pods × 1 CPU / 512 Mi. No action.                                                                                                                                                                                                                                                            |
|   100 | yellow | At the tested-OK ceiling. Raise the backend memory limit to 768 Mi (~380 MB/worker observed under load).                                                                                                                                                                                                      |
|   200 | orange | **Add a third pod**, and check the merged report-stats p95 on the latency panel — that endpoint hit 1.3 s at 200 users on the dev DB. Connections, not CPU, are the binding constraint: `replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` must stay under the DB's `max_connections`. Blocked on #2527 items 4–5. |
|   600 | red    | Not supported today. Needs HPA + pgbouncer (#2527 items 1–5).                                                                                                                                                                                                                                                 |

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

## Item B — job-class alerting, after it was removed

> **Rewritten 2026-09-10, before this plan was merged.** This item was
> written to reconcile `JobLatencySLOBreach` with measured reality.
> **That alert no longer exists.** openshift-app-config **#38**
> (2026-09-07) removed job-class latency alerting in every environment —
> dev's `JobPollLatencySLOBreach`, `JobTriggerLatencySLOBreach` and
> `JobRouteClassAbsent`, and stage's and prod's `JobLatencySLOBreach` —
> after `JobRouteClassAbsent` fired on dev following a quiet weekend when
> nobody had opened the sync UI for three days. The decision recorded
> there is categorical: _"no alerting on job-class routes at all."_
>
> So the reconciliation this item proposed is moot, and re-proposing it
> would relitigate a decision already taken. What follows keeps only the
> analysis that is still true: why those alerts were unfixable rather
> than mis-tuned, and the two live defects the removal did **not**
> address.

### Why the issue's premise was wrong to begin with

#2529 §3 reads: "`JobLatencySLOBreach` fires on a 10 s bucket, but
measured plan prefill is 42 s median at 40 users and uploads reach
184 s." Those two numbers could never have moved that alert, because the
alert never saw them.

It was a proportion over
`http_server_duration_milliseconds{route_class="job"}` — the duration of
**individual HTTP requests**. The 42 s and 184 s figures are locust
`FLOW` metrics: client-side wall time across a whole multi-request flow.
`PlanUser.plan_lifecycle` (`backend/tests/performance/locustfile.py:393`)
is `POST` → `PATCH` → ~21 poll `GET`s at `PERF_POLL_INTERVAL=2` →
3 reads → `DELETE`, and `fire_flow_metric` records the wall time of all
of it. Every constituent request is fast; the flow is slow because it
waits. `CsvUploadUser` is the same shape.

Those numbers are also quantized to the 2 s poll interval and are upper
bounds — the job finished somewhere in the preceding 2 s. Any future SLO
built from them must not claim finer precision than ±2 s.

### Why the removed alerts could not have been fixed, only removed

[1402-trim-down-alerting.md](1402-trim-down-alerting.md) recorded, from
4 weeks of stage traffic: `route_class="job"` p50 60.8 ms, **p95 and p99
both saturated at 10000 ms**.

`histogram_quantile` returns the highest finite bucket boundary when the
quantile lands in the `+Inf` bucket. So p95 = 10000 means **more than 5%
of job-class requests already exceeded 10 s in normal stage traffic** —
which was verbatim the alert's own firing condition (`> 0.05` over
`le="10000"`). It was not mis-thresholded by some margin; it was set _at_
its observed baseline, and stayed quiet only because `for: 15m` combined
with the `> 0.02 req/s` traffic floor meant stage was rarely busy enough
for 15 continuous minutes to clear it.

And **10 s could not be raised.** `http_server_duration_milliseconds`
uses the OTel SDK's default explicit bucket boundaries, whose last finite
bucket is `10000`. There is no `le="60000"` to query. A request-duration
histogram simply cannot express "this job took 42 s".

That is the real reason #38's removal was right rather than merely
convenient: the instrument could not measure the thing, at any threshold.

### 🔴 Still live: the classification bug

**The removal did not touch this, and it is the one defect here that can
still page someone at 3am for the wrong reason.**

Derived from the collector's metrics `transform` block
(`overlays/{env}/kustomization.yaml`, the `route_class` rules), which
matches on `http.target` tails: `/v1/project-plans/*` matches **none** of
the `job` patterns (`dispatch|jobs|workers|active-pipelines|
recalculation-status|pipelines|health/stale-stats|admin/recompute-stats`).
So it falls through to the final `set(... "api")` rule, and the prefill
trigger `PATCH` plus all ~21 prefill poll `GET`s per plan lifecycle land
in `route_class="api"` — the class with the **tight**
`LatencyP50/95/99High` thresholds, which are all still active.

So if plan prefill gets slow, it pages `LatencyP95High`. That was true
before #38 and is still true after it; removing the job-class rules
removed the alert that _would not_ have fired and left the one that
will. This is the same failure mode #1402 caught twice already
(`/healthz` and `/dispatch` landing in `api`; `GET /v1/units` landing in
`job`).

Fix: add the project-plans prefill routes to the right job class.
**Confirm the live label shape first** — #1402 explicitly records that
where the `/v1/<router-prefix>` collapse happens is _still unconfirmed_,
so the tail these routes actually produce must be observed, not
predicted:

```promql
count by (route_class, http_target, http_method) (
  http_server_duration_milliseconds_count{namespace="$ns"}
)
```

### Still open: the split shipped to dev only

openshift-app-config **#30** split `route_class="job"` into `job_poll` /
`job_trigger` in the collector transform, tagged `co2-calculator#2529`.
#38 explicitly **kept** that transform — only the `PrometheusRule`
entries went — because "dashboards and TraceQL filters still use job /
job_poll / job_trigger".

But the split only ever landed in the **dev** overlay. Stage and prod
still emit a single `job` class. So the same dashboard panel and the same
TraceQL filter mean different things in different environments, which is
its own quiet trap.

Two coherent options, and this needs a decision rather than drift:
propagate the split to stage and prod, or revert dev to match them. The
split is independently correct and costs nothing at query time, so
propagating is the better default — but it is a call, not a conclusion.

### The real gap, unchanged and now wider

The correct fix for "plan prefill takes 42 s and upload-to-ingested takes
184 s" is **making those jobs faster** —
[#2527](https://github.com/EPFL-ENAC/co2-calculator/issues/2527) items
1–3. Nothing in this plan improves either number.

The metric that should carry those numbers is a job-duration business
metric (`pipeline_duration_seconds` / a `PipelineSlow` alert), an open
step in [1402](1402-trim-down-alerting.md) and tracked as C4 in
[2049-optimize-pipeline-performance.md](2049-optimize-pipeline-performance.md).

**That work is out of scope here and stays gated.** It requires hooking
job completion in `backend/app/tasks/runner.py` / `_chain.py` /
`_pipeline_reconciler.py` — recalculation internals, which the
[guardrails](../contributing/guardrails.md) put behind a written plan
reviewed by both maintainers, however additive the metric itself looks.

What #38 changed is the urgency: there is now **no alert anywhere that
can see a slow job**, by deliberate choice. That is defensible while the
only available instrument was a saturated request-duration histogram. It
stops being defensible once 2049-C4 exists, and it is the strongest
argument for unblocking it.

### What this item deliberately does not propose

**Re-adding job-class latency alerts.** #38 removed them on a considered
decision after a real false page. Nothing measured since contradicts it,
and the analysis above explains why no threshold would have helped. If
job slowness should page, it pages off a job-duration metric — not off a
histogram whose last bucket is 10 s.

---

## Steps

### Item A

- [ ] `backend/app/core/active_users.py` — locked map, `touch()`, pruning
      observable-gauge callback, unit `{user}`.
- [ ] One call in `resolve_user_by_jwt_payload`
      (`backend/app/core/security.py`), beside `tag_span_with_user`.
- [ ] Unit test in `backend/tests/unit/core/test_active_users.py`.
- [ ] Deploy to dev; confirm `co2_active_users_5m` appears with one series
      per backend pod and a plausible value. Same trip, record which labels
      actually survive — group by `service_name` and `k8s_pod_name` and see
      what comes back — so the panel is written against observed labels,
      not assumed ones.
- [ ] **Ops repo PR** (separate): the "Active users (5m) — capacity tier"
      panel in all three overlays, with the threshold steps and the
      description above; bump the dashboard `version`.

### Item B

Everything about re-thresholding is gone — see the rewrite note. What is
left is the classification defect and one decision.

- [ ] Run `count by (route_class, http_target, http_method)` and record
      the real tail for `/v1/project-plans/*`. This is the only gating
      measurement left: the fix below must be written against observed
      labels, not predicted ones.
- [ ] **Ops repo PR**: add the project-plans prefill routes to the right
      job class, so they stop landing in `route_class="api"` under the
      tight `LatencyP50/95/99High` thresholds that are still active.
- [ ] **Decide**: propagate the dev-only `job_poll` / `job_trigger`
      transform to stage and prod, or revert dev to match them. Today the
      same dashboard panel and TraceQL filter mean different things per
      environment.
- [ ] Re-verify classification during a real import, per #1402's open
      step — a wrong regex mis-classifies silently and every threshold
      downstream becomes meaningless without failing.
- [ ] **Do not** re-add job-class latency rules (openshift-app-config
      #38). If job slowness should page, it pages off 2049-C4's
      job-duration metric.

## Open questions for the maintainer

1. **Is 2049-C4 (`pipeline_duration_seconds`) unblocked by this?** It is
   the only way to alert on the 42 s / 184 s numbers at all, and it needs
   two-maintainer review because it touches pipeline internals. Item B
   can ship without it, but it will keep measuring the wrong thing.
2. **`sum()` or `max()` as the panel's headline stat?** Proposed `sum()`
   (upper bound, errs toward acting early), with `max()` charted
   alongside. Say if you would rather the headline read low.
3. **Does the `job_poll` / `job_trigger` split propagate to stage and
   prod, or does dev revert to match them?** #30 shipped it to dev only
   and #38 kept the transform while dropping the rules, so the classes
   exist in one environment and not the others — the same panel and the
   same TraceQL filter mean different things depending where you look.
   Propagating is the better default (independently correct, free at
   query time), but with no job-class alerts left the only consumers are
   dashboards and traces, so reverting is defensible too.
