---
status: in-progress
issue: 310-c
last_updated: 2026-05-06
title: "310-c — DAG + Handler Registry + Observability"
summary: "DAG-driven handler registry with observability columns replacing ad-hoc safety and auto-trigger code."
---

# 310-c — DAG + Handler Registry + Observability

## Context

After Plans A and B ship:

- Path 2 has claim_job, locked_by, pipeline_id, an in-process safety poller, and the
  factor → recalc auto-trigger.
- But each pipeline is still wired ad-hoc: `ProviderFactory` for ingestion, direct function
  calls (`run_recalculation`, `run_module_recalculation`) for emission tasks, a different
  function for unit sync. Plan B's `_enqueue_stale_recalculations` is a one-off helper that
  re-implements the chaining logic in-line.
- **Plan A's safety poller (`_poller.dispatch_job`) does not actually recover real ingestion
  jobs.** Today it tries to look up the handler via `meta["provider_name"]`, but real jobs
  don't persist the provider class name in `meta` — `provider_name` on provider classes is
  an `IngestionMethod` enum (`csv`, `api`), not a class name. The poller picks orphan
  `NOT_STARTED` rows, then logs `"No provider_name in meta — skipping"` and never
  re-dispatches them. Until this plan replaces `dispatch_job` with the unified runner,
  orphan recovery is effectively manual (via `POST /sync/jobs/{id}/recover`).

This plan unifies dispatch under a **handler registry** (`job_type` → handler fn) and a single
`run_job(job_id)` runner that every entry point uses. Every existing task becomes a handler
registered with a `job_type`. Plan B's helper folds into a generic `chain_job` used by every
handler. The poller is rewired to call `run_job(job_id)` — at which point orphan recovery
finally works.

Scope: **Path 2 only.** Path 1 (interactive UI) does not go through the runner.

Depends on: **Plan A** (claim_job, locked_by, job_type, pipeline_id), **Plan B** (factor
upsert + auto-recalc baseline).

---

## Handler registry (`backend/app/tasks/registry.py`)

```python
from typing import Awaitable, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_ingestion import DataIngestionJob

# Handler signature:
#   handler(job, job_session, data_session) -> dict (becomes job.meta on success)
HandlerFn = Callable[
    [DataIngestionJob, AsyncSession, AsyncSession],
    Awaitable[dict],
]

_REGISTRY: dict[str, HandlerFn] = {}

def register(job_type: str):
    """Decorator to register a handler for a job_type."""
    def decorator(fn: HandlerFn) -> HandlerFn:
        if job_type in _REGISTRY:
            raise ValueError(f"job_type {job_type!r} already registered")
        _REGISTRY[job_type] = fn
        return fn
    return decorator

def get_handler(job_type: str) -> HandlerFn:
    handler = _REGISTRY.get(job_type)
    if handler is None:
        raise ValueError(f"No handler registered for job_type={job_type!r}")
    return handler
```

### Registered job types after Plan C lands

| `job_type`               | Handler module                    | Description                         |
| ------------------------ | --------------------------------- | ----------------------------------- |
| `csv_ingest`             | `ingestion_tasks.py`              | CSV data-entry upload               |
| `api_ingest`             | `ingestion_tasks.py`              | API data-entry ingest (e.g. travel) |
| `factor_ingest`          | `ingestion_tasks.py`              | Factor CSV/API upsert               |
| `emission_recalc`        | `emission_recalculation_tasks.py` | Single-type recalc                  |
| `module_emission_recalc` | `emission_recalculation_tasks.py` | Module-level bulk recalc            |
| `unit_sync`              | `unit_sync_tasks.py`              | Accred unit + user sync             |
| `aggregation`            | (Plan D)                          | `carbon_reports.stats` recompute    |

Existing task functions are wrapped or annotated with `@register(...)`. Internal logic is
unchanged. The registration call site is the only addition.

Plan B's `_enqueue_stale_recalculations` is rewritten as a `factor_ingest` post-success step
that calls `chain_job(...)` per stale type (see below).

---

## Unified `run_job(job_id)` runner (`backend/app/tasks/runner.py`)

> **Delivered: PR #1044.** Notes inline below mark where the shipped
> shape diverges from the original sketch (driven by Copilot review on
> #1044 and prior-PR contracts that landed in the meantime: #1026's
> `started_at` atomic stamping inside `claim_job` and FINISHED-state
> auto-stamp of `finished_at`).

```python
import asyncio
from app.db import SessionLocal
from app.core.logging import get_logger
from app.models.data_ingestion import IngestionResult, IngestionState
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID
from app.tasks.registry import get_handler

logger = get_logger(__name__)

async def run_job(job_id: int) -> None:
    """
    Single dispatch path for every job_type. Used by:
      - endpoints (fire_and_forget(run_job(id)) after creating a job)
      - chain_job (fire_and_forget(run_job(child_id)) after a parent commits)
      - the safety poller (Plan A)
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        repo = DataIngestionRepository(job_session)
        job = await repo.get_job_by_id(job_id)
        if job is None:
            logger.error(f"run_job: job {job_id} not found")
            return
        if job.job_type is None:
            logger.error(f"run_job: job {job_id} has no job_type — refusing to dispatch")
            return

        # Capture job_type while it's narrowed to ``str`` by the check above;
        # the post-claim re-fetch widens it back to Optional[str].
        job_type: str = job.job_type

        if not await repo.claim_job(job_id, POD_ID):
            return  # another pod claimed it, or attempts exhausted, or finished

        # claim_job ran a raw SQL UPDATE (state=RUNNING, attempts++,
        # locked_by, locked_at, AND started_at via func.coalesce — atomic
        # with the RUNNING transition, see PR #1026).  The in-memory `job`
        # still reflects the pre-claim row; re-fetch so handlers see the
        # authoritative post-claim state.  A vanished row here = preempted
        # in the gap (treat as such).
        job = await repo.get_job_by_id(job_id)
        if job is None:
            logger.warning(f"run_job: job {job_id} disappeared after claim — exiting")
            return

        # Plain asyncio.create_task (NOT fire_and_forget): cancellation in
        # the finally block is the expected shutdown path, and
        # fire_and_forget's deliberate cancellation-WARNING (kept loud
        # for diagnosing the 310-B incident) would fire on every successful
        # run, drowning out genuine cancellations elsewhere.
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(job_id), name=f"heartbeat-{job_id}"
        )

        try:
            try:
                handler = get_handler(job_type)
                meta = await handler(job, job_session, data_session)
                status_message = str(meta.get("status_message", "Success"))
                metadata = dict(meta)
                result = meta.get("result", IngestionResult.SUCCESS)
                handler_succeeded = True
            except Exception as exc:
                logger.exception(
                    f"run_job: handler for job_type={job_type!r} failed (job {job_id})"
                )
                status_message = str(exc)
                metadata = {}
                result = IngestionResult.ERROR
                handler_succeeded = False

            # Preemption check covers BOTH success AND error paths.  If a
            # stale-lock sweep recovered this row mid-handler, a different
            # pod may now own it; our writes — successful or error — must
            # NOT race with the new owner.  Roll back data and skip the
            # state update; the new owner closes out.
            current = await repo.get_job_by_id(job_id)
            if current is None or current.locked_by != POD_ID:
                logger.warning(
                    f"run_job: job {job_id} preempted "
                    f"(locked_by={current and current.locked_by!r}); "
                    "rolling back data writes and exiting without updating job state"
                )
                await data_session.rollback()
                return

            if handler_succeeded:
                await data_session.commit()
            else:
                await data_session.rollback()
            await repo.update_ingestion_job(
                job_id,
                status_message=status_message,
                metadata=metadata,
                state=IngestionState.FINISHED,
                result=result,
                # NOTE: no finished_at parameter — PR #1026 dropped that
                # opt-in flag and made FINISHED auto-stamp the column.
            )
            await job_session.commit()
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
```

### Divergences from the original sketch

These changes landed in PR #1044; future Tier-2 PRs build on the
delivered shape, not the original code block above:

1. **Single preempt-check + state-write site** for both branches. The
   original sketch had separate FINISHED+SUCCESS and FINISHED+ERROR
   blocks with no preempt-check on the error path; that would race a
   new owner if the handler raised AFTER preemption.
2. **Re-fetch `job` after `claim_job`.** `claim_job` runs as a raw
   SQL `UPDATE` (not an ORM mutation), so the in-memory `job`
   instance still shows the pre-claim row state. Handlers that
   introspect `job.attempts` or `job.state` would see lies without
   the refresh.
3. **`set_started_at` is no longer called from the runner.** PR
   #1026 moved `started_at` stamping inside `claim_job` itself
   (atomic with the RUNNING transition via `func.coalesce`). The
   `set_started_at` repo helper remains as a primitive but is
   redundant in this path.
4. **`finished_at` stamping is automatic.** PR #1026 dropped the
   opt-in `finished_at: bool = False` flag from
   `update_ingestion_job`; transition to `state=FINISHED`
   auto-stamps the column.
5. **Heartbeat uses plain `asyncio.create_task`** (not
   `fire_and_forget`) so the deterministic `cancel()` + `await` in
   `finally` doesn't trip the loud cancellation WARNING that
   `fire_and_forget` emits.

All endpoints switch from per-task functions to:

```python
asyncio.create_task(run_job(created.id))
```

The legacy `run_ingestion`, `run_recalculation`, `run_module_recalculation`,
`sync_units_from_accred_task` sync wrappers are removed once their handler bodies are
registered. This is a follow-up cleanup commit within the same PR.

### Pod-crash safety net: heartbeat + preemption check (rolled in from PR #998 review)

PR #998 added an auto-recovery sweep to the safety poller (jobs stuck in RUNNING past
`STALE_JOB_TIMEOUT_MINUTES` get reset to NOT_STARTED or marked FINISHED+ERROR). The
review on that PR flagged a real concurrency hazard that lives until the runner
heartbeats: any job whose runtime exceeds the stale-timeout window is falsely
classified as stuck — the sweep recovers the row, another pod re-claims, and now two
pods are processing the same job. PR #998's mitigation is operational: bump
`STALE_JOB_TIMEOUT_MINUTES` to 60 min and document the caveat. The proper fix lives
here, in `run_job`, in two parts:

**1. Heartbeat the active worker.** Add a column or repurpose `locked_at`:

```python
# repo helper
async def heartbeat(self, job_id: int) -> None:
    await self.session.execute(
        update(DataIngestionJob)
        .where(col(DataIngestionJob.id) == job_id,
               col(DataIngestionJob.locked_by) == POD_ID,  # only OUR job
               col(DataIngestionJob.state) == IngestionState.RUNNING)
        .values(locked_at=func.now())
    )
    await self.session.commit()
```

Inside `run_job`, spawn a per-job heartbeat task that wakes every
`STALE_JOB_TIMEOUT_MINUTES / 4` (default: every 15 min for a 60 min timeout) and
calls `heartbeat(job_id)` until the handler returns. Wrap with `try/finally` so the
heartbeat task is reliably cancelled even if the handler raises. The auto-recovery
sweep then becomes safe regardless of how long the worker takes — what it actually
detects is "no heartbeat for >`STALE_JOB_TIMEOUT_MINUTES`," i.e. real pod death.

**2. Worker-side preemption check.** Defence-in-depth for the brief window before
the first heartbeat fires, and for any future regression in heartbeat scheduling.
Inside `run_job`, before each `data_session.commit()`:

```python
current = await repo.get_job_by_id(job_id)
if current is None or current.locked_by != POD_ID:
    logger.warning(
        f"Job {job_id} was preempted (locked_by={current and current.locked_by!r}); "
        "rolling back our work and exiting"
    )
    await data_session.rollback()
    return  # do NOT update job state — the new owner will
```

Together these eliminate the duplicate-processing risk that PR #998's sweep adds.
With the heartbeat, `STALE_JOB_TIMEOUT_MINUTES` can be tightened back down (10–15 min)
to bound recovery latency on real crashes.

---

## DAG chaining via `chain_job` helper

> **Delivered: PR #1044.** Plan B's `_enqueue_stale_recalculations`
> will fold into a `chain_job` call when its `factor_ingest` handler
> is registered (Tier-2 PR #2).

```python
# backend/app/tasks/runner.py

async def chain_job(
    parent: DataIngestionJob,
    *,
    job_type: str,
    session: AsyncSession,
    module_type_id: Optional[int] = None,
    data_entry_type_id: Optional[int] = None,
    year: Optional[int] = None,
    config: Optional[dict] = None,
    target_type: TargetType = TargetType.DATA_ENTRIES,
    ingestion_method: IngestionMethod = IngestionMethod.computed,
    entity_type: EntityType = EntityType.MODULE_PER_YEAR,
) -> int:
    """
    Create a child job that inherits parent's pipeline_id and fire it via
    fire_and_forget. Safety poller picks up if pod crashes between commit
    and fire_and_forget.

    ``module_type_id`` and ``year`` inherit from the parent when the
    caller passes None.  ``data_entry_type_id`` is intentionally NOT
    inherited: a multi-det parent (e.g. a FACTORS ingest spanning
    several dets) fans out to one child per det, so the caller MUST
    pass the specific det per call.

    Returns child job_id.  If ``parent.pipeline_id`` is None, generates
    a fresh UUID and persists it on the parent BEFORE creating the
    child — so a pod-crash-then-recovery of the parent doesn't
    generate a different UUID and orphan the child.
    """
    repo = DataIngestionRepository(session)

    pipeline_id = parent.pipeline_id
    if pipeline_id is None:
        pipeline_id = uuid4()
        parent.pipeline_id = pipeline_id
        session.add(parent)
        await session.commit()

    child = DataIngestionJob(
        job_type           = job_type,
        module_type_id     = module_type_id if module_type_id is not None else parent.module_type_id,
        data_entry_type_id = data_entry_type_id,  # NO inheritance — see docstring
        year               = year if year is not None else parent.year,
        target_type        = target_type,
        ingestion_method   = ingestion_method,
        entity_type        = entity_type,
        state              = IngestionState.NOT_STARTED,
        is_current         = False,
        pipeline_id        = pipeline_id,
        # NULL means "runnable immediately" — claim_job's WHERE treats
        # NULL run_after as eligible.  Matches the existing
        # ingestion_tasks.py recalc-job creation pattern.
        run_after          = None,
        meta               = {"config": config or {}, "parent_job_id": parent.id},
    )
    created = await repo.create_ingestion_job(child)
    await session.commit()
    fire_and_forget(run_job(created.id), name=f"run_job-{created.id}")
    return created.id
```

### Fan-out

A handler that needs to chain to N children just calls `chain_job` N times. The factor_ingest
handler's post-success block becomes:

```python
@register("factor_ingest")
async def factor_ingest_handler(job, job_session, data_session):
    # ... existing factor upsert logic (Plan B) ...
    # On success, fan out to one emission_recalc per stale (module, det):
    if final_result != IngestionResult.ERROR:
        rows = await DataIngestionRepository(job_session).get_recalculation_status_by_year(job.year)
        for row in rows:
            if not row["needs_recalculation"]:
                continue
            if job.module_type_id is not None and row["module_type_id"] != job.module_type_id:
                continue
            if job.data_entry_type_id is not None and row["data_entry_type_id"] != job.data_entry_type_id:
                continue
            await chain_job(
                job,
                job_type="emission_recalc",
                module_type_id=row["module_type_id"],
                data_entry_type_id=row["data_entry_type_id"],
                year=job.year,
                config={"data_entry_type_id": row["data_entry_type_id"]},
                session=job_session,
            )
    return {"upsert_count": ..., "recalc_jobs_chained": len(...)}
```

`pipeline_id` lifecycle (final): the **endpoint** generates a UUID for jobs that initiate a
multi-step flow (factor_ingest, csv_ingest, etc.). All chained children inherit it via
`chain_job`. Single-step jobs (e.g. ad-hoc `emission_recalc` triggered by an operator) get a
fresh UUID at endpoint time. The dashboard query groups by `pipeline_id` to show full pipeline
runs.

---

## Backward compatibility for jobs without `job_type`

Plan A added `job_type` as nullable. The runner refuses to dispatch a job with `job_type IS
NULL`. Handling at deploy time:

1. New code creates jobs with `job_type` always set.
2. Pre-existing in-flight jobs (created before deploy, still running under legacy dispatch)
   are unaffected — they finish under the old code path.
3. Pre-existing FINISHED jobs are read-only history.
4. The poller skips `job_type IS NULL` rows (filter added to its SELECT).

No backfill migration needed.

### Poller cutover (resolves Plan A's broken `dispatch_job`)

Plan A's `_poller.dispatch_job` reads `meta["provider_name"]` to choose a handler. Real
ingestion jobs don't persist that field, so the poller silently skips them. Plan C replaces
the poller's body with a single call:

```python
# backend/app/tasks/_poller.py — after Plan C
from app.tasks.runner import run_job

async def poll_pending_jobs() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                stmt = (
                    select(DataIngestionJob)
                    .where(
                        DataIngestionJob.state == IngestionState.NOT_STARTED,
                        DataIngestionJob.job_type.is_not(None),  # NEW
                        or_(
                            DataIngestionJob.run_after.is_(None),
                            DataIngestionJob.run_after <= func.now(),
                        ),
                        DataIngestionJob.locked_by.is_(None),
                        DataIngestionJob.attempts < DataIngestionJob.max_attempts,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(10)
                )
                jobs = (await session.execute(stmt)).scalars().all()
                for job in jobs:
                    asyncio.create_task(run_job(job.id))
        except Exception as exc:
            logger.warning(f"Poller iteration failed: {exc}", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

The old `dispatch_job` / `schedule_job` helpers are deleted. The `run_job` runner reads
`job_type` from the row itself, looks up the registered handler, and invokes it — no
`meta["provider_name"]` plumbing needed.

Until Plan C lands, document the gap explicitly: orphan recovery for ingestion jobs is
**manual** via `POST /sync/jobs/{id}/recover` and the 30-min stale window. Operators should
be aware.

---

## Observability

### Migration

```sql
ALTER TABLE data_ingestion_jobs
  ADD COLUMN started_at  TIMESTAMPTZ,
  ADD COLUMN finished_at TIMESTAMPTZ;
```

### Semantics (clarified)

- **`locked_at`** (Plan A): updates on **every** claim — most recent attempt's lock time.
  Used to detect stale locks (`locked_at < now() - STALE_JOB_TIMEOUT`).
- **`started_at`** (this plan): set on **first** claim only (`if job.started_at is None`).
  Stays put across retries. Used to compute total wall-clock duration.
- **`finished_at`**: set when job reaches FINISHED state.

`started_at` and `finished_at` together give true duration. `locked_at` alone is per-attempt.

### Repository helpers

```python
async def set_started_at(self, job_id: int) -> None:
    await self.session.execute(
        update(DataIngestionJob)
        .where(
            DataIngestionJob.id == job_id,
            DataIngestionJob.started_at.is_(None),
        )
        .values(started_at=func.now())
    )

# update_ingestion_job extended with optional finished_at: bool = False arg that
# sets finished_at=now() when state transitions to FINISHED.
```

### Dashboard query (documented; no code change)

```sql
SELECT
    job_type,
    state,
    result,
    count(*)                                                          AS jobs,
    avg(extract(epoch from (finished_at - started_at)))               AS avg_duration_s,
    percentile_cont(0.95) within group (order by extract(epoch from (finished_at - started_at)))
                                                                      AS p95_duration_s,
    sum(case when attempts > 1 then 1 else 0 end)                     AS retried_jobs
FROM data_ingestion_jobs
WHERE created_at > now() - interval '7 days'
  AND job_type IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1, 2;
```

### `pipeline_id` query (multi-step run progress)

```sql
SELECT id, job_type, state, result, started_at, finished_at, status_message
  FROM data_ingestion_jobs
 WHERE pipeline_id = :pipeline_id
 ORDER BY id;
```

Surface this via `GET /sync/pipelines/{pipeline_id}` so the frontend can stream all jobs in a
multi-step run, not just the first.

---

## Tests

| Test                       | Assertion                                                            |
| -------------------------- | -------------------------------------------------------------------- |
| `register` decorator       | handler registered; second `@register("X")` raises                   |
| `get_handler` registered   | returns fn                                                           |
| `get_handler` unknown      | raises ValueError                                                    |
| `run_job` unknown job_type | logs error, no claim, no state change                                |
| `run_job` claim fails      | returns without invoking handler                                     |
| `run_job` success          | handler called, data committed, state=FINISHED, finished_at set      |
| `run_job` handler raises   | data rolled back, state=FINISHED/ERROR, status_message=exc str       |
| `run_job` first attempt    | started_at set                                                       |
| `run_job` retry attempt    | started_at unchanged; locked_at updated                              |
| `chain_job`                | child created with parent's pipeline_id, run_after=now(), task fired |
| `factor_ingest` fan-out    | N stale types → N children chained, all with same pipeline_id        |
| Pipeline endpoint          | `GET /sync/pipelines/{id}` returns ordered job list                  |

---

## Relevant files

- `backend/app/tasks/registry.py` (new)
- `backend/app/tasks/runner.py` (new — `run_job`, `chain_job`)
- `backend/app/tasks/ingestion_tasks.py` — handlers wrapped with `@register("csv_ingest" / "api_ingest" / "factor_ingest")`
- `backend/app/tasks/emission_recalculation_tasks.py` — wrapped with `@register("emission_recalc" / "module_emission_recalc")`
- `backend/app/tasks/unit_sync_tasks.py` — wrapped with `@register("unit_sync")`
- `backend/app/tasks/_poller.py` (Plan A) — switched to call `run_job` instead of legacy dispatch
- `backend/app/repositories/data_ingestion.py` — `set_started_at`, `update_ingestion_job(finished_at=True)` extension
- `backend/app/api/v1/data_sync.py` — endpoints switch from per-task functions to `asyncio.create_task(run_job(id))`; new `GET /sync/pipelines/{id}`
- `backend/app/models/data_ingestion.py` — `started_at`, `finished_at` columns
- `backend/migrations/` — 1 migration (started_at, finished_at)

---

## Follow-ups rolled in from PR #976 review

These were noted on PR #976 (Plan B) as "out-of-scope here, fits Plan C." None block
Plan B's merge; flagged here so they aren't lost.

### Permission gate on `GET /factors/stale`

The stale-factor list endpoint added in Plan B (`backend/app/api/v1/factors.py`) currently
requires only `Depends(get_current_user)` — any authenticated user can list which factors
are out of sync with the latest CSV upload. Other operator endpoints in `data_sync.py`
gate on `backoffice.data_management.view`. Tighten the dependency to match:

```python
current_user: User = Depends(
    require_permission("backoffice.data_management", "view")
),
```

This is a one-line change but pairs naturally with Plan C's broader cleanup of
backoffice endpoints, so rolling it in here keeps the auth surface coherent.

### Fan-out instrumentation on the parent factor job

`_enqueue_stale_recalculations` (Plan B, in `ingestion_tasks.py`) returns silently when
no recalc children get fired (e.g. `year is None`, or
`MODULE_TYPE_TO_DATA_ENTRY_TYPES[module]` is empty). The parent FACTORS job still
finishes with `result=SUCCESS` and a generic status message — operators have no in-band
signal that "factor uploaded but no recalc cascade ran."

When Plan C generalises this into `chain_job`, stamp the count of fired children into
the parent's `extra_metadata`:

```python
fired_children = await chain_job(parent, ...)
await update_ingestion_job(
    parent.id,
    extra_metadata={"children_fired": len(fired_children),
                    "child_pipeline_id": str(pipeline_id)},
)
```

Cheap, makes the chain auditable without parsing logs.

### Stable ordering on `list_stale_for_year`

`FactorRepository.list_stale_for_year` orders by `(data_entry_type_id, id)` after the
PR #976 fix, but if Plan C reshapes the stale-factor surface (e.g. as part of
`/sync/pipelines/{id}` rollup), preserve the deterministic ordering — operators
diffing two reads back-to-back rely on it.

### PG test fixture drift

Plan B's PG tests inline `_install_plan_310b_indexes(engine)` to add the partial
unique indexes that `SQLModel.metadata.create_all` doesn't know about. Once Plan C
adds `started_at` / `finished_at` and the `pipeline_id` query, more migration-only
DDL will accumulate. Promote the inline DDL into a shared `pg_dsn_with_310b` fixture
in `conftest.py` so every PG-bound test gets the production schema without
copy-pasting `CREATE UNIQUE INDEX` blocks.
