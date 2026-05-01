# 310c — DAG + Handler Registry + Observability

## Context

After Plans A and B ship:

- Path 2 has claim_job, locked_by, pipeline_id, an in-process safety poller, and the
  factor → recalc auto-trigger.
- But each pipeline is still wired ad-hoc: `ProviderFactory` for ingestion, direct function
  calls (`run_recalculation`, `run_module_recalculation`) for emission tasks, a different
  function for unit sync. Plan B's `_enqueue_stale_recalculations` is a one-off helper that
  re-implements the chaining logic in-line.

This plan unifies dispatch under a **handler registry** (`job_type` → handler fn) and a single
`run_job(job_id)` runner that every entry point uses. Every existing task becomes a handler
registered with a `job_type`. Plan B's helper folds into a generic `chain_job` used by every
handler.

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

```python
import asyncio, logging
from app.db import SessionLocal
from app.models.data_ingestion import IngestionResult, IngestionState
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID
from app.tasks.registry import get_handler

logger = logging.getLogger(__name__)

async def run_job(job_id: int) -> None:
    """
    Single dispatch path for every job_type. Used by:
      - endpoints (asyncio.create_task(run_job(id)) after creating a job)
      - chain_job (asyncio.create_task(run_job(child_id)) after a parent finishes)
      - the safety poller (Plan A)
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        repo = DataIngestionRepository(job_session)
        job = await repo.get_job_by_id(job_id)
        if job is None:
            logger.error(f"Job {job_id} not found")
            return
        if job.job_type is None:
            logger.error(f"Job {job_id} has no job_type — refusing to dispatch")
            return

        if not await repo.claim_job(job_id, POD_ID):
            return  # another pod claimed it, or attempts exhausted, or finished

        # claim_job already set state=RUNNING and is_current=TRUE; record started_at if new
        if job.started_at is None:
            await repo.set_started_at(job_id)
            await job_session.commit()

        try:
            handler = get_handler(job.job_type)
            meta = await handler(job, job_session, data_session)
            await data_session.commit()
            await repo.update_ingestion_job(
                job_id,
                status_message=meta.get("status_message", "Success"),
                metadata=meta,
                state=IngestionState.FINISHED,
                result=meta.get("result", IngestionResult.SUCCESS),
                finished_at=True,
            )
            await job_session.commit()
        except Exception as exc:
            logger.exception(f"Handler for {job.job_type} failed (job {job_id})")
            await data_session.rollback()
            await repo.update_ingestion_job(
                job_id,
                status_message=str(exc),
                metadata={},
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                finished_at=True,
            )
            await job_session.commit()
```

All endpoints switch from per-task functions to:

```python
asyncio.create_task(run_job(created.id))
```

The legacy `run_ingestion`, `run_recalculation`, `run_module_recalculation`,
`sync_units_from_accred_task` sync wrappers are removed once their handler bodies are
registered. This is a follow-up cleanup commit within the same PR.

---

## DAG chaining via `chain_job` helper

Plan B's `_enqueue_stale_recalculations` becomes a special case of:

```python
# backend/app/tasks/runner.py

async def chain_job(
    parent: DataIngestionJob,
    *,
    job_type: str,
    module_type_id: Optional[int] = None,
    data_entry_type_id: Optional[int] = None,
    year: Optional[int] = None,
    config: Optional[dict] = None,
    target_type: TargetType = TargetType.DATA_ENTRIES,
    ingestion_method: IngestionMethod = IngestionMethod.computed,
    entity_type: EntityType = EntityType.MODULE_PER_YEAR,
    session: AsyncSession,
) -> int:
    """
    Create a child job that inherits parent's pipeline_id and fire it via
    asyncio.create_task. Safety poller picks up if pod crashes between commit
    and create_task.

    Returns child job_id.
    """
    child = DataIngestionJob(
        job_type           = job_type,
        module_type_id     = module_type_id   if module_type_id   is not None else parent.module_type_id,
        data_entry_type_id = data_entry_type_id,
        year               = year             if year             is not None else parent.year,
        target_type        = target_type,
        ingestion_method   = ingestion_method,
        entity_type        = entity_type,
        state              = IngestionState.NOT_STARTED,
        pipeline_id        = parent.pipeline_id,    # inherit grouping
        run_after          = func.now(),
        meta               = {"config": config or {}, "parent_job_id": parent.id},
    )
    repo = DataIngestionRepository(session)
    created = await repo.create_ingestion_job(child)
    await session.commit()
    asyncio.create_task(run_job(created.id))
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
