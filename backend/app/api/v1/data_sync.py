import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import is_permitted, require_permission
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    FactorType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks.emission_recalculation_tasks import (
    run_module_recalculation,
    run_recalculation,
)
from app.tasks.ingestion_tasks import run_ingestion
from app.tasks.unit_sync_tasks import SyncUnitRequest, sync_units_from_accred_task
from app.utils.request_context import extract_ip_address, extract_route_payload

router = APIRouter()


class SyncRequestConfig(BaseModel):
    carbon_report_module_id: Optional[int] = None
    data_entry_type_id: Optional[int] = None


class SyncRequest(BaseModel):
    ingestion_method: IngestionMethod
    target_type: TargetType
    year: Optional[int] = None
    filters: Optional[dict] = {}
    config: Optional[SyncRequestConfig] = None
    file_path: Optional[str] = None


class SyncStatusResponse(BaseModel):
    job_id: int
    state: IngestionState
    message: str
    progress: Optional[dict] = None


class SyncJobResponse(BaseModel):
    job_id: int
    module_type_id: Optional[int] = None
    data_entry_type_id: Optional[int] = None
    year: Optional[int] = None
    ingestion_method: IngestionMethod
    target_type: Optional[TargetType] = None
    status_message: Optional[str] = None
    meta: Optional[dict] = None
    state: Optional[IngestionState] = None
    result: Optional[IngestionResult] = None


class RecalculationStatus(BaseModel):
    """Per-(module_type_id, data_entry_type_id) recalculation status."""

    module_type_id: int
    data_entry_type_id: int
    year: int
    needs_recalculation: bool
    last_factor_job_id: Optional[int] = None
    last_factor_job_result: Optional[IngestionResult] = None
    last_recalculation_job_id: Optional[int] = None
    last_recalculation_job_result: Optional[IngestionResult] = None


class ModuleRecalculationStatus(BaseModel):
    """Per-module rollup — true if any data_entry_type needs recalculation."""

    module_type_id: int
    year: int
    needs_recalculation: bool
    data_entry_types: list[RecalculationStatus]


@router.post("/data-entries/{module_type_id}", response_model=SyncStatusResponse)
async def sync_module_data_entries(
    module_type_id: ModuleTypeEnum,
    syncRequest: SyncRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync data entries for a specific module.

    **Required Permission**: `backoffice.data_management.sync`

    Example of request body for module_type_year:
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
    has_permission = await is_permitted(
        current_user, "backoffice.data_management", "sync"
    ) or await is_permitted(current_user, "modules.*", "sync")
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permission denied: requires backoffice.data_management.sync "
                "or modules.* sync permission"
            ),
        )

    if syncRequest.target_type == TargetType.FACTORS and syncRequest.year is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year is required for factor CSV ingestion",
        )

    # Prepare config with file_path and carbon_report_module_id if provided
    config = syncRequest.config.model_dump() if syncRequest.config else {}
    if syncRequest.file_path:
        config["file_path"] = syncRequest.file_path

    # Determine entity_type early based on carbon_report_module_id presence
    entity_type = (
        EntityType.MODULE_UNIT_SPECIFIC
        if config.get("carbon_report_module_id") is not None
        else EntityType.MODULE_PER_YEAR
    )
    config["entity_type"] = entity_type.value
    config["year"] = syncRequest.year

    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum(module_type_id),
        ingestion_method=syncRequest.ingestion_method,
        target_type=syncRequest.target_type,
        config=config,
        user=current_user,
        job_session=db,  # Use same session for both during validation
        data_session=db,  # Actual work happens in background task
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"""Provider '{syncRequest.ingestion_method}'
                not supported for module '{module_type_id}'""",
        )

    if not await provider.validate_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to {syncRequest.ingestion_method}",
        )

    factor_type_id = getattr(syncRequest, "factor_type_id", None)
    if factor_type_id is not None:
        factor_type_id = FactorType(factor_type_id)
    data_entry_type_id = config.get("data_entry_type_id") or getattr(
        syncRequest, "data_entry_type_id", None
    )
    job_id = await provider.create_job(
        module_type_id=ModuleTypeEnum(module_type_id),
        data_entry_type_id=data_entry_type_id,
        entity_type=entity_type,
        year=syncRequest.year,
        ingestion_method=syncRequest.ingestion_method,
        target_type=syncRequest.target_type,
        factor_type_id=factor_type_id,
        config=config,
        db=db,
        request_context={
            "ip_address": extract_ip_address(request),
            "route_path": request.url.path,
            "route_payload": await extract_route_payload(request),
        },
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
        filters=syncRequest.filters or {},
    )

    return {
        "job_id": job_id,
        "state": IngestionState.NOT_STARTED,
        "message": f"""Sync initiated using {syncRequest.ingestion_method}""",
        "progress": None,
    }


@router.post(
    "/factors/{module_type_id}/{data_entry_type_id}", response_model=SyncStatusResponse
)
async def sync_module_factors(
    module_type_id: ModuleTypeEnum,
    data_entry_type_id: DataEntryTypeEnum,
    syncRequest: SyncRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
):
    """
    Sync (recompute) factors for a specific module and data-entry type.

    **Required Permission**: `backoffice.data_management.sync`

    ``year`` is **mandatory** for this endpoint — factor updates are always
    year-scoped.

    Example request body for computed factor update:
    {
        "ingestion_method": 3,
        "target_type": 1,
        "year": 2025
    }
    """
    if syncRequest.year is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year is required for factor sync",
        )

    config: dict = {
        "entity_type": EntityType.MODULE_PER_YEAR.value,
        "year": syncRequest.year,
        "data_entry_type_id": data_entry_type_id.value,
    }

    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum(module_type_id),
        ingestion_method=syncRequest.ingestion_method,
        target_type=syncRequest.target_type,
        config=config,
        user=current_user,
        job_session=db,
        data_session=db,
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider '{syncRequest.ingestion_method}' not supported for "
                f"module '{module_type_id}' / data-entry type '{data_entry_type_id}'"
            ),
        )

    if not await provider.validate_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to {syncRequest.ingestion_method}",
        )

    job_id = await provider.create_job(
        module_type_id=ModuleTypeEnum(module_type_id),
        data_entry_type_id=data_entry_type_id.value,
        entity_type=EntityType.MODULE_PER_YEAR,
        year=syncRequest.year,
        ingestion_method=syncRequest.ingestion_method,
        target_type=syncRequest.target_type,
        config=config,
        db=db,
        request_context={
            "ip_address": extract_ip_address(request),
            "route_path": request.url.path,
            "route_payload": await extract_route_payload(request),
        },
    )
    await db.commit()

    background_tasks.add_task(
        run_ingestion,
        provider_name=provider.__class__.__name__,
        job_id=job_id,
        filters=syncRequest.filters or {},
    )

    return {
        "job_id": job_id,
        "state": IngestionState.NOT_STARTED,
        "message": f"Sync initiated using {syncRequest.ingestion_method}",
        "progress": None,
    }


@router.get("/jobs/by-status", response_model=list[DataIngestionJob])
async def get_jobs_by_status(
    filter_type: str = "completed",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list:
    """
    Get jobs filtered by status.

    **Required Permission**: `backoffice.data_management.view`

    Args:
        filter_type: "active" for in-progress jobs, "completed" for finished jobs
    """
    if filter_type.lower() == "active":
        jobs = await DataIngestionRepository(db).get_active_jobs()
    else:
        jobs = await DataIngestionRepository(db).get_finished_jobs()
    return jobs


@router.get("/jobs/year/{year}", response_model=list[SyncJobResponse])
async def get_jobs_by_year(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list:
    """
    Get all sync jobs for a specific year.

    **Required Permission**: `backoffice.data_management.view`

    Args:
        year: The year to filter jobs by

    Returns:
        List of sync jobs for the specified year
    """
    jobs = await DataIngestionRepository(db).get_jobs_by_year(year)

    # Transform to SyncJobResponse format
    # Filter out jobs with None id (shouldn't happen but type checker needs it)
    return [
        SyncJobResponse(
            job_id=job.id,
            module_type_id=job.module_type_id,
            year=job.year,
            ingestion_method=job.ingestion_method,
            target_type=job.target_type,
            state=job.state if job.state else None,
            status_message=job.status_message,
            meta=job.meta,
        )
        for job in jobs
        if job.id is not None
    ]


@router.get("/jobs/year/{year}/latest", response_model=list[SyncJobResponse])
async def get_latest_jobs_by_year(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list:
    """
    Get the current job for each (module_type_id, target_type) combination.

    **Required Permission**: `backoffice.data_management.view`

    Args:
        year: The year to filter jobs by

    Returns:
        List of sync jobs where is_current = true
    """
    jobs = await DataIngestionRepository(db).get_latest_jobs_by_year(year)

    return [
        SyncJobResponse(
            job_id=job.id,
            module_type_id=job.module_type_id,
            data_entry_type_id=job.data_entry_type_id,
            year=job.year,
            ingestion_method=job.ingestion_method,
            target_type=job.target_type,
            state=job.state,
            result=job.result,
            status_message=job.status_message,
            meta=job.meta,
        )
        for job in jobs
        if job.id is not None
    ]


# SSE endpoint to stream a single job by ID - MUST be before /jobs/{job_id}
@router.get("/jobs/{job_id}/stream")
async def job_stream_by_id(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint to stream a single job update in real-time.

    **Required Permission**: `backoffice.data_management.view`

    Polls the database for status changes and sends updates to the client.
    Stream ends when the job is completed or failed.
    // technically we should check permissions on the specific job's module_type_id
    but for simplicity we check general view permissions here
    """
    has_permission = await is_permitted(
        current_user, "backoffice.data_management", "view"
    ) or await is_permitted(current_user, "modules.*", "view")
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permission denied: requires backoffice.data_management.view "
                "or modules.* view permission"
            ),
        )

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
                "status": job.state,
                "state": job.state,
                "result": job.result,
                "status_message": job.status_message,
                "meta": job.meta if job.meta else None,
            }

            # Yield if either status OR message changed
            if last_status != current_status or last_message != job.status_message:
                yield f"data: {json.dumps(current_status)}\n\n"
                last_status = current_status
                last_message = job.status_message

            # If job is finished...
            if job.state == IngestionState.FINISHED:
                polls_after_completion += 1
                if polls_after_completion >= 2:
                    # Send final completion message before closing stream
                    final_status = {**current_status, "stream_closed": True}
                    yield f"data: {json.dumps(final_status)}\n\n"
                    break

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/recalculation-status", response_model=list[ModuleRecalculationStatus])
async def get_recalculation_status(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list[ModuleRecalculationStatus]:
    """Return per-module recalculation status for the given year.

    **Required Permission**: `backoffice.data_management.view`

    Derived from existing DataIngestionJob rows — no new DB table.
    Returns an empty list when no completed FACTORS jobs exist for the year.

    Args:
        year: The report year to scope the status query.
    """
    rows = await DataIngestionRepository(db).get_recalculation_status_by_year(year)

    modules: dict[int, list[RecalculationStatus]] = {}
    for row in rows:
        module_id = row["module_type_id"]
        if module_id not in modules:
            modules[module_id] = []
        modules[module_id].append(
            RecalculationStatus(
                module_type_id=row["module_type_id"],
                data_entry_type_id=row["data_entry_type_id"],
                year=row["year"],
                needs_recalculation=row["needs_recalculation"],
                last_factor_job_id=row["last_factor_job_id"],
                last_factor_job_result=row["last_factor_job_result"],
                last_recalculation_job_id=row["last_recalculation_job_id"],
                last_recalculation_job_result=row["last_recalculation_job_result"],
            )
        )

    return [
        ModuleRecalculationStatus(
            module_type_id=module_id,
            year=year,
            needs_recalculation=any(det.needs_recalculation for det in dets),
            data_entry_types=dets,
        )
        for module_id, dets in modules.items()
    ]


@router.post(
    "/recalculate-emissions/{module_type_id}/{data_entry_type_id}",
    response_model=SyncStatusResponse,
)
async def recalculate_emissions_for_type(
    module_type_id: ModuleTypeEnum,
    data_entry_type_id: DataEntryTypeEnum,
    year: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
) -> SyncStatusResponse:
    """Trigger emission recalculation for a single data entry type.

    **Required Permission**: `backoffice.data_management.sync`

    Creates a background job and streams progress via
    ``GET /sync/jobs/{job_id}/stream``.

    Args:
        module_type_id: The module type to recalculate.
        data_entry_type_id: The data entry type to recalculate.
        year: The report year (required).
    """
    job = DataIngestionJob(
        module_type_id=module_type_id.value,
        data_entry_type_id=data_entry_type_id.value,
        year=year,
        ingestion_method=IngestionMethod.computed,
        target_type=TargetType.DATA_ENTRIES,
        entity_type=EntityType.MODULE_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        meta={"config": {"year": year, "data_entry_type_id": data_entry_type_id.value}},
    )
    created_job = await DataIngestionRepository(db).create_ingestion_job(job)
    await db.commit()
    if created_job.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recalculation job",
        )

    background_tasks.add_task(
        run_recalculation,
        module_type_id=module_type_id.value,
        data_entry_type_id=data_entry_type_id.value,
        year=year,
        job_id=created_job.id,
    )
    return SyncStatusResponse(
        job_id=created_job.id,
        state=IngestionState.NOT_STARTED,
        message="Emission recalculation scheduled",
    )


@router.post(
    "/recalculate-emissions/{module_type_id}",
    response_model=SyncStatusResponse,
)
async def recalculate_emissions_for_module(
    module_type_id: ModuleTypeEnum,
    year: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    only_stale: bool = True,
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
) -> SyncStatusResponse:
    """Trigger bulk emission recalculation for all (or only stale) data entry types.

    Bulk recalculation for a module.

    **Required Permission**: `backoffice.data_management.sync`

    When ``only_stale=True`` (default), only data entry types where
    ``needs_recalculation=True`` are included.  Returns 400 if no types qualify.
    When ``only_stale=False``, all data entry types for the module are recalculated.

    Args:
        module_type_id: The module type to recalculate.
        year: The report year (required).
        only_stale: If True, skip types that are already up to date.
    """
    all_det_ids = [
        det.value for det in MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type_id, [])
    ]

    if only_stale:
        status_rows = await DataIngestionRepository(
            db
        ).get_recalculation_status_by_year(year)
        stale_ids = {
            row["data_entry_type_id"]
            for row in status_rows
            if row["module_type_id"] == module_type_id.value
            and row["needs_recalculation"]
        }
        det_ids = [det_id for det_id in all_det_ids if det_id in stale_ids]
        if not det_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data entry types require recalculation for this module",
            )
    else:
        det_ids = all_det_ids

    job = DataIngestionJob(
        module_type_id=module_type_id.value,
        data_entry_type_id=None,
        year=year,
        ingestion_method=IngestionMethod.computed,
        target_type=TargetType.DATA_ENTRIES,
        entity_type=EntityType.MODULE_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        meta={
            "config": {
                "year": year,
                "data_entry_type_ids": det_ids,
                "only_stale": only_stale,
            }
        },
    )
    created_job = await DataIngestionRepository(db).create_ingestion_job(job)
    await db.commit()
    if created_job.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recalculation job",
        )

    background_tasks.add_task(
        run_module_recalculation,
        module_type_id=module_type_id.value,
        data_entry_type_ids=det_ids,
        year=year,
        job_id=created_job.id,
    )
    n = len(det_ids)
    return SyncStatusResponse(
        job_id=created_job.id,
        state=IngestionState.NOT_STARTED,
        message=f"Module emission recalculation scheduled for {n} data entry types",
    )


@router.post("/units", response_model=SyncStatusResponse)
async def sync_units_from_accred(
    syncRequest: SyncUnitRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync units from Accred API.

    Triggers background task to fetch and upsert all units and principal users
    from the Accred API. Uses hardcoded UserProvider.ACCRED for now.

    **Required Permission**: `backoffice.data_management.sync`

    Returns:
        SyncStatusResponse with job status (note: job_id is 0 as this is a
        simple background task without persistent job tracking)
    """

    # Schedule background task
    background_tasks.add_task(sync_units_from_accred_task, syncRequest)

    return SyncStatusResponse(
        job_id=0,  # No persistent job tracking for now
        state=IngestionState.NOT_STARTED,
        message="Unit sync from Accred API scheduled",
    )
