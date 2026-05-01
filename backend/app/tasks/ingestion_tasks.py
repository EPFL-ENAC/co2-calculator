"""Background tasks for data ingestion."""

import asyncio
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

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
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks._pod_id import POD_ID

logger = get_logger(__name__)


async def run_sync_task(
    provider_class_name: str,
    job_id: int,
    filters: Optional[dict] = None,
) -> None:
    """
    Async helper function to run ingestion with database operations.
    Uses two separate sessions:
    - job_session: For job status updates (commits immediately, visible to SSE)
    - data_session: For data operations (single atomic commit at the end)
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        job_repo = DataIngestionRepository(job_session)

        # Validate cheap things BEFORE acquiring the lock — otherwise a
        # bogus provider name leaves the job stuck in RUNNING until the
        # 30-minute stale-recovery window expires.  claim_job itself
        # handles the "job not found" case (returns False), so we don't
        # need a separate existence check here.
        provider_class = ProviderFactory.get_provider_class(provider_class_name)
        if not provider_class:
            logger.error(f"Provider class '{provider_class_name}' not found.")
            return

        claimed = await job_repo.claim_job(job_id, POD_ID)
        if not claimed:
            logger.info(f"Job {job_id} already claimed or not eligible — skipping")
            return

        # Re-fetch the now-RUNNING row for use in provider construction.
        job = await job_repo.get_job_by_id(job_id)
        if not job:
            logger.error(f"Job ID {job_id} not found after claim.")
            return

        # Extract config from job.meta if available, otherwise use job.__dict__
        job_config = {}
        if hasattr(job, "meta") and job.meta and "config" in job.meta:
            job_config = job.meta["config"]

        provider = provider_class(
            config={**job.__dict__, **job_config, "job_id": job.id},
            user=job.user if hasattr(job, "user") else None,
            job_session=job_session,  # For status updates (frequent commits)
            data_session=data_session,  # For data operations (atomic)
        )
        if hasattr(provider, "set_job_id") and job is not None and job.id is not None:
            await provider.set_job_id(job.id)
        # Use job.meta as filters if present, else fallback to provided filters
        filters_to_use = (
            job.meta if hasattr(job, "meta") and job.meta else (filters or {})
        )
        if not job.id:
            logger.error("Job ID is missing in the job record.")
            return
        # Run ingestion
        try:
            result = await provider.ingest(filters_to_use)
            # Commit the data transaction atomically (all or nothing)
            await data_session.commit()
            # Extract the result from ingest() - provider already computed it
            # in _finalize_and_commit() based on rows_processed/rows_skipped
            ingestion_result = result.get("data", {}).get(
                "result", IngestionResult.SUCCESS
            )

            # Plan 310B Part 4 — fan out emission recalculation jobs after a
            # successful FACTORS sync.  Operators previously had to trigger
            # this manually and forgot.  Children inherit the parent's
            # pipeline_id so dashboards can group the chain.
            if (
                job.target_type == TargetType.FACTORS
                and ingestion_result != IngestionResult.ERROR
            ):
                pipeline_id = job.pipeline_id or uuid4()
                await _enqueue_stale_recalculations(
                    job_session,
                    parent_job_id=job.id,
                    module_type_id=job.module_type_id,
                    data_entry_type_id=job.data_entry_type_id,
                    year=job.year,
                    pipeline_id=pipeline_id,
                )

            # Update final job status with the computed result
            await provider._update_job(
                state=IngestionState.FINISHED,
                result=ingestion_result,
                status_message=result.get("status_message", "Success"),
                extra_metadata=result.get("data", {}),
            )
            logger.info("Sync completed successfully ")
        except Exception as e:
            logger.error(f"Sync failed for job ID {job.id}: {str(e)}")
            # Explicitly rollback data session to ensure no partial writes
            await data_session.rollback()
            # Job updates are preserved because they commit immediately
            await provider._update_job(
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                status_message=str(e),
                extra_metadata={"message": "run_sync_task failure"},
            )
            raise  # propagate exception


# @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
# add self to make it celery compatible
def run_ingestion(provider_name: str, job_id: int, filters: dict):
    """almost celery compatible sync wrapper for run_sync_task"""
    try:
        asyncio.run(run_sync_task(provider_name, job_id, filters))
    except Exception as e:
        logger.error(f"Sync failed for job ID {job_id}: {str(e)}")
        # Error already logged and job status updated in run_sync_task
        raise  # propagate exception for Celery retry


async def _enqueue_stale_recalculations(
    session: AsyncSession,
    *,
    parent_job_id: Optional[int],
    module_type_id: Optional[int],
    data_entry_type_id: Optional[int],
    year: Optional[int],
    pipeline_id: UUID,
) -> None:
    """Fan out one ``emission_recalc`` job per stale ``(module, det)`` combo
    after a successful factor ingest.

    Filters ``get_recalculation_status_by_year`` by the parent job's scope
    (module/det if set; otherwise all combos that need recalc).  Each child
    inherits ``pipeline_id`` from the parent so dashboards can group runs.

    Children are fired in-process via ``asyncio.create_task``.  If the pod
    crashes between enqueue and dispatch, the safety poller (Plan 310A)
    picks them up via ``state=NOT_STARTED AND run_after<=now()``.

    This helper is intentionally local to ingestion_tasks.py — Plan C
    generalises it as ``chain_job(parent, child)`` once the handler
    registry lands.
    """
    if year is None:
        logger.warning("Cannot enqueue recalculations without a year on the parent job")
        return

    # Late import to avoid a circular import via app.workflows.
    from app.tasks.emission_recalculation_tasks import run_recalculation_task

    repo = DataIngestionRepository(session)
    rows = await repo.get_recalculation_status_by_year(year)
    targets = [
        r
        for r in rows
        if r["needs_recalculation"]
        and (module_type_id is None or r["module_type_id"] == module_type_id)
        and (
            data_entry_type_id is None or r["data_entry_type_id"] == data_entry_type_id
        )
    ]

    if not targets:
        logger.info(f"No stale (module, det) combos to recalculate for year={year}")
        return

    for row in targets:
        new_job = DataIngestionJob(
            job_type="emission_recalc",
            module_type_id=row["module_type_id"],
            data_entry_type_id=row["data_entry_type_id"],
            year=year,
            ingestion_method=IngestionMethod.computed,
            target_type=TargetType.DATA_ENTRIES,
            entity_type=EntityType.MODULE_PER_YEAR,
            state=IngestionState.NOT_STARTED,
            pipeline_id=pipeline_id,
            # run_after=None means runnable immediately; claim_job's WHERE
            # treats NULL run_after as eligible.
            run_after=None,
            meta={
                "config": {
                    "year": year,
                    "data_entry_type_id": row["data_entry_type_id"],
                    "module_type_id": row["module_type_id"],
                    "parent_job_id": parent_job_id,
                }
            },
        )
        created = await repo.create_ingestion_job(new_job)
        await session.commit()
        if created.id is None:
            logger.error(
                "Failed to create child recalc job for "
                f"(module={row['module_type_id']}, det={row['data_entry_type_id']})"
            )
            continue
        asyncio.create_task(
            run_recalculation_task(
                row["module_type_id"],
                row["data_entry_type_id"],
                year,
                created.id,
            )
        )
        logger.info(
            f"Enqueued recalc job {created.id} for module={row['module_type_id']} "
            f"det={row['data_entry_type_id']} year={year} pipeline={pipeline_id}"
        )
