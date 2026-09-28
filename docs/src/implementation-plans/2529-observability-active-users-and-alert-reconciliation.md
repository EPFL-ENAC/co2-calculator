---
status: in-progress
issue: 2529
title: "Concurrent-users gauge + job-latency alerting after #38"
last_updated: 2026-09-28
summary: "Item A: `co2_active_users_5m`, distinct users per backend pod, is in the backend; the dev check and a two-line panel remain. Item B needs no change: openshift-app-config#38 removed the job-class alerts, and plan prefill's requests are fast enqueue/poll calls that belong in `api`, so openshift-app-config#74 is not needed."
---

# Concurrent-users gauge + job-latency alerting after #38

The two observability items of
[#2529 §3](https://github.com/EPFL-ENAC/co2-calculator/issues/2529).
Dashboards and alert rules live in
[`openshift-app-config`](https://github.com/EPFL-ENAC/openshift-app-config)
under `epfl/co2-calculator/overlays/{dev,stage,prod}/`.

## Item A — `co2_active_users_5m`

`http.server.active_requests` counts requests, not people. This gauge
counts the distinct authenticated users each backend pod served in the
last 5 minutes.

### Shipped

- `backend/app/core/active_users.py`: a `User.id → monotonic last-seen`
  dict under a `threading.Lock`, since the gauge callback runs on the
  metric-reader thread. The callback prunes entries past the window and
  yields one observation with no attributes: one series per pod, and the
  user id never leaves the process. Unit `{user}` gives the Prometheus
  name `co2_active_users_5m`. Registered at import time like
  `db.pool.connections`, so it is a no-op without a MeterProvider.
- One `active_users.touch(user.id)` in `resolve_user_by_jwt_payload`,
  next to `tag_span_with_user`. Not a middleware: it would re-verify the
  JWT and count 401s. Unauthenticated traffic is not counted.
- Tests: `tests/unit/core/test_active_users.py` (window edge, pruning, no
  attributes, `touch(None)` raises), and
  `test_resolved_user_is_counted_as_active`, which fails if the `touch()`
  call is removed.

### Reading it

Each pod counts only the users it served, so the total depends on how the
router spreads one user's requests:

- **Sticky cookie on** (the OpenShift router default; stage and prod
  today): a user stays on one pod, and `sum()` is the true count.
- **Sticky cookie off** (dev since 2026-09-25: `disable_cookies` +
  `leastconn` on the backend route, for #2295): a user's requests spread
  over every pod. `max()` is about the true count, and `sum()` is roughly
  users × pods, so it grows when the HPA scales out.

Whatever the setting, `max() ≤ true count ≤ sum()`. The setting lives in
each environment's overlay in the ops repo, so the dev → stage → main
promotion does not carry it. The dev overlay calls it "dev first": when
stage and prod follow, `max()` becomes the number to read everywhere.

It also undercounts in two cases. An SSE stream authenticates once, when
it opens, so a user whose only traffic is one long stream drops out after
5 minutes. And every environment runs `WORKERS=1`; with more uvicorn
workers per pod, each worker would count separately.

### Panel (ops repo)

"Active users (5m)" in `overlays/{env}/grafana/cm-specific-dashboard.yaml`,
next to "DB Pool Usage" and in the same JSON shape:

| Query                                       | Legend                     |
| ------------------------------------------- | -------------------------- |
| `max(co2_active_users_5m{namespace="$ns"})` | `max (exact, no cookie)`   |
| `sum(co2_active_users_5m{namespace="$ns"})` | `sum (exact, with cookie)` |

The worker deployment reports a constant 0, which changes neither query.
No thresholds: the capacity tiers in #2529 §2 predate the HPA and
pgbouncer. No alert: many users is not a fault.

## Item B — job-latency alerting after #38

openshift-app-config#38 (2026-09-07) removed every job-class latency
alert: "no alerting on job-class routes at all". What is left:

- **The premise was wrong.** The 42 s prefill and 184 s upload figures
  are locust flow times: a trigger, then polls every 2 s. Each request in
  the flow is fast, and a request-duration histogram whose last bucket is
  10 s cannot measure a job at any threshold
  ([1402](1402-trim-down-alerting.md)).
- **Plan prefill stays in `route_class="api"`.** Its routes enqueue a job
  or read one job row; the prefill runs outside the request
  (`_enqueue_prefill` → `run_job`). They are ordinary API calls, so the
  `api` latency alerts are the right ones, and openshift-app-config#74 is
  not needed.
- **Dev's `job_poll` / `job_trigger` split goes.** No alert reads it
  since #38, so dev returns to the single `job` class of stage and prod
  instead of both getting the split. No drift, fewer lines.
- **Job durations:** #2854's `job_duration_seconds` and
  `job_queue_wait_seconds`, per `job_type`, cover single jobs such as
  prefill. Upload-to-ingested is a pipeline and needs 2049-C4's
  `pipeline_duration_seconds`, which touches pipeline internals and stays
  behind two-maintainer review.
- Do not re-add job-class latency rules. If job slowness should page, it
  pages off a job-duration metric.

## Steps

### Item A

- [x] `active_users.py`: locked map, `touch()`, pruning callback.
- [x] `touch()` in `resolve_user_by_jwt_payload`.
- [x] Tests.
- [ ] Deploy to dev. Check one series per backend pod and a plausible
      value with `count by (service_name, k8s_pod_name) (co2_active_users_5m)`.
- [ ] Ops repo PR: the two-line panel in all three overlays, written
      against the labels that check returned; bump the dashboard `version`.

### Item B

- [ ] Close openshift-app-config#74.
- [ ] Ops repo PR: remove dev's `job_poll` / `job_trigger` split.
