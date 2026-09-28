---
status: abandoned
issue: 2529
title: "Concurrent-users gauge + job-latency alerting after #38"
last_updated: 2026-09-28
summary: "Abandoned 2026-09-28. Item A, a `co2_active_users_5m` gauge, is dropped: the manual scaling tiers it served are handled by the HPA and pgbouncer, people online is known by other means, and its reading depended on router affinity. Item B needs no change here: openshift-app-config#38 removed the job-class alerts, and plan prefill's requests belong in `api`."
---

# Concurrent-users gauge + job-latency alerting after #38

The two observability items of
[#2529 §3](https://github.com/EPFL-ENAC/co2-calculator/issues/2529).
Both are closed without code in this repo.

## Item A — active-users gauge: abandoned

A per-pod count of distinct authenticated users in the last 5 minutes,
built in #2957 and removed before merge. It was meant to drive manual
capacity tiers counted in users (raise memory, add a pod, need HPA and
pgbouncer). The HPA (3–6 backend pods) and pgbouncer now do that, and
capacity is measured in CPU per request. People online is known by other
means. Its reading also depended on the router's sticky cookie: `sum()`
over pods is exact with it, `max()` without it.

## Item B — job-latency alerting: no change

openshift-app-config#38 (2026-09-07) removed every job-class latency
alert. What remained:

- The 42 s prefill and 184 s upload figures are locust flow times, a
  trigger then polls. Each request is fast, and a request-duration
  histogram whose last bucket is 10 s cannot measure a job
  ([1402](../1402-trim-down-alerting.md)).
- Plan prefill's routes enqueue a job or read one job row; the prefill
  runs outside the request. They belong in `route_class="api"`, so
  openshift-app-config#74 is closed.
- Dev's `job_poll` / `job_trigger` split has no consumer since #38. It is
  removed in the ops repo so dev matches stage and prod.
- Job durations are measured per `job_type` by #2854. Upload-to-ingested
  is a pipeline and needs 2049-C4, which stays behind two-maintainer
  review.
