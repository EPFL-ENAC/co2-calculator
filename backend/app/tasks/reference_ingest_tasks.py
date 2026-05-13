"""Reference-data ingest handler.

Registered under ``job_type='reference_ingest'`` — a sibling of
``csv_ingest`` / ``factor_ingest`` that skips the emission-recalc
fan-out.  Reference data (locations, building rooms) writes to global,
year-agnostic tables that no factor or emission row references, so the
fan-out chain is both unnecessary and incorrect.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import DataIngestionJob, IngestionResult
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks.registry import register

logger = get_logger(__name__)


@register("reference_ingest")
async def reference_ingest_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Run the reference-data provider with no post-success chaining."""
    if job.id is None:
        raise ValueError("reference_ingest handler: job has no id")

    job_meta = job.meta or {}
    provider_name = job_meta.get("provider_name")
    if not provider_name:
        raise ValueError(
            f"reference_ingest: job {job.id} missing meta.provider_name "
            "(endpoint must set it when creating the job)"
        )

    provider_class = ProviderFactory.get_provider_class(provider_name)
    if provider_class is None:
        raise ValueError(
            f"reference_ingest: provider class {provider_name!r} not found "
            f"(job {job.id})"
        )

    job_config = job_meta.get("config") or {}
    provider = provider_class(
        config={**job.__dict__, **job_config, "job_id": job.id},
        user=job.user if hasattr(job, "user") else None,
        job_session=job_session,
        data_session=data_session,
    )
    provider.defer_finalize = True
    if hasattr(provider, "set_job_id"):
        await provider.set_job_id(job.id)

    filters = job_meta.get("filters") or {}
    result = await provider.ingest(filters)
    data = result.get("data", {}) or {}
    ingestion_result = data.get("result", IngestionResult.SUCCESS)
    return {
        "status_message": result.get("status_message", "Success"),
        "result": ingestion_result,
        **data,
    }


__all__ = ["reference_ingest_handler"]
