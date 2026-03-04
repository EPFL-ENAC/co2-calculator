import asyncio
import logging
from typing import Optional

from app.db import SessionLocal
from app.models.data_ingestion import IngestionStatus
from app.repositories.data_ingestion import DataIngestionRepository
from app.services.data_ingestion.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)


async def run_sync_task(
    provider_class_name: str,
    job_id: int,
    filters: Optional[dict] = None,
):
    """
    Async helper function to run ingestion with database operations.
    Uses two separate sessions:
    - job_session: For job status updates (commits immediately, visible to SSE)
    - data_session: For data operations (single atomic commit at the end)
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        # Retrieve job from db
        job = await DataIngestionRepository(job_session).get_job_by_id(job_id)
        if not job:
            logger.error(f"Job ID {job_id} not found.")
            return
        provider_class = ProviderFactory.get_provider_class(provider_class_name)
        if not provider_class:
            logger.error(f"Provider class '{provider_class_name}' not found.")
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
            # Update final job status
            await provider._update_job(
                status_code=result["status_code"],
                status_message=result["status_message"],
                extra_metadata=result.get("data", {}),
            )
            logger.info("Sync completed successfully ")
        except Exception as e:
            logger.error(f"Sync failed for job ID {job.id}: {str(e)}")
            # Explicitly rollback data session to ensure no partial writes
            await data_session.rollback()
            # Job updates are preserved because they commit immediately
            await provider._update_job(
                status_code=IngestionStatus.FAILED,
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
