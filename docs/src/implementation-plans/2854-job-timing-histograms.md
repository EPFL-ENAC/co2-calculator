---
status: delivered
issue: 2854
last_updated: 2026-09-18
summary: "Job queue wait and duration were columns nobody queried; two OTel histograms per job_type put p95s in Grafana so pod count and MAX_CONCURRENT_JOBS get set from a week of real use instead of a hand-run SQL."
---

# Job queue-wait and duration histograms

Companion to the connection-budget sizing formula
([2854 measurement](./../database/02-connection-budget.md)). The formula
takes `MAX_CONCURRENT_JOBS` and the pod counts as inputs; this is what
tells whether they are right.

## What shipped

- `app/tasks/_job_timings.py`: `job.queue_wait_seconds` (`created_at →
started_at`, label `job_type`) recorded right after the runner's
  post-claim re-fetch, and `job.duration_seconds` (claim to FINISHED,
  labels `job_type`, `result`) recorded next to `finish_job`. Explicit
  buckets 1 s to 1 h; the OTel defaults stop at 10 s and a csv_ingest
  regularly runs minutes.
- Same export path as the DB counters, nothing to configure in the
  collector.
- Grafana "specific graphs", one panel per environment: p95 by job type
  for both series (openshift-app-config, next to the DB failure counters).

## Reading rule

Queue wait rising while worker CPU is saturated: add a worker or CPU.
Rising while CPU is idle: raise `MAX_CONCURRENT_JOBS`. Flat: the pod
count is right, only overflow is worth touching.

## Tests

`tests/unit/tasks/test_job_timings.py`: value and labels of both
instruments, naive UTC stamps, missing stamps record nothing, bucket
boundaries reach minutes.
