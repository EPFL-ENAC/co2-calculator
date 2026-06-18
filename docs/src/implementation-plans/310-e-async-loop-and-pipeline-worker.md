---
status: proposed
issue: 310-e
last_updated: 2026-06-15
title: "310-e Async-loop hygiene & pipeline worker hardening"
summary: "Improvement backlog from the 2026-06-15 dev incident: a CSV ingestion job ran in-process on the web event loop, starved /healthz past the 2s liveness timeout, and the pod was restarted mid-job. Captures the shipped mitigation plus the larger refactors it points to — a dedicated pipeline worker, event-loop offloading, and poller/durability sharpening."
---

# 310-e Async-loop hygiene & pipeline worker hardening

> **Status: proposed.** Backlog, not yet scheduled. The quick mitigation
> (item 0) shipped; everything below is deferred shape work.

## Incident that triggered this

Dev, 2026-06-15. An upload of _purchase common data_ (`MODULE_PER_YEAR`)
ran as an in-process `fire_and_forget` asyncio task (`handler-174`) on the
**web server's event loop**. `process_csv_in_batches` did CPU-bound row
work between sparse yields; `/healthz` (a pure return) couldn't be
scheduled within the dev `livenessProbe.timeoutSeconds: 2`; the kubelet
failed 3 liveness checks and restarted the pod, killing the job. Symptoms
chased in order — `/ready` timeouts (red herring: readiness never
restarts), then OOM (ruled out: 460Mi peak vs 1000Mi cap), then the actual
cause: **liveness probe killed it on a starved event loop**. Stage was
spared only by more CPU headroom; the bug is latent there too.

Root lesson: **CPU-bound batch work must never run on the request event
loop**, and the platform should degrade gracefully when it does.

## 0. Shipped mitigation (done)

- `base_csv_provider.py`: row-loop yields every 100 rows (was 1000);
  defensive `await asyncio.sleep(0)` after each factor-type merge in
  `_setup_handlers_and_factors` (guards the ~23k-factor map build).
- `data_entry_repo.bulk_copy`: chunked `model_validate` (1000-row chunks
  with yields) instead of one 50k-row list-comp.
- Dev probe/resource override: liveness & readiness `timeoutSeconds 2 → 5`,
  CPU request `150m → 250m`.

These remove the immediate starvation but keep heavy work on the loop.
The items below address the underlying shape.

## Improvement backlog

| #   | Item                                                | Impact | Effort |
| --- | --------------------------------------------------- | ------ | ------ |
| 1   | Dedicated pipeline **worker Deployment**            | High   | L      |
| 2   | Offload CPU-bound ingestion off the loop            | High   | M      |
| 3   | Heartbeat-driven stale detection (drop fixed 60min) | Med    | M      |
| 4   | Eliminate per-row DB queries in ingestion           | Med    | M      |
| 5   | Concurrency / backpressure on imports               | Med    | S      |
| 6   | Event-loop-lag & probe-latency observability        | Med    | S      |
| 7   | Probe/resource parity dev↔base + startupProbe       | Low    | S      |
| 8   | Audit other sync-CPU-in-async hotspots              | Med    | M      |

### 1. Dedicated pipeline worker Deployment

Run pipeline consumption (`tasks/runner.py` + `_poller.py`) in a **second
long-running Deployment** off the same image, different command — _not_
dynamic per-job pods. Web pods only enqueue (`create job` →
`NOT_STARTED`); the worker polls and executes. Decouples ingestion CPU
from web liveness/readiness permanently; lets the two scale and be
resource-tuned independently. Web pods can then stop running the
in-process poller (`RUN_BACKGROUND_POLLER=false` on web, `true` on worker).
Cross-link: [[310-a-pod-safety]], [[310-c-dag-handler-registry]].

### 2. Offload CPU-bound ingestion off the event loop

Until/unless a worker lands, the CPU-bound parse/validate/COPY-buffer
build should run via `run_in_threadpool`/`asyncio.to_thread` with a sync
DB session, so a single job can't starve the loop regardless of yield
tuning. Pairs with item 8 (find the hotspots first).

### 3. Heartbeat-driven stale detection

`STALE_JOB_TIMEOUT_MINUTES=60` is a blunt instrument: a crash-looping job
takes up to 3×60min to exhaust `max_attempts` and surface as
`FINISHED+ERROR`. Now that the runner heartbeats `locked_at`, switch the
sweep to "no heartbeat for N×interval" so genuine crashes recover in
seconds while long-running jobs are never preempted. Also consider failing
fast when `attempts` climb due to repeated probe-kills (crash-loop
detection).

### 4. Eliminate per-row DB queries in ingestion

`check_institutional_id_unique` runs one query **per member row**
(`base_csv_provider.py:889`). Batch it (pre-load existing IDs per module,
check in-memory) to cut the long tail that made the incident job take ~48s.

### 5. Concurrency / backpressure on imports

Bound how many ingestion jobs run concurrently per pod/worker so two large
uploads can't compound CPU pressure. A simple semaphore or `POLLER_BATCH
_LIMIT`-style cap on _running_ (not just dispatched) jobs.

### 6. Event-loop-lag & probe-latency observability

Add an event-loop-lag metric and per-probe latency so this class of
problem is visible _before_ a restart. (Note: the `otel-collector:4317`
`DEADLINE_EXCEEDED` spam in dev is unrelated trace-export noise — fix or
silence it so it stops masquerading as a signal during incidents.)

### 7. Probe/resource parity + startupProbe

The dev override block diverged from the base chart (lower timeouts, no
`startupProbe`). Reconcile per-env overrides with `helm/values.yaml`, and
ensure every env keeps the `startupProbe` so cold starts aren't liveness-
killed. Right-size CPU requests against observed import bursts (~1 core).

### 8. Audit other sync-CPU-in-async hotspots

The factors-map build and `model_validate` were two; there are likely
others (large serializations, in-Python aggregations). Sweep async paths
for un-yielded CPU loops and large list-comps over DB result sets.

## Out of scope

Bug-level fixes already covered elsewhere; this is shape work. The
incident's regression coverage belongs with the ingestion test suite, not
here.
