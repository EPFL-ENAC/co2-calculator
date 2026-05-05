---
status: delivered
last_updated: 2026-05-05
summary: In-process asyncio.create_task chained jobs with a 10s safety-net poller; defer Celery until data-volume thresholds.
---

# ADR-010: Background Job Processing

**Status**: Accepted
**Date**: 2026-05-05 (supersedes 2025-11-10 "Planned")
**Deciders**: Development Team
**Related**: [ADR-004: Database Selection](./004-database-selection.md); plan `docs/src/implementation-plans/310-overview.md`

## Context

Path 2 (bulk operator) workflows — CSV ingest, factor sync, emission
recalculation, unit sync — must run asynchronously across multi-pod
deployments. Earlier drafts assumed Celery + Redis, but the data
volume never demanded a dedicated worker fleet. Meanwhile, ad-hoc
FastAPI `BackgroundTasks` exposed pod-collision races, untracked
`unit_sync` jobs, and stuck `RUNNING` rows after pod crashes.

We needed a model that runs reliably in-process today yet stays
swappable when throughput justifies isolated workers.

## Decision

Use **in-process `asyncio.create_task`** to chain pipeline steps,
backed by a **10-second safety-net poller** in every web pod.

1. **Fast path**: a successful job handler calls
   `asyncio.create_task(run_job(next_job_id))` to fire the next step
   in milliseconds.
2. **Safety net**: each pod polls every 10s for orphan jobs
   (`state=NOT_STARTED AND run_after<=now() AND locked_by IS NULL`)
   using `FOR UPDATE SKIP LOCKED`, recovering chains broken by pod
   crashes.
3. **Atomic claim**: `claim_job` flips `state=RUNNING` and
   `is_current=TRUE` in a single transaction, guarded by the partial
   unique index on `(state, is_current)`. Pod collisions lose the
   UPDATE, not the data.

**Celery + Redis is deferred**, not rejected. Plan C's handler
registry (`run_job(job_id)`) keeps the dispatch boundary clean: a
future Deployment can host the runner without rewriting handlers.

See `docs/src/implementation-plans/310-overview.md` for the full
rationale and the four-plan roadmap (310-a through 310-d).

## Consequences

**Positive**:

- Zero new infrastructure (no Redis broker, no worker fleet).
- Sub-second chain latency on the happy path.
- Crash recovery within 10s without operator intervention.
- Atomic `claim_job` eliminates the duplicate-write race (ADR-015).
- Handler registry keeps the migration path to Celery cheap.

**Negative**:

- Job CPU shares the web pod's event loop. Bulk recalcs can affect
  request p95 — monitored, not yet observed.
- Poller adds ~1 SELECT/pod/10s; trivial today, audit at scale.
- No job-level resource isolation (memory caps, priority queues).

**Re-evaluate Celery when** any of:

- p95 web latency rises during ingestion.
- Job throughput exceeds ~100 jobs/minute.
- Recalcs need >4 GB RAM per worker.
- Sub-second chain latency required (10s poll becomes the floor).

## References

- `docs/src/implementation-plans/310-overview.md`
- `docs/src/implementation-plans/310-a-pod-safety.md`
- [ADR-015: claim_job atomic claim](./015-claim-job-atomic-state-is-current.md)
