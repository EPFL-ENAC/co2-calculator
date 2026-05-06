"""Plan 310-C unified job runner.

The runner is the single dispatch path for every Plan 310-C
``DataIngestionJob``.  Endpoints, the safety poller, and ``chain_job``
all funnel through ``run_job(job_id)``; the registry resolves the
correct handler from ``job.job_type``.

Why a single dispatcher:

- **One claim path** — every job goes through ``claim_job``, so the
  pod-safety guarantees from Plan 310-A (atomic state→RUNNING +
  attempts++ + locked_by + ``started_at`` stamping) apply uniformly.
- **One observability path** — every job ends with the same
  ``update_ingestion_job(state=FINISHED, …)`` call, which auto-stamps
  ``finished_at`` (Plan 310-C observability columns).  Dashboard
  queries that rely on ``finished_at IS NOT NULL`` see every job.
- **One preemption-safety story** — the heartbeat + worker-side
  preemption check eliminate the duplicate-processing risk that the
  safety poller's stale-recovery sweep introduced (PR #998 review).

Concurrency model per ``run_job`` invocation:

- Two SQLModel sessions: ``job_session`` for the
  ``DataIngestionJob`` row's lifecycle, ``data_session`` for the
  handler's domain writes.  Separate so a handler ``rollback`` does
  not roll back the FINISHED+ERROR state-write the runner makes
  afterward.
- One per-job heartbeat task that wakes every
  ``STALE_JOB_TIMEOUT_MINUTES / 4`` and refreshes ``locked_at`` via
  its OWN session.  Cancelled in ``finally`` regardless of outcome
  (handler success, handler raise, preemption).
"""

import asyncio
from typing import Optional
from uuid import uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._background import fire_and_forget
from app.tasks._pod_id import POD_ID
from app.tasks.registry import get_handler

logger = get_logger(__name__)


async def run_job(job_id: int) -> None:
    """Dispatch a job through its registered handler.

    Single entry point used by:
      - HTTP endpoints (``fire_and_forget(run_job(id))`` after creating a job)
      - ``chain_job`` (parent handler chains a child)
      - the safety poller (orphan recovery)

    Lifecycle:

      1. Open job_session + data_session.
      2. Resolve job → reject if missing or ``job_type IS NULL``.
      3. ``claim_job`` (atomic RUNNING + attempts++ + ``started_at``).
         Returns False if the job was already claimed / finished /
         out of retries — in which case run_job is a silent no-op.
      4. Spawn heartbeat task (refreshes ``locked_at`` periodically).
      5. Look up handler from registry → execute it.
      6. Pre-commit preemption check: re-read the row; if
         ``locked_by`` no longer equals our pod, roll back the
         data_session and exit without state-changing the job (the
         new owner will).
      7. Commit data_session, update_ingestion_job to
         FINISHED+SUCCESS (or FINISHED+ERROR on handler raise).
      8. ``update_ingestion_job`` with state=FINISHED auto-stamps
         ``finished_at`` (Plan 310-C observability), so the dashboard
         duration query (finished_at - started_at) closes cleanly.
      9. Cancel heartbeat task in ``finally``.

    Errors raised by the handler are caught and persisted as
    FINISHED+ERROR.  Errors raised by the runner itself (claim
    contention, preemption) are logged and the job state is left for
    the next claimer.
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        repo = DataIngestionRepository(job_session)

        job = await repo.get_job_by_id(job_id)
        if job is None:
            logger.error(f"run_job: job {job_id} not found")
            return
        if job.job_type is None:
            logger.error(
                f"run_job: job {job_id} has no job_type — refusing to dispatch"
            )
            return

        # Capture job_type while it's narrowed to ``str`` by the
        # check above; the post-claim re-fetch widens it back to
        # ``Optional[str]`` (claim_job never touches job_type, so this
        # is a type-narrowing convenience, not a behavior change).
        job_type: str = job.job_type

        if not await repo.claim_job(job_id, POD_ID):
            # Another pod beat us, attempts exhausted, or the row is
            # already FINISHED.  Either way: not ours to run.
            return

        # ``claim_job`` ran a raw SQL UPDATE (state=RUNNING, attempts++,
        # locked_by, locked_at, and — via the func.coalesce from PR #1026
        # — started_at).  The in-memory ``job`` instance from the pre-claim
        # ``get_job_by_id`` still reflects the OLD row, so re-fetch to
        # hand handlers the authoritative post-claim state (state, attempts,
        # locked_by, started_at).  ``get_job_by_id`` already calls refresh.
        job = await repo.get_job_by_id(job_id)
        if job is None:
            # Race: claimed but row vanished before the re-read.  Treat
            # as preempted and exit; no state to write since there's no
            # row to write to.
            logger.warning(f"run_job: job {job_id} disappeared after claim — exiting")
            return

        # Plain ``asyncio.create_task`` (not ``fire_and_forget``): the
        # local ``heartbeat_task`` ref keeps the task alive for the
        # lifetime of this function, and we cancel + await it in the
        # ``finally`` block so the cancellation is observed cleanly.
        # Routing through ``fire_and_forget`` would trip its deliberate
        # cancellation-WARNING (kept loud for diagnosing the 310-B
        # incident) on every successful run, drowning out genuine
        # cancellations.
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(job_id),
            name=f"heartbeat-{job_id}",
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

            # Preemption check covers BOTH success and error paths: if a
            # stale-lock sweep recovered this row mid-handler, a different
            # pod may now own it.  Either way, our writes — successful or
            # error — must NOT race with the new owner's run.  Roll back
            # data and skip the state update; the new owner will close out.
            current = await repo.get_job_by_id(job_id)
            if current is None or current.locked_by != POD_ID:
                logger.warning(
                    f"run_job: job {job_id} preempted "
                    f"(locked_by={current and current.locked_by!r}); "
                    "rolling back data writes and exiting without "
                    "updating job state"
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
            )
            await job_session.commit()
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                # Expected — we cancelled it ourselves.
                pass


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
    """Create a child job and fire it through ``run_job``.

    Inherits the parent's ``pipeline_id`` (or generates a fresh UUID
    if the parent has none yet — the first chain on an ad-hoc run
    starts the pipeline).  The child is created NOT_STARTED with
    ``run_after=None`` (NULL means "runnable immediately"; the
    safety poller's claim WHERE treats NULL as eligible, so it can
    pick the row up if this pod crashes between the commit and the
    ``fire_and_forget``).

    Defaults match the most common case (an ``emission_recalc``
    child of an ingest parent: same module, scoped to a single det,
    DATA_ENTRIES target, computed source).  ``module_type_id`` and
    ``year`` inherit from the parent when the caller passes ``None``.
    ``data_entry_type_id`` does NOT inherit by design: a multi-det
    parent (e.g. a FACTORS ingest spanning several dets) fans out to
    one child per det, so the caller must always pass the specific
    child det.  Callers override the rest as they need.

    Returns the child's ``id``.  Persists the parent's
    ``pipeline_id`` if it had to generate one — without that, a
    pod-crash-then-recovery-claim of the parent would generate a
    different UUID and the child would be orphaned from the parent's
    run.
    """
    repo = DataIngestionRepository(session)

    pipeline_id = parent.pipeline_id
    if pipeline_id is None:
        pipeline_id = uuid4()
        parent.pipeline_id = pipeline_id
        session.add(parent)
        await session.commit()

    child = DataIngestionJob(
        job_type=job_type,
        module_type_id=(
            module_type_id if module_type_id is not None else parent.module_type_id
        ),
        data_entry_type_id=data_entry_type_id,
        year=year if year is not None else parent.year,
        target_type=target_type,
        ingestion_method=ingestion_method,
        entity_type=entity_type,
        state=IngestionState.NOT_STARTED,
        is_current=False,
        pipeline_id=pipeline_id,
        # ``None`` means "runnable immediately" — claim_job's WHERE
        # treats NULL run_after as eligible.  Matches the existing
        # ingestion_tasks.py recalc-job creation pattern.
        run_after=None,
        meta={"config": config or {}, "parent_job_id": parent.id},
    )
    created = await repo.create_ingestion_job(child)
    await session.commit()

    if created.id is None:
        # Defensive: create_ingestion_job should always return a
        # row with id set after commit.  If it ever doesn't, the
        # safety poller will pick up the row anyway via run_after.
        logger.error(
            f"chain_job: child {job_type!r} of parent {parent.id} "
            "was created without an id — relying on poller for dispatch"
        )
        return -1

    fire_and_forget(run_job(created.id), name=f"run_job-{created.id}")
    return created.id


async def _heartbeat_loop(job_id: int) -> None:
    """Refresh ``locked_at`` on the active job until cancelled.

    Wake every ``STALE_JOB_TIMEOUT_MINUTES / 4`` (default: every
    15 min for a 60 min timeout) and call ``repo.heartbeat``.  If
    the heartbeat returns 0 rows updated, our lock has been preempted
    — exit the loop so the runner's preemption check can take over
    on its next pass.

    Each tick uses a fresh session: heartbeats fire concurrently
    with the handler's session, so sharing would deadlock or
    serialize on the underlying connection.
    """
    settings = get_settings()
    interval_seconds = max(1.0, settings.STALE_JOB_TIMEOUT_MINUTES * 60 / 4)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with SessionLocal() as session:
                repo = DataIngestionRepository(session)
                updated = await repo.heartbeat(job_id, POD_ID)
                if updated == 0:
                    logger.warning(
                        f"_heartbeat_loop: lost lock on job {job_id} "
                        "(preempted or state moved out of RUNNING) — "
                        "stopping heartbeat"
                    )
                    return
        except asyncio.CancelledError:
            # Normal shutdown path — the runner cancels us in its
            # ``finally`` block.  Re-raise so asyncio sees the
            # cancellation cleanly.
            raise
        except Exception as exc:
            # Don't let a transient DB hiccup kill the heartbeat;
            # log and try again next interval.
            logger.warning(f"_heartbeat_loop: heartbeat for job {job_id} failed: {exc}")
