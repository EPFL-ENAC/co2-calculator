"""In-process safety poller for orphaned jobs (Plan 310A + 310C cutover).

Plan 310-C cutover: dispatch goes through the unified
``app.tasks.runner.run_job``.  The poller's role is unchanged —
detect orphaned NOT_STARTED jobs (typically created by an HTTP endpoint
that fired ``run_job`` and then crashed before the runner claimed) and
re-fire them.  Jobs without a ``job_type`` (legacy in-flight rows
created pre-Plan-C) are excluded from the SELECT so they don't get
funneled through a runner that has no handler for them.
"""

import asyncio

from sqlalchemy import func, or_
from sqlmodel import col, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import DataIngestionJob, IngestionState
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID
from app.tasks.runner import run_job

logger = get_logger(__name__)


def schedule_job(job: DataIngestionJob, pod_id: str) -> None:
    """Fire-and-forget: dispatch a job, logging any unhandled exception.

    Routes through ``fire_and_forget`` so the Task is held in a strong-ref
    set and survives GC (Python 3.11+ asyncio holds only weak references
    to running tasks).  Bare ``asyncio.create_task`` here had the same
    hazard that bit recalc enqueuing in 310-B — orphan recovery would
    silently fail to dispatch.
    """
    if job.id is None:
        return
    from app.tasks._background import fire_and_forget

    fire_and_forget(dispatch_job(job, pod_id), name=f"dispatch-{job.id}")


async def dispatch_job(job: DataIngestionJob, pod_id: str) -> None:
    """Dispatch a single job through the unified runner.

    Plan 310-C cutover: every job_type funnels through ``run_job(job_id)``
    which handles claim / heartbeat / preempt-check / state-write
    uniformly.  ``pod_id`` is no longer needed at this layer (the runner
    reads ``POD_ID`` itself), but the parameter is kept for compatibility
    with the existing ``schedule_job`` signature and tests.
    """
    jid = job.id
    if jid is None:
        logger.warning("Job has no ID — skipping")
        return
    await run_job(jid)


def _pending_runner_jobs_query(limit: int = 10):
    """Pending-jobs query for the runner cutover.

    Same predicates as ``DataIngestionRepository._pending_jobs_query``,
    plus a ``job_type IS NOT NULL`` filter so legacy in-flight jobs
    (created pre-Plan-C with a NULL ``job_type``) don't get dispatched
    through a runner that has no registered handler for them.  The
    runner itself defends in depth (refuses to dispatch a NULL row),
    but filtering at SELECT time avoids per-iteration noise in the logs.
    """
    return (
        select(DataIngestionJob)
        .where(
            col(DataIngestionJob.state) == IngestionState.NOT_STARTED,
            col(DataIngestionJob.job_type).is_not(None),
            or_(
                col(DataIngestionJob.run_after).is_(None),
                col(DataIngestionJob.run_after) <= func.now(),
            ),
            col(DataIngestionJob.locked_by).is_(None),
            col(DataIngestionJob.attempts) < col(DataIngestionJob.max_attempts),
        )
        .with_for_update(skip_locked=True)
        .limit(limit)
    )


async def poll_pending_jobs() -> None:
    """Pick up jobs that were created but never scheduled (e.g. crashed pod).

    Two sweeps per iteration:

    1. ``sweep_stuck_running_jobs`` — auto-recovery for jobs stuck in
       RUNNING past the stale-timeout window (a pod crashed mid-execution).
       Recoverable rows go back to NOT_STARTED; rows out of retries are
       moved to FINISHED+ERROR so operators see them.

    2. NOT_STARTED dispatch sweep — pick up rows the endpoint fired but
       the in-process Task never reached (pod crashed in the gap between
       commit and ``fire_and_forget``).  Filtered to ``job_type IS NOT
       NULL`` so legacy rows don't trip on the missing handler path.
    """
    settings = get_settings()
    while True:
        try:
            async with SessionLocal() as session:
                repo = DataIngestionRepository(session)

                # Sweep 1: pod-crash auto-recovery.
                recovered, abandoned = await repo.sweep_stuck_running_jobs(
                    settings.STALE_JOB_TIMEOUT_MINUTES
                )
                if recovered:
                    logger.warning(
                        f"Poller: auto-recovered {recovered} stuck RUNNING job(s) "
                        "(state→NOT_STARTED, attempts preserved for max-retry guard)"
                    )
                if abandoned:
                    logger.error(
                        f"Poller: abandoned {abandoned} stuck RUNNING job(s) — "
                        "exhausted max_attempts retries, marked FINISHED+ERROR"
                    )

                # Sweep 2: dispatch NOT_STARTED jobs through the unified runner.
                stmt = _pending_runner_jobs_query(settings.POLLER_BATCH_LIMIT)
                jobs = (await session.execute(stmt)).scalars().all()
                for job in jobs:
                    logger.info(f"Poller: scheduling orphaned job {job.id}")
                    schedule_job(job, POD_ID)
        except Exception as exc:
            logger.warning(f"Poller iteration failed: {exc}", exc_info=True)
        await asyncio.sleep(settings.POLLER_INTERVAL_SECONDS)


# Safety poller task is managed in main.py lifespan context manager,
# not via deprecated on_event.
