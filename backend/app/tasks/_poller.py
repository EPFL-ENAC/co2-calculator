"""In-process safety poller for orphaned jobs (Plan 310A)."""

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import DataIngestionJob
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 10


def schedule_job(job: DataIngestionJob, pod_id: str) -> None:
    """Fire-and-forget: dispatch a job, logging any unhandled exception.

    Routes through ``fire_and_forget`` so the Task is held in a strong-ref
    set and survives GC (Python 3.11+ asyncio holds only weak references
    to running tasks).  The earlier bare ``asyncio.create_task`` here had
    the same hazard that bit recalc enqueuing — orphaned-job recovery
    would silently fail to dispatch.
    """
    if job.id is None:
        return
    from app.tasks._background import fire_and_forget

    fire_and_forget(dispatch_job(job, pod_id), name=f"dispatch-{job.id}")


async def dispatch_job(job: DataIngestionJob, pod_id: str) -> None:
    """Dispatch a single job to the appropriate handler.

    The poller predates the unified runner (Plan C).  It re-enters the
    existing task functions that already call ``claim_job``.  Plan C will
    consolidate this into a generic ``run_job(job_id)`` dispatcher.
    """
    jid = job.id
    if jid is None:
        logger.warning("Job has no ID — skipping")
        return

    job_type = job.job_type
    meta = job.meta or {}

    if job_type in ("csv_ingest", "api_ingest", None):
        # Legacy ingestion jobs — determine provider from stored meta
        provider_name = meta.get("provider_name")
        if not provider_name:
            logger.warning(f"No provider_name in meta for job {jid} — skipping")
            return
        from app.tasks.ingestion_tasks import run_sync_task as _run_sync_task

        await _run_sync_task(
            provider_class_name=provider_name,
            job_id=jid,
            filters=meta.get("filters") or {},
        )
    elif job_type == "emission_recalc":
        from app.tasks.emission_recalculation_tasks import (
            run_recalculation_task as _run_recalc,
        )

        mid = job.module_type_id
        det_id = job.data_entry_type_id
        yr = job.year
        if mid is None or det_id is None or yr is None:
            logger.warning(f"Missing fields for recalc job {jid} — skipping")
            return
        await _run_recalc(
            module_type_id=mid,
            data_entry_type_id=det_id,
            year=yr,
            job_id=jid,
        )
    elif job_type == "module_emission_recalc":
        from app.tasks.emission_recalculation_tasks import (
            run_module_recalculation_task as _run_module_recalc,
        )

        mid = job.module_type_id
        yr = job.year
        det_ids = (meta.get("config") or {}).get("data_entry_type_ids")
        if mid is None or yr is None or not det_ids:
            logger.warning(f"Missing fields for module recalc job {jid} — skipping")
            return
        await _run_module_recalc(
            module_type_id=mid,
            data_entry_type_ids=det_ids,
            year=yr,
            job_id=jid,
        )
    else:
        logger.warning(f"Unknown job_type '{job_type}' for job {jid} — skipping")


async def poll_pending_jobs() -> None:
    """Pick up jobs that were created but never scheduled (e.g. crashed pod).

    Two sweeps per iteration:

    1. ``sweep_stuck_running_jobs`` — auto-recovery for jobs stuck in
       RUNNING past the stale-timeout window (a pod crashed mid-execution).
       Recoverable rows go back to NOT_STARTED; rows out of retries are
       moved to FINISHED+ERROR so operators see them.  Without this, the
       only way to recover from a pod crash was the manual
       ``POST /sync/jobs/{id}/recover`` endpoint and the 30-min stale
       window.

    2. The original NOT_STARTED dispatch sweep.
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

                # Sweep 2: dispatch NOT_STARTED jobs (existing Plan 310A behaviour).
                stmt = repo._pending_jobs_query(10)
                jobs = (await session.execute(stmt)).scalars().all()
                for job in jobs:
                    logger.info(f"Poller: scheduling orphaned job {job.id}")
                    schedule_job(job, POD_ID)
        except Exception as exc:
            logger.warning(f"Poller iteration failed: {exc}", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# Safety poller task is managed in main.py lifespan context manager,
# not via deprecated on_event.
