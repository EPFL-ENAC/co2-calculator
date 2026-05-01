# 310a — Pod Safety + Atomic Claim

## Context

FastAPI runs sync background tasks in a thread-pool executor. Two concurrent HTTP requests, or
two pods handling the same trigger, can run the same job type simultaneously. The existing
flow creates a job at `state=NOT_STARTED, is_current=False`, then the background task sets
`is_current=True` only after starting — leaving a race window during which the partial unique
index does not protect anything.

This plan is the **foundation for all 310 plans**. It introduces the atomic claim, the safety
poller, and the new job model fields used by Plans B, C, and D.

Scope: **Path 2 only** (bulk/operator). Path 1 (interactive UI) is unchanged.

---

## Model changes (`backend/app/models/data_ingestion.py`)

Add to `DataIngestionJob`:

```python
# Claiming
locked_by:  Optional[str]      = Field(None)  # set atomically on claim
locked_at:  Optional[datetime] = Field(None)  # most recent claim time (updates on retry)

# Retry scaffolding (used live by Plan A's poller; max_attempts honored by claim_job)
attempts:     int               = Field(0)
max_attempts: int               = Field(3)
run_after:    Optional[datetime] = Field(None)  # NULL = run immediately

# Grouping / dispatch
pipeline_id: Optional[uuid.UUID] = Field(None)  # groups jobs in a multi-step run
job_type:    Optional[str]        = Field(None)  # "csv_ingest", "factor_ingest",
                                                  # "emission_recalc", "unit_sync", etc.
```

`pipeline_id` lifecycle: the **endpoint** that initiates a multi-step flow generates a UUID
and stores it on the first job's row. Plan B's auto-recalc trigger and Plan C's chained
handlers propagate the parent's `pipeline_id` to children via `chain_job(...)` helper
(Plan C).

`job_type` is nullable for backward compatibility; the runner (Plan C) treats `NULL` as
"unknown — log and skip." Existing in-flight jobs at deploy time finish under the legacy
dispatch and never enter the new runner. New jobs always set `job_type`.

---

## Migration

```sql
ALTER TABLE data_ingestion_jobs
  ADD COLUMN locked_by    VARCHAR(255),
  ADD COLUMN locked_at    TIMESTAMPTZ,
  ADD COLUMN attempts     INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3,
  ADD COLUMN run_after    TIMESTAMPTZ,
  ADD COLUMN pipeline_id  UUID,
  ADD COLUMN job_type     VARCHAR(100);

CREATE INDEX ix_data_ingestion_jobs_pending
    ON data_ingestion_jobs (run_after)
    WHERE state = 0      -- NOT_STARTED
      AND locked_by IS NULL;   -- supports the safety poller
```

---

## Pod ID

Evaluated once at process start (module-level constant):

```python
# backend/app/tasks/_pod_id.py
import os, socket
POD_ID: str = os.environ.get("HOSTNAME", socket.gethostname())
```

In Kubernetes, `HOSTNAME` is automatically set to the pod name.

---

## Atomic `claim_job` (closes the `is_current` race)

`claim_job` runs **two statements in one DB transaction**: first it unsets any previous
current row for the same `(module, det, target, method, year)` combo, then it atomically
flips the target row to `state=RUNNING, is_current=TRUE, locked_by=POD_ID`.

```python
# backend/app/repositories/data_ingestion.py

async def claim_job(self, job_id: int, pod_id: str) -> bool:
    """
    Atomically claim a job for execution.

    Returns True if this caller claimed it; False if another pod beat us, the job
    is no longer eligible, or attempts >= max_attempts.

    Two-step transaction:
      1. Unset is_current on previous current row (if any) for the same
         (module_type_id, data_entry_type_id, target_type, ingestion_method, year)
         combo, EXCEPT the row we're claiming.
      2. Atomic UPDATE on the target row. The partial unique index trips here
         if a concurrent claimer already set is_current=TRUE on a different row
         for the same combo.
    """
    job = await self.get_job_by_id(job_id)
    if job is None:
        return False

    # Step 1: clear previous is_current for this combo
    where = and_(
        col(DataIngestionJob.is_current),
        col(DataIngestionJob.id) != job_id,
        col(DataIngestionJob.target_type) == job.target_type,
        col(DataIngestionJob.ingestion_method) == job.ingestion_method,
        col(DataIngestionJob.year) == job.year,
    )
    if job.module_type_id is None:
        where = and_(where, col(DataIngestionJob.module_type_id).is_(None))
    else:
        where = and_(where, col(DataIngestionJob.module_type_id) == job.module_type_id)
    if job.data_entry_type_id is None:
        where = and_(where, col(DataIngestionJob.data_entry_type_id).is_(None))
    else:
        where = and_(
            where, col(DataIngestionJob.data_entry_type_id) == job.data_entry_type_id
        )
    await self.session.execute(
        update(DataIngestionJob).where(where).values(is_current=False)
    )

    # Step 2: atomic claim. Unique index trips on race.
    try:
        result = await self.session.execute(
            update(DataIngestionJob)
            .where(
                col(DataIngestionJob.id) == job_id,
                col(DataIngestionJob.state).in_(
                    [IngestionState.NOT_STARTED, IngestionState.QUEUED]
                ),
                col(DataIngestionJob.locked_by).is_(None),
                col(DataIngestionJob.attempts) < col(DataIngestionJob.max_attempts),
            )
            .values(
                locked_by=pod_id,
                locked_at=func.now(),
                state=IngestionState.RUNNING,
                is_current=True,
                attempts=col(DataIngestionJob.attempts) + 1,
            )
            .returning(DataIngestionJob.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None
    except IntegrityError:
        # Unique-index trip: another pod claimed for this combo
        await self.session.rollback()
        return False
```

`mark_job_as_current` becomes a private helper used only by `claim_job` — direct callers in
existing tasks are removed (see "Task changes" below).

---

## Per-task changes

The "set state=RUNNING" calls in tasks are replaced by `claim_job` differently per file:

### `backend/app/tasks/ingestion_tasks.py` (`run_sync_task`)

The provider's `_update_job(state=RUNNING)` call is replaced by `repo.claim_job(job_id, POD_ID)`
called BEFORE `provider.ingest()`. If claim fails, return early without invoking the provider.

### `backend/app/tasks/emission_recalculation_tasks.py`

Both `run_recalculation_task` (lines 58-66) and `run_module_recalculation_task` (lines 172-180)
currently do:

```python
await job_repo.update_ingestion_job(state=IngestionState.RUNNING, ...)
await job_repo.mark_job_as_current(job)
await job_session.commit()
```

Replace with:

```python
claimed = await job_repo.claim_job(job_id, POD_ID)
if not claimed:
    logger.info(f"Job {job_id} already claimed by another pod or not eligible")
    return
```

The subsequent `update_ingestion_job(state=RUNNING, status_message="...")` calls remain (for
SSE progress) but no longer flip state — they only update the message.

### `backend/app/tasks/unit_sync_tasks.py`

The current `run_sync_task_accred` does not interact with `DataIngestionJob` at all (returns
`job_id=0`). Plan B reworks this; Plan A only adds the import path for `claim_job`.

---

## Stale-lock recovery (manual)

Add `POST /sync/jobs/{job_id}/recover` (permission `backoffice.data_management.sync`):

```python
# Resets a job stuck in RUNNING after a pod crash.
# Allowed only if locked_at < now() - settings.STALE_JOB_TIMEOUT.
UPDATE data_ingestion_jobs
   SET state     = 'NOT_STARTED',
       locked_by = NULL,
       locked_at = NULL,
       attempts  = 0,         -- give it a fresh quota
       run_after = now()
 WHERE id = :job_id
   AND state = 'RUNNING'
   AND locked_at < now() - :stale_timeout
RETURNING id;
```

`STALE_JOB_TIMEOUT` is a settings value (default `interval '30 minutes'`), not a magic
number.

---

## In-process safety poller

The poller is the orphan-recovery mechanism. It lives next to `claim_job` because it operates
on the same fields.

```python
# backend/app/tasks/_poller.py
import asyncio
from app.core.config import settings
from app.db import SessionLocal
from app.models.data_ingestion import DataIngestionJob, IngestionState
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID
# Plan C: from app.tasks.runner import run_job
# In Plan A, run_job is the legacy dispatch (run_ingestion / run_recalculation / etc.)
# selected by job_type. Plan C consolidates this.

POLL_INTERVAL_SECONDS = 10

async def poll_pending_jobs() -> None:
    """Pick up jobs that were created but never scheduled (e.g. crashed pod)."""
    while True:
        try:
            async with SessionLocal() as session:
                stmt = (
                    select(DataIngestionJob)
                    .where(
                        DataIngestionJob.state == IngestionState.NOT_STARTED,
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


def start_poller(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _startup():
        if settings.RUN_BACKGROUND_POLLER:
            app.state.poller_task = asyncio.create_task(poll_pending_jobs())

    @app.on_event("shutdown")
    async def _shutdown():
        task = getattr(app.state, "poller_task", None)
        if task:
            task.cancel()
```

`settings.RUN_BACKGROUND_POLLER` defaults to `True` in production, `False` in tests.

`SKIP LOCKED` ensures multiple pods polling concurrently never claim the same row twice. The
10s interval is conservative — well under 1 RPS even at 10 pods. Decrease only if observed
chain latency becomes a bottleneck.

---

## Tests

| Test                                      | Assertion                                                                                                                             |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `claim_job` success path                  | RUNNING + is_current=TRUE; previous current row unset; returns True                                                                   |
| `claim_job` duplicate                     | second call returns False, no state change                                                                                            |
| `claim_job` exceeds max_attempts          | returns False                                                                                                                         |
| `claim_job` already FINISHED              | returns False                                                                                                                         |
| **Concurrent claim race (real Postgres)** | two `asyncio.gather(claim_job(j1), claim_job(j2))` for the same combo — exactly one returns True; other rolls back via IntegrityError |
| `run_sync_task` claim guard               | mock `claim_job → False`, assert task returns without invoking provider                                                               |
| `run_recalculation_task` claim guard      | same                                                                                                                                  |
| `POST /jobs/{id}/recover` stale           | resets state + attempts, sets run_after=now()                                                                                         |
| `POST /jobs/{id}/recover` not stale       | returns 409                                                                                                                           |
| Poller picks up orphan job                | seed job with state=NOT_STARTED, locked_by=NULL; assert poller schedules it                                                           |

The concurrent-claim test must use the actual test Postgres — unit tests with mocks cannot
exercise the unique-index trip.

---

## Settings additions

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    ...
    STALE_JOB_TIMEOUT_MINUTES: int = 30
    RUN_BACKGROUND_POLLER: bool = True
```

---

## Relevant files

- `backend/app/models/data_ingestion.py` — new fields
- `backend/app/repositories/data_ingestion.py` — `claim_job`; `mark_job_as_current` becomes private
- `backend/app/tasks/_pod_id.py` (new)
- `backend/app/tasks/_poller.py` (new)
- `backend/app/tasks/ingestion_tasks.py` — claim before provider.ingest
- `backend/app/tasks/emission_recalculation_tasks.py` — replace state-flip + mark with claim_job
- `backend/app/api/v1/data_sync.py` — `POST /jobs/{id}/recover`
- `backend/app/main.py` (or wherever `app` is created) — wire `start_poller(app)`
- `backend/app/core/config.py` — settings
- `backend/migrations/` — 1 migration (job columns + partial index)
