---
status: delivered
issue: 2696
last_updated: 2026-09-09
title: "Worker hands running jobs back on SIGTERM; how it scales"
summary: "A worker rollout killed the running job at the default 30 s grace and left its row RUNNING under a dead pod until the stale sweep 5 min later. The lifespan now cancels in-flight jobs first; each stops its handler, rolls back and releases its row (NOT_STARTED, unlocked, attempts kept) so the next poller tick re-dispatches it. The worker Deployment gets a 60 s grace period. Replica count per environment stays gated on the DB budget; automatic scaling would key on the NOT_STARTED backlog, not CPU, and is capped by DB slots per worker."
---

# Worker hands running jobs back on SIGTERM (#2696)

## Symptom

Every worker rollout (several a day on dev) stops job processing for up to
`STALE_JOB_TIMEOUT_MINUTES` (5 min). The old pod gets SIGTERM, uvicorn
runs the lifespan teardown, the loops are cancelled and the pool is
disposed, but the `run_job` tasks spawned through `fire_and_forget` were
never cancelled: they die with the process, and the row keeps
`state = RUNNING, locked_by = <dead pod>` until
`sweep_stuck_running_jobs` on the new pod finds it stale.

## Shipped

1. **`DataIngestionRepository.release_job(job_id, pod_id)`**: the CAS
   guard of `finish_job` (`locked_by = pod AND state = RUNNING`), the
   target of the stale sweep's recoverable bucket (NOT_STARTED, unlocked,
   `attempts` preserved so `claim_job`'s retry cap still counts the run).
2. **`run_job` catches `CancelledError` around the handler**: cancels the
   handler task, rolls back both sessions, releases the row, logs "handed
   back to the queue" or "no longer ours", re-raises. Test:
   `tests/unit/tasks/test_runner_handback.py`.
3. **`cancel_background_tasks()`** in `_background.py`: cancels every
   in-flight task and waits up to `JOB_HANDBACK_SECONDS` (20 s) for the
   hand-backs; from then on a cancelled task logs at INFO, since at
   shutdown that is the expected outcome. Test in `test_background.py`.
4. **Lifespan order**: safety poller cancelled first (nothing dispatches
   anymore), then the drain, then the other loops, then
   `engine.dispose()`. The drain has to run while the heartbeat still owns
   the lock and the pool is open. Test in `test_lifespan_shutdown.py`.
5. **Helm**: `worker.terminationGracePeriodSeconds: 60` (was the
   Kubernetes default 30), rendered on the worker Deployment. 20 s of
   hand-back plus `dispose()` fits with a stalled DB; no `preStop`, since
   nothing routes HTTP to the worker.

The same path covers the backend pods with `DISPATCH_JOBS_INLINE` on.

## Replicas per environment

Multi-pod job processing already exists: `claim_job` is an atomic
compare-and-set on `locked_by`, the heartbeat detects preemption, the
sweep recovers dead owners. Going to two workers is `worker.replicaCount`
in the environment overlay, and the Deployment strategy switches from
surge to rolling on its own.

What gates it is the [connection budget](../database/02-connection-budget.md):
a worker costs `DB_POOL_SIZE` at rest and `3 × MAX_CONCURRENT_JOBS` under
load. On dev (bouncer pool 35) a second worker at 2+7 does not fit. On
prod (90 usable) two workers at 5+15 give steady 3 × 15 + 2 × 20 = 85,
which fits without a rollout surge and not with one, so prod goes to two
workers only after DBaaS raises the bouncer pool or `max_connections`, or
with the worker at 5+10.

## Automatic scaling, if it is ever needed

**Horizontal.** The signal is the backlog, not CPU: a worker waiting on
the bouncer or on S3 is idle by every CPU metric while jobs pile up.
`count(*) FROM data_ingestion_jobs WHERE state = 'NOT_STARTED' AND
job_type IS NOT NULL` is one gauge on the existing 30 s heartbeat; KEDA's
Prometheus scaler (or an HPA on a custom metric through the Prometheus
adapter) scales on it with `minReplicas` 1 and `maxReplicas` set by the
budget: `(budget − backends × backend ceiling) / worker ceiling`. Scale-down
is safe because the hand-back above makes a terminating worker return
its job within 20 s. A cooldown of a few minutes avoids flapping on a
single CSV upload, which creates a burst of NOT_STARTED rows that one
worker drains in seconds.

**Vertical.** The worker is I/O-bound (DB, S3); its CPU request of 2 is
generous already. Memory is the only axis: a 144k-row CSV ingest holds
the parsed rows in memory, and the 1 Gi limit is what an OOMKill would hit
first. A VPA in recommendation mode on memory would tell whether the
limit is right; automatic vertical scaling restarts the pod to apply,
which is a rollout, so it depends on this issue's hand-back as well.

Neither is worth building before the DB budget grows: with 35 slots on
dev a second worker cannot even start, and on prod the ceiling rule
leaves room for exactly one more. The manual `replicaCount` per
environment, with the budget arithmetic in the overlay comment, is the
whole scaling story until then.

## Rejected

- **Waiting for the running job to finish before exiting**: job 59 ran
  70 min; no grace period covers that, and a rollout stuck behind one job
  is worse than a re-dispatch.
- **Longer `STALE_JOB_TIMEOUT_MINUTES` or a shorter one**: the sweep is
  crash recovery; the graceful path should not depend on it at all.
- **HPA on CPU**: scales on the wrong signal, see above.

## Verification

- Unit: `test_runner_handback.py`, `test_background.py`,
  `test_lifespan_shutdown.py`, runner suites green.
- `helm template` renders `terminationGracePeriodSeconds: 60` on the
  worker Deployment; `helm lint` clean.
- Next dev rollout: the old worker logs "handed back to the queue" and
  the new one logs "Poller: dispatching job N" within
  `POLLER_INTERVAL_SECONDS`, no 5 min gap in `data_ingestion_jobs`.
