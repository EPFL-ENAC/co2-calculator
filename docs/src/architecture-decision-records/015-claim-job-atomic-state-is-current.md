---
status: delivered
last_updated: 2026-05-05
summary: claim_job sets state=RUNNING and is_current=TRUE atomically, letting the partial unique index reject the second pod.
---

# ADR-015: Atomic `claim_job` on `state` + `is_current`

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team
**Related**: [ADR-010: Background Job Processing](./010-background-job-processing.md); plan `docs/src/implementation-plans/310-a-pod-safety.md`

## Context

The legacy job lifecycle created a row at
`state=NOT_STARTED, is_current=FALSE`, then the background task set
`is_current=TRUE` only after starting. The partial unique index
`ix_data_ingestion_jobs_is_current_unique` therefore protected
nothing during the gap. Two concurrent operator clicks, or two pods
handling the same trigger, both ran the same job and double-wrote
`carbon_reports`.

## Decision

`claim_job(job_id, pod_id)` performs the claim in **one DB
transaction with two statements**:

1. `UPDATE` to unset `is_current` on any previous current row for the
   same `(module_type_id, data_entry_type_id, target_type,
ingestion_method, year)` combo.
2. `UPDATE` the target row to
   `state=RUNNING, is_current=TRUE, locked_by=POD_ID,
locked_at=NOW(), attempts=attempts+1`,
   gated by `WHERE id=:id AND state=NOT_STARTED AND
attempts<max_attempts`.

Two pods racing this transaction both attempt step 2. Step 1 in pod
B's transaction tries to flip the same `is_current=TRUE` row that
pod A just set, but the partial unique index trips before commit.
Pod B's transaction rolls back; `claim_job` returns `False`.

Returns:

- `True` — caller owns the job, must run it.
- `False` — another pod won, or the job is no longer eligible
  (`state != NOT_STARTED`, `attempts >= max_attempts`).

## Consequences

**Positive**:

- Pod collisions on the bulk path are eliminated by the database,
  not by application-level locks.
- Combined with the 10s safety-net poller (ADR-010), crashed claims
  recover automatically: the next poller re-claims the row once
  `locked_by` clears (handled by the recovery path in 310-a).
- Backbone for `attempts`/`max_attempts` retry semantics — each
  re-claim increments `attempts`, capping retry storms.

**Negative**:

- Caller must check the `bool` return and skip silently on `False`.
  Forgetting this re-introduces double-execution; covered by
  integration tests in 310-a.
- The partial unique index must be present before deploying this
  code path. Migration ordering matters — the column add and index
  creation ship in the same Alembic revision as `claim_job`.

**Tested under contention** with a real PostgreSQL fixture that
fires two concurrent `claim_job` calls and asserts exactly one
returns `True`. SQLite is not a substitute for this test.

## References

- `docs/src/implementation-plans/310-a-pod-safety.md`
- `docs/src/implementation-plans/310-overview.md`
- [ADR-010: Background Job Processing](./010-background-job-processing.md)
