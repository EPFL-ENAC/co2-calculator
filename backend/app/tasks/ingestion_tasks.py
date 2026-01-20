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
    """
    async with SessionLocal() as db:
        # retrieve job from db, then init provider!
        job = await DataIngestionRepository(db).get_job_by_id(job_id)
        if not job:
            logger.error(f"Job ID {job_id} not found.")
            return
        provider_class = ProviderFactory.get_provider_class(provider_class_name)
        if not provider_class:
            logger.error(f"Provider class '{provider_class_name}' not found.")
            return
        provider = provider_class(
            config={**job.__dict__, "job_id": job.id},
            user=job.user
            if hasattr(job, "user")
            else None,  # User info can be added if needed
        )
        # Use job.meta as filters if present, else fallback to provided filters
        filters_to_use = (
            job.meta if hasattr(job, "meta") and job.meta else (filters or {})
        )
        if not job.id:
            logger.error("Job ID is missing in the job record.")
            return
        # Ensure job_id is set
        await provider.set_job_id(job.id)
        # Run ingestion
        result = await provider.ingest(filters_to_use)

        # Update module's last_sync_status
        await provider._update_job(
            status_code=result["status_code"],
            status_message=result["message"],
            extra_metadata=result.get("data", {}),
        )

        logger.info("Sync completed successfully ")


# @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
# add self to make it celery compatible
def run_ingestion(provider_name: str, job_id: int, filters: dict):
    """almost celery compatible sync wrapper for run_sync_task"""
    try:
        asyncio.run(run_sync_task(provider_name, job_id, filters))
    except Exception as e:
        logger.error(f"Sync failed for job ID {job_id}: {str(e)}")

        provider_class = ProviderFactory.get_provider_class(provider_name)
        if not provider_class:
            raise ValueError(f"Provider class '{provider_name}' not found")

        provider = provider_class(config={}, user=None)

        # Use asyncio.run here because _update_job is async
        asyncio.run(
            provider._update_job(
                status_code=IngestionStatus.FAILED,
                status_message=str(e),
                extra_metadata={"message": "background_tasks: run_sync_task failure"},
            )
        )

        raise  # propagate exception for Celery retry
