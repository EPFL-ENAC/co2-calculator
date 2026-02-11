import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    FactorType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks.ingestion_tasks import run_ingestion

router = APIRouter()


class SyncRequestConfig(BaseModel):
    carbon_report_module_id: Optional[int] = None
    data_entry_type_id: Optional[int] = None
    factor_variant: Optional[str] = None


class SyncRequest(BaseModel):
    ingestion_method: IngestionMethod
    target_type: TargetType
    year: Optional[int] = None
    filters: Optional[dict] = {}
    config: Optional[SyncRequestConfig] = None
    file_path: Optional[str] = None


class SyncStatusResponse(BaseModel):
    job_id: int
    status: str
    status_code: IngestionStatus
    message: str
    progress: Optional[dict] = None


class SyncJobResponse(BaseModel):
    job_id: int
    module_type_id: Optional[int] = None
    year: Optional[int] = None
    ingestion_method: IngestionMethod
    target_type: Optional[TargetType] = None
    status: IngestionStatus
    status_message: Optional[str] = None
    meta: Optional[dict] = None


@router.post("/data-entries/{module_type_id}", response_model=SyncStatusResponse)
async def sync_module_data_entries(
    module_type_id: ModuleTypeEnum,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    example of request body for module_type_year:
    {
        "ingestion_method": "csv",
        "target_type": 0,
        "year": 2025,
        "carbon_report_module_id": 123,
        "filters": {},
        "config": {},
        "file_path": "tmp/1770129151949277/seed_equipment_data.csv"
    }

    example of request body for carbon_report_module_id only:
    {
        "ingestion_method": "api",
        "target_type": 0,
        "carbon_report_module_id": 123,
        "filters": {},
        "config": {}
    }
    """
    if request.target_type == TargetType.FACTORS and request.year is None:
        raise HTTPException(
            status_code=400,
            detail="year is required for factor CSV ingestion",
        )

    # Prepare config with file_path and carbon_report_module_id if provided
    config = request.config.model_dump() if request.config else {}
    if request.file_path:
        config["file_path"] = request.file_path

    # Determine entity_type early based on carbon_report_module_id presence
    entity_type = (
        EntityType.MODULE_UNIT_SPECIFIC
        if config.get("carbon_report_module_id") is not None
        else EntityType.MODULE_PER_YEAR
    )
    config["entity_type"] = entity_type.value
    config["year"] = request.year

    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum(module_type_id),
        ingestion_method=request.ingestion_method,
        target_type=request.target_type,
        config=config,
        user=current_user,
        job_session=db,  # Use same session for both during validation
        data_session=db,  # Actual work happens in background task
    )

    if not provider:
        raise HTTPException(
            status_code=400,
            detail=f"""Provider '{request.ingestion_method}'
                not supported for module '{module_type_id}'""",
        )

    if not await provider.validate_connection():
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to {request.ingestion_method}"
        )

    factor_type_id = getattr(request, "factor_type_id", None)
    if factor_type_id is not None:
        factor_type_id = FactorType(factor_type_id)
    data_entry_type_id = config.get("data_entry_type_id") or getattr(
        request, "data_entry_type_id", None
    )
    job_id = await provider.create_job(
        module_type_id=ModuleTypeEnum(module_type_id),
        data_entry_type_id=data_entry_type_id,
        entity_type=entity_type,
        year=request.year,
        ingestion_method=request.ingestion_method,
        target_type=request.target_type,
        factor_type_id=factor_type_id,
        config=config,
        db=db,
    )
    # Commit job creation to database
    await db.commit()

    # Schedule the ingestion task in the background
    # NOTE: file_path validation happens in provider.__init__()
    #   via _validate_file_path()
    # to prevent directory traversal attacks (e.g., /../../../etc/passwd)
    background_tasks.add_task(
        run_ingestion,
        provider_name=provider.__class__.__name__,
        job_id=job_id,
        filters=request.filters or {},
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "status_code": IngestionStatus.IN_PROGRESS,
        "message": f"""Sync initiated using {request.ingestion_method}""",
        "progress": None,
    }


@router.post("/factors/{module_id}/{factor_type_id}", response_model=SyncStatusResponse)
async def sync_module_factors(
    module_id: int,
    factor_type_id: int,
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
):
    # Implementation similar to sync_module_data_entries,
    # but tailored for factor synchronization.
    pass


@router.get("/jobs/by-status", response_model=list[DataIngestionJob])
async def get_jobs_by_status(
    filter_type: str = "completed",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list:
    """
    Get jobs filtered by status.

    Args:
        filter_type: "active" for in-progress jobs, "completed" for finished jobs
    """
    if filter_type.lower() == "active":
        jobs = await DataIngestionRepository(db).get_active_jobs()
    else:
        jobs = await DataIngestionRepository(db).get_completed_jobs()
    return jobs


# SSE endpoint to stream job updates - MUST be before /jobs/{job_id}
@router.get("/jobs/stream")
async def job_stream(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events endpoint to stream job updates in real-time.
    Polls the database for job status changes and sends updates to the client.

    Each update includes:
    - job_id: unique job identifier
    - module_type_id: the module type for this job
    - target_type: data_entries or factors
    - year: year for the job
    - status: current ingestion status
    - status_message: detailed message
    - updated_at: last update timestamp
    """

    async def event_generator():
        # Track last seen job IDs and statuses
        last_jobs = {}

        while True:
            # Fetch all active jobs (not completed or failed)
            # jobs = await DataIngestionRepository(db).get_active_jobs()
            jobs = await DataIngestionRepository(db).get_completed_jobs()

            # Compare with last state
            for job in jobs:
                job_key = f"{job.id}"
                current_status = {
                    "job_id": job.id,
                    "module_type_id": job.module_type_id,
                    "target_type": job.target_type,
                    "year": job.year,
                    "status": job.status,
                    "status_message": job.status_message,
                    "updated_at": job.updated_at.isoformat()
                    if job.updated_at
                    else None,
                }

                # Send update if status changed
                if job_key not in last_jobs or last_jobs[job_key] != current_status:
                    yield f"data: {json.dumps(current_status)}\n\n"
                    last_jobs[job_key] = current_status

            # Remove jobs that no longer exist
            existing_job_ids = {f"{job.id}" for job in jobs}
            last_jobs = {k: v for k, v in last_jobs.items() if k in existing_job_ids}

            # Wait before next poll (adjust interval as needed)
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# SSE endpoint to stream a single job by ID - MUST be before /jobs/{job_id}
@router.get("/jobs/{job_id}/stream")
async def job_stream_by_id(
    job_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events endpoint to stream a single job update in real-time.
    Polls the database for status changes and sends updates to the client.
    Stream ends when the job is completed or failed.
    """

    async def event_generator():
        last_status = None
        last_message = None
        polls_after_completion = 0

        while True:
            job = await DataIngestionRepository(db).get_job_by_id(job_id)
            if not job:
                not_found_status = {
                    "job_id": job_id,
                    "status_message": "Job not found",
                }
                yield f"data: {json.dumps(not_found_status)}\n\n"
                break

            current_status = {
                "job_id": job.id,
                "module_type_id": job.module_type_id,
                "target_type": job.target_type,
                "year": job.year,
                "status": job.status,
                "status_message": job.status_message,
            }

            # Yield if either status OR message changed
            if last_status != current_status or last_message != job.status_message:
                yield f"data: {json.dumps(current_status)}\n\n"
                last_status = current_status
                last_message = job.status_message

            # If job is completed or failed...
            if job.status in {IngestionStatus.COMPLETED, IngestionStatus.FAILED}:
                polls_after_completion += 1
                if polls_after_completion >= 2:
                    # Send final completion message before closing stream
                    final_status = {**current_status, "stream_closed": True}
                    yield f"data: {json.dumps(final_status)}\n\n"
                    break

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
