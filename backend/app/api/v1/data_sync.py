import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.data_ingestion import (
    FactorType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.module_type import ALL_MODULE_TYPE_IDS, ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks.ingestion_tasks import run_ingestion

router = APIRouter()


class SyncRequest(BaseModel):
    ingestion_method: IngestionMethod
    target_type: TargetType
    year: int
    filters: Optional[dict] = {}
    config: Optional[dict] = {}


class SyncStatusResponse(BaseModel):
    job_id: int
    status: str
    status_code: IngestionStatus
    message: str
    progress: Optional[dict] = None


class SyncJobResponse(BaseModel):
    job_id: int
    module_type_id: int
    year: int
    ingestion_method: IngestionMethod
    target_type: TargetType
    status: IngestionStatus
    status_message: Optional[str] = None
    meta: Optional[dict] = None


@router.post("/data-entries/{module_type_id}", response_model=SyncStatusResponse)
async def sync_module_data_entries(
    module_type_id: ModuleTypeEnum,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """
    example of request body:
    {
        "ingestion_method": "api",
        "target_type": 0,
        "year": 2023,
        "filters": {
            "filter_units": [1,3,5]
        },
    }
    """
    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum(module_type_id),
        ingestion_method=request.ingestion_method,
        target_type=request.target_type,
        config=request.config or {},
        user=current_user,
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
    job_id = await provider.create_job(
        module_type_id=ModuleTypeEnum(module_type_id),
        year=request.year,
        ingestion_method=request.ingestion_method,
        target_type=request.target_type,
        factor_type_id=factor_type_id,
    )
    # Enqueue Celery task instead of background_tasks
    # run_ingestion.delay(
    #     provider_name=provider.__class__.__name__,
    #     job_id=job_id,
    #     filters=request.filters,
    # )
    background_tasks.add_task(
        run_ingestion,
        provider_name=provider.__class__.__name__,
        job_id=job_id,
        filters=request.filters or {},
    )

    # TODO: return job status and status_code not custom message!
    #  get Job ?
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


# New endpoint to get all sync jobs for a specific year
@router.get("/jobs/year/{year}", response_model=dict)
async def get_sync_jobs_by_year(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    ## maybe pass by service?
    jobs = await DataIngestionRepository(db).get_jobs_by_year(year)

    # Initialize result structure with all module
    # types and both target types (0=data_entries, 1=factors)
    result = {}
    for module_type_id_iter in ALL_MODULE_TYPE_IDS:  # 1 to 7 inclusive
        result[module_type_id_iter.value] = {
            0: {"status": 0, "message": ""},  # data_entries default
            1: {"status": 0, "message": ""},  # factors default
        }

    # Update with actual job data
    for job in jobs:
        if (job.module_type_id is None) or (job.target_type is None):
            continue
        module_type_id = job.module_type_id
        target_type = job.target_type
        if module_type_id in result and target_type in result[module_type_id]:
            result[module_type_id][target_type] = {
                "status": job.status,
                "message": job.status_message or "",
            }

    return result


# SSE endpoint to stream job updates


@router.get("/jobs/stream")
async def job_stream(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Server-Sent Events endpoint to stream job updates in real-time.
    Polls the database for job status changes and sends updates to the client.
    """

    async def event_generator():
        # Track last seen job IDs and statuses
        last_jobs = {}

        while True:
            # Fetch all active jobs (not completed or failed)
            jobs = await DataIngestionRepository(db).get_active_jobs()

            # Compare with last state
            for job in jobs:
                job_key = f"{job.id}"
                current_status = {
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
