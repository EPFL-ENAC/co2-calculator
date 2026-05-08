import asyncio
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import db as db_module
from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.policy import check_module_permission, get_module_permission_decision
from app.core.security import is_permitted, require_permission
from app.models.carbon_report import CarbonReport, CarbonReportModule
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
from app.models.unit import Unit
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository, WhyStaleLiteral
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks._background import fire_and_forget
from app.tasks.runner import run_job
from app.tasks.unit_sync_tasks import SyncUnitRequest
from app.utils.request_context import extract_ip_address, extract_route_payload


def _job_type_for(target_type: TargetType, ingestion_method: IngestionMethod) -> str:
    """Map (target_type, ingestion_method) → ``DataIngestionJob.job_type``.

    Plan 310-C runner uses ``job_type`` as the registry key; the endpoint
    must stamp it on the row before firing ``run_job``.  Mapping mirrors
    the registered handlers in ``app/tasks/ingestion_tasks.py``:

    - ``FACTORS``        → ``factor_ingest`` (any ingestion method —
                           CSV upload, API pull, computed recompute)
    - ``DATA_ENTRIES`` + ``csv``      → ``csv_ingest``
    - ``DATA_ENTRIES`` + ``api``      → ``api_ingest``
    - ``DATA_ENTRIES`` + ``manual`` / ``computed`` — same handler shape
       as ``api_ingest`` (provider-driven), so route there.
    """
    if target_type == TargetType.FACTORS:
        return "factor_ingest"
    if ingestion_method == IngestionMethod.csv:
        return "csv_ingest"
    return "api_ingest"


async def _stamp_job_type_and_meta(
    db: AsyncSession,
    job_id: int,
    *,
    job_type: str,
    provider_name: Optional[str] = None,
    extra_meta: Optional[dict] = None,
) -> None:
    """After ``provider.create_job`` returns, stamp ``job_type`` and
    extend ``meta`` so the runner's registry lookup hits the right
    handler and so the handler can resolve its provider class.

    The provider's ``create_job`` already wrote ``meta = {"factor_type_id":
    …, "config": job_config}``; we keep those keys and merge in
    ``provider_name`` plus any caller-supplied extras.  Commit is the
    caller's responsibility.
    """
    repo = DataIngestionRepository(db)
    row = await repo.get_job_by_id(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job {job_id} disappeared after creation",
        )
    row.job_type = job_type
    merged_meta: dict = {**(row.meta or {})}
    if provider_name is not None:
        merged_meta["provider_name"] = provider_name
    if extra_meta:
        merged_meta.update(extra_meta)
    row.meta = merged_meta
    db.add(row)


async def _institutional_id_for_job(
    job: DataIngestionJob, db: AsyncSession
) -> Optional[str]:
    """Resolve a job's institutional scope for permission gating.

    ``MODULE_UNIT_SPECIFIC`` jobs carry ``entity_id`` (FK to
    ``carbon_report_modules.id``) which chains to ``carbon_reports.unit_id`` →
    ``units.institutional_id``.  ``MODULE_PER_YEAR`` (the common
    aggregation/recalc case) is global and has no unit; the caller falls back
    to the bare ``modules.{name}`` permission path.
    """
    if job.entity_type != EntityType.MODULE_UNIT_SPECIFIC or job.entity_id is None:
        return None
    stmt = (
        select(Unit.institutional_id)
        # mypy: SQLAlchemy ``==`` between Column attrs returns a
        # ``BinaryExpression`` at runtime, but mypy without the SQLAlchemy
        # plugin sees ``bool``.  Standard project workaround.
        .join(CarbonReport, CarbonReport.unit_id == Unit.id)  # type: ignore[arg-type]
        .join(
            CarbonReportModule,
            CarbonReportModule.carbon_report_id == CarbonReport.id,  # type: ignore[arg-type]
        )
        .where(CarbonReportModule.id == job.entity_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _check_job_scope(
    job: DataIngestionJob,
    current_user: User,
    db: AsyncSession,
    *,
    action: str = "view",
) -> None:
    """Per-job permission gate (unit-scoped jobs only).

    Layered on top of the existing ``backoffice.data_management.*`` global
    gate so a user with backoffice access still has to clear the per-module
    scope when a job is pinned to a specific unit (``MODULE_UNIT_SPECIFIC``).

    Jobs that are cross-unit (``MODULE_PER_YEAR`` aggregation/recalc) or
    unscoped (``unit_sync``, factor ingests not pinned to a module) are
    gated by the global permission alone — the per-module path doesn't
    apply.  Unit-scoped backoffice users only hold
    ``modules.X/<institutional_id>`` permissions, so calling
    ``check_module_permission(institutional_id=None)`` for a cross-unit
    job would deny everyone except the (rare) operator with an unscoped
    ``modules.X`` permission.
    """
    if job.module_type_id is None:
        return
    institutional_id = await _institutional_id_for_job(job, db)
    if institutional_id is None:
        # MODULE_PER_YEAR or unresolvable scope — the global
        # backoffice.data_management gate already ran upstream via
        # require_permission(...) and is the right granularity here.
        # TODO(#459): once sub-perimeter scoping ships, derive a
        # broader scope set from the job's module + year and tighten.
        return
    await check_module_permission(
        current_user,
        job.module_type_id,
        action,
        institutional_id=institutional_id,
    )


async def _check_pipeline_scope_from_jobs(
    jobs: list[DataIngestionJob],
    current_user: User,
    db: AsyncSession,
    *,
    action: str = "view",
) -> None:
    """Per-pipeline permission gate, given an already-fetched job list.

    Use this from endpoints that have already loaded the pipeline's jobs
    (the read endpoint and the SSE stream both do — sharing the result
    avoids a redundant ``list_jobs_by_pipeline_id`` round-trip on every
    poll iteration).

    Picks the parent job to derive ``(module_type_id, institutional_id)``:
    prefer the latest ``aggregation`` job (the chain terminator that pins
    the module + year scope), otherwise fall back to any job in the
    pipeline so factor-only chains still resolve.
    """
    if not jobs:
        return
    parent = next(
        (j for j in reversed(jobs) if j.job_type == "aggregation"),
        jobs[0],
    )
    await _check_job_scope(parent, current_user, db, action=action)


async def _check_pipeline_scope(
    pipeline_id: UUID,
    current_user: User,
    db: AsyncSession,
    *,
    action: str = "view",
) -> None:
    """Per-pipeline permission gate (fetches the job list itself).

    Prefer ``_check_pipeline_scope_from_jobs`` when the caller has
    already loaded the pipeline's jobs.
    """
    jobs = await DataIngestionRepository(db).list_jobs_by_pipeline_id(pipeline_id)
    await _check_pipeline_scope_from_jobs(jobs, current_user, db, action=action)


router = APIRouter()


class SyncRequestConfig(BaseModel):
    carbon_report_module_id: Optional[int] = None
    data_entry_type_id: Optional[int] = None
    reduction_objective_type_id: Optional[int] = None
    module_type_id: Optional[ModuleTypeEnum] = None


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
    locked_by: Optional[str] = None
    is_current: Optional[bool] = None


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


class PipelineJobResponse(BaseModel):
    """Single ``DataIngestionJob`` row inside a multi-step pipeline run.

    Plan 310C — surfaces the columns dashboards need to render the chain
    parent + fan-out children produced by ``_enqueue_stale_recalculations``.

    TODO(#1026): once ``started_at`` / ``finished_at`` columns land on
    ``data_ingestion_jobs``, extend this schema and the endpoint mapping
    below to return them so the UI can show per-step durations.  Leaving
    them out here keeps this PR mergeable on top of ``dev`` before #1026.
    """

    job_id: int
    job_type: Optional[str] = None
    state: Optional[IngestionState] = None
    result: Optional[IngestionResult] = None
    target_type: Optional[TargetType] = None
    status_message: Optional[str] = None
    module_type_id: Optional[int] = None
    data_entry_type_id: Optional[int] = None
    year: Optional[int] = None


class PipelineResponse(BaseModel):
    """Wrapper for ``GET /sync/pipelines/{pipeline_id}`` — pipeline UUID
    plus the ordered job list (parent first, then fan-out children)."""

    pipeline_id: UUID
    jobs: list[PipelineJobResponse]


class StaleStatsEntry(BaseModel):
    """One ``(module_type_id, year)`` scope whose aggregation is missing,
    failed, stuck, or too old.  Returned by ``GET /sync/health/stale-stats``
    for Datadog/Prometheus scrape — Plan 310-D Follow-up 1 (#1063)."""

    module_type_id: int
    year: int
    last_finished_aggregation_at: Optional[datetime] = None
    why_stale: WhyStaleLiteral
    last_aggregation_job_id: Optional[int] = None


@router.post("/dispatch", response_model=SyncStatusResponse)
async def sync_module_data_entries(
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
                not supported""",
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
    module_type_id = config.get("module_type_id") or getattr(
        syncRequest, "module_type_id", None
    )
    if module_type_id is not None:
        module_type_id = ModuleTypeEnum(module_type_id)
    job_id = await provider.create_job(
        module_type_id=module_type_id,
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
    # NOTE: file_path validation happens in provider.__init__() via
    # _validate_file_path() to prevent directory traversal attacks
    # (e.g., /../../../etc/passwd).
    await _stamp_job_type_and_meta(
        db,
        job_id,
        job_type=_job_type_for(syncRequest.target_type, syncRequest.ingestion_method),
        provider_name=provider.__class__.__name__,
        extra_meta={"filters": syncRequest.filters or {}},
    )
    await db.commit()

    fire_and_forget(run_job(job_id), name=f"run_job-{job_id}")

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
        "module_type_id": ModuleTypeEnum(module_type_id),
    }

    provider = await ProviderFactory.create_provider(
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
    await _stamp_job_type_and_meta(
        db,
        job_id,
        job_type=_job_type_for(syncRequest.target_type, syncRequest.ingestion_method),
        provider_name=provider.__class__.__name__,
        extra_meta={"filters": syncRequest.filters or {}},
    )
    await db.commit()

    fire_and_forget(run_job(job_id), name=f"run_job-{job_id}")

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


@router.post("/jobs/{job_id}/cancel", response_model=SyncJobResponse)
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
):
    """
    Cancel a stuck ingestion job.

    Sets the job to FINISHED/ERROR and unsets is_current so the user
    can re-upload. Only jobs in NOT_STARTED, QUEUED, or RUNNING state
    can be cancelled.

    **Required Permission**: `backoffice.data_management.sync`
    """
    repo = DataIngestionRepository(db)
    existing = await repo.get_job_by_id(job_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or not cancellable",
        )
    # TODO(#459): tighten when sub-perimeter scoping ships
    await _check_job_scope(existing, current_user, db, action="sync")
    job = await repo.cancel_job(job_id)
    if not job or job.id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or not cancellable",
        )
    await db.commit()
    return SyncJobResponse(
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


# SSE endpoint to stream a single job by ID - MUST be before /jobs/{job_id}
@router.get("/jobs/{job_id}/stream")
async def job_stream_by_id(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint to stream a single job update in real-time.

    **Required Permission**: `backoffice.data_management.view`

    Polls the database for status changes and sends updates to the client.
    Stream ends when the job is completed, failed, or the client disconnects.

    Session lifetime: a fresh ``SessionLocal()`` is opened per poll iteration
    and closed before the sleep so we don't pin an asyncpg pool slot for the
    full stream duration (minutes).  ``request.is_disconnected()`` is checked
    at the top of each iteration so client aborts surface immediately rather
    than after the next poll.

    TODO(#459): tighten when sub-perimeter scoping ships
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

    # Up-front per-job scope check — drops a pool slot before the stream opens
    # so cross-tenant subscriptions never hit the poll loop.
    async with db_module.SessionLocal() as session:
        existing = await DataIngestionRepository(session).get_job_by_id(job_id)
        if existing is not None:
            # TODO(#459): tighten when sub-perimeter scoping ships
            await _check_job_scope(existing, current_user, session, action="view")

    async def event_generator():
        last_status = None
        last_message = None
        polls_after_completion = 0

        while True:
            if await request.is_disconnected():
                break

            async with db_module.SessionLocal() as session:
                job = await DataIngestionRepository(session).get_job_by_id(job_id)

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


@router.get("/active-pipelines", response_model=dict[int, str])
async def get_active_pipelines(
    year: int,
    modules: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> dict[int, str]:
    """Return the active pipeline_id (if any) for each requested module.

    **Required Permission**: ``backoffice.data_management.view``

    Plan 310-D / Issue #1062 — bulk read used by the unified frontend
    ``pipelineStateStore`` to drive the "Recalculating..." badge.  Thin
    wrapper over ``DataIngestionRepository.get_current_pipeline_ids_for_modules``.

    Args:
        year: Report year scope — pipelines touching ``(module_type_id, year)``.
        modules: Comma-separated list of ``module_type_id`` ints (e.g.
            ``"1,2,3"``).  Empty string returns ``{}``.

    Returns:
        Mapping ``module_type_id -> pipeline_id`` (string UUID) for every
        module that has at least one active (NOT_STARTED/QUEUED/RUNNING)
        pipeline-attached job for the given ``year``.  Modules with no
        active pipeline are absent from the dict — callers ``.get(...)``
        and treat missing keys as "no badge" (sparse passthrough matching
        the underlying repo helper's contract).
    """
    if not modules.strip():
        return {}
    try:
        module_type_ids = [int(m) for m in modules.split(",") if m.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="modules must be a comma-separated list of integers",
        ) from exc

    # Per-module scope filter: drop entries the caller can't view rather than
    # 403-ing the whole batch.  The global ``backoffice.data_management.view``
    # gate above proves the user is a backoffice user; this loop additionally
    # verifies they have view access to each specific module.  Without it, a
    # backoffice user scoped to a sub-perimeter could enumerate active
    # pipeline UUIDs across modules they otherwise can't read.
    # TODO(#459): once sub-perimeter scoping ships, also pass institutional_id.
    allowed_module_ids: list[int] = []
    for module_type_id in module_type_ids:
        decision = await get_module_permission_decision(
            current_user, module_type_id, "view"
        )
        if decision.get("allow"):
            allowed_module_ids.append(module_type_id)

    if not allowed_module_ids:
        return {}

    pipeline_by_module = await DataIngestionRepository(
        db
    ).get_current_pipeline_ids_for_modules(allowed_module_ids, year=year)
    return {module_id: str(pid) for module_id, pid in pipeline_by_module.items()}


@router.get("/active-pipelines/year/{year}", response_model=list[str])
async def get_active_year_level_pipelines(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list[str]:
    """Return active **year-level** pipeline_ids (``entity_type=GLOBAL_PER_YEAR``).

    **Required Permission**: ``backoffice.data_management.view``

    Issue #867 — back-office data-management page reload reattach.  The
    sibling ``GET /active-pipelines`` only sees module-scoped pipelines
    (it requires a ``modules`` query param and filters by
    ``module_type_id``).  Year-level chains (e.g. the unit-sync pipeline
    minted by the create-year flow) carry no ``module_type_id`` and
    were invisible to that endpoint, so the frontend SSE watcher could
    not re-attach after a reload.

    Returns a flat list of pipeline_id UUIDs (string-serialised) for
    every job in ``NOT_STARTED`` / ``QUEUED`` / ``RUNNING`` with
    ``entity_type=GLOBAL_PER_YEAR`` and the given ``year``.  Order is
    most-recent-first by job id; the frontend treats the list as a
    set, but a stable order makes assertion-based tests trivial.

    The endpoint applies only the global ``backoffice.data_management.view``
    gate — there is no per-module decision loop here because year-level
    pipelines are not module-scoped (the per-module security guard on
    the sibling endpoint defends against pipeline_id enumeration across
    *modules* a backoffice user can't read; year-level pipelines have
    no equivalent sub-perimeter today).

    Empty result is the steady state — both "no active year-level
    pipelines" and "U1's pipeline-stamping for unit_sync hasn't shipped
    yet" surface as the same empty list, which is what the watcher
    needs to safely no-op.
    """
    pipeline_ids = await DataIngestionRepository(
        db
    ).get_active_year_level_pipeline_ids(year)
    return [str(pid) for pid in pipeline_ids]


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


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline_jobs(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> PipelineResponse:
    """Return every job in a multi-step pipeline run, ordered by id.

    **Required Permission**: ``backoffice.data_management.view``

    Plan 310C — ``_enqueue_stale_recalculations`` (310B) stamps the same
    ``pipeline_id`` on the parent FACTORS job and every fan-out
    DATA_ENTRIES child it seeds.  The dashboard uses this endpoint to
    render the whole chain, not just the parent.

    Returns 404 when no jobs share the given ``pipeline_id`` — matches
    the convention of other lookup endpoints in this module
    (``cancel_job``, ``recover_job``).
    """
    jobs = await DataIngestionRepository(db).list_jobs_by_pipeline_id(pipeline_id)
    if not jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No jobs found for pipeline_id {pipeline_id}",
        )
    # TODO(#459): tighten when sub-perimeter scoping ships
    await _check_pipeline_scope_from_jobs(jobs, current_user, db, action="view")

    return PipelineResponse(
        pipeline_id=pipeline_id,
        jobs=[
            PipelineJobResponse(
                job_id=job.id,
                job_type=job.job_type,
                state=job.state,
                result=job.result,
                target_type=job.target_type,
                status_message=job.status_message,
                module_type_id=job.module_type_id,
                data_entry_type_id=job.data_entry_type_id,
                year=job.year,
            )
            for job in jobs
            if job.id is not None
        ],
    )


@router.get("/pipelines/{pipeline_id}/stream")
async def pipeline_stream_by_id(
    pipeline_id: UUID,
    request: Request,
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
):
    """Server-Sent Events stream for every job sharing a ``pipeline_id``.

    **Required Permission**: ``backoffice.data_management.view`` — same gate
    as the read-only ``GET /sync/pipelines/{pipeline_id}`` endpoint.

    Plan 310D — the frontend stale-stats UX subscribes here when a module's
    carbon-report response surfaces a ``current_pipeline_id``.  Each tick
    re-reads every job in the pipeline and emits an ``event:
    pipeline-update`` SSE message *only when* a job's
    ``(state, status_message, result, started_at, finished_at)`` tuple
    changed — so an idle pipeline doesn't spam the wire.  ``started_at``
    is included because PR #1026 made it transition NOT_STARTED → claim
    via ``func.coalesce``, and the dashboard wants to surface that flip.
    A separate ``event: ping`` heartbeat
    fires every ~15s to keep proxies (nginx, AWS ALB) from idling the
    connection out.  The stream closes once **every** job in the pipeline is
    ``FINISHED``; a final ``stream_closed`` flag is sent so the client can
    react before the EventSource reconnect-on-close kicks in.

    Returns ``404`` when no rows share the given ``pipeline_id`` — fired on
    the first poll *before* the stream opens, so SSE clients see a clean
    HTTP error rather than a 200-with-empty-body that they'd interpret as
    an aborted connection.
    """
    # Up-front 404 + scope check: the existing job-stream endpoint emits a
    # "not found" event in-stream, but for pipeline streams the SSE client
    # cannot tell "pipeline does not exist" from "pipeline exists, no events
    # yet" once the 200 lands.  Surfacing the 404 before opening the stream
    # makes the contract symmetric with ``GET /sync/pipelines/{pipeline_id}``.
    # The session is closed before the StreamingResponse opens so we don't
    # pin a pool slot for the whole stream lifetime.
    async with db_module.SessionLocal() as session:
        repo = DataIngestionRepository(session)
        initial_jobs = await repo.list_jobs_by_pipeline_id(pipeline_id)
        if not initial_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No jobs found for pipeline_id {pipeline_id}",
            )
        # TODO(#459): tighten when sub-perimeter scoping ships
        await _check_pipeline_scope_from_jobs(
            initial_jobs, current_user, session, action="view"
        )

    # Tunables — keep the polling cadence tight enough that UI updates
    # feel real-time, but spread the heartbeat across many polls so the
    # ping packet is rare.  Defaults match the existing job-stream poll.
    poll_interval_seconds = 2
    heartbeat_interval_seconds = 15

    async def event_generator():
        last_snapshot: Optional[list[dict]] = None
        polls_after_completion = 0
        seconds_since_heartbeat = 0

        while True:
            if await request.is_disconnected():
                break

            # Open a fresh session per poll so the asyncpg pool slot is
            # released between ticks.  The previous implementation captured
            # ``Depends(get_db)`` for the entire generator lifetime, pinning
            # one slot per subscriber for the whole stream (minutes).
            async with db_module.SessionLocal() as session:
                jobs = await DataIngestionRepository(session).list_jobs_by_pipeline_id(
                    pipeline_id
                )

            # Snapshot the columns the spec calls out for the dashboard:
            # only these fields trigger a re-emit, so meta-only mutations
            # (e.g. progress dicts) don't flood the stream.
            snapshot = [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "state": (job.state.value if job.state is not None else None),
                    "result": (job.result.value if job.result is not None else None),
                    "status_message": job.status_message,
                    "started_at": (
                        job.started_at.isoformat() if job.started_at else None
                    ),
                    "finished_at": (
                        job.finished_at.isoformat() if job.finished_at else None
                    ),
                }
                for job in jobs
                if job.id is not None
            ]

            if snapshot != last_snapshot:
                payload = {
                    "pipeline_id": str(pipeline_id),
                    "jobs": snapshot,
                }
                yield f"event: pipeline-update\ndata: {json.dumps(payload)}\n\n"
                last_snapshot = snapshot
                # Snapshot change counts as keep-alive — reset the heartbeat
                # clock so we don't double-emit on the next tick.
                seconds_since_heartbeat = 0

            all_finished = bool(jobs) and all(
                job.state == IngestionState.FINISHED for job in jobs
            )
            if all_finished:
                polls_after_completion += 1
                # Mirror the job-stream endpoint's "send a final marker
                # then close" handshake so clients can flip UI state
                # before the EventSource reconnect logic fires.
                if polls_after_completion >= 2:
                    final_payload = {
                        "pipeline_id": str(pipeline_id),
                        "jobs": last_snapshot or snapshot,
                        "stream_closed": True,
                    }
                    yield (
                        f"event: pipeline-update\ndata: {json.dumps(final_payload)}\n\n"
                    )
                    break

            await asyncio.sleep(poll_interval_seconds)
            seconds_since_heartbeat += poll_interval_seconds
            if seconds_since_heartbeat >= heartbeat_interval_seconds:
                yield "event: ping\ndata: {}\n\n"
                seconds_since_heartbeat = 0

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
        job_type="emission_recalc",
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

    fire_and_forget(run_job(created_job.id), name=f"run_job-{created_job.id}")
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
        job_type="module_emission_recalc",
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

    fire_and_forget(run_job(created_job.id), name=f"run_job-{created_job.id}")
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

    Plan 310B Part 5 — creates a tracked DataIngestionJob (job_type=
    unit_sync, entity_type=GLOBAL_PER_YEAR) so progress is observable via
    the SSE stream and the job is recoverable on pod crash via the safety
    poller.

    **Required Permission**: `backoffice.data_management.sync`

    Returns:
        SyncStatusResponse with the persistent job_id and initial state.
    """
    job = DataIngestionJob(
        job_type="unit_sync",
        module_type_id=None,
        data_entry_type_id=None,
        year=syncRequest.target_year,
        ingestion_method=IngestionMethod.api,
        target_type=TargetType.REFERENCE_DATA,
        entity_type=EntityType.GLOBAL_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        meta={"config": {"target_year": syncRequest.target_year}},
    )
    created = await DataIngestionRepository(db).create_ingestion_job(job)
    await db.commit()
    if created.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create unit sync job",
        )

    # Fire-and-forget; the safety poller (Plan 310A) recovers the job
    # if this pod crashes before the runner claims it.  Plan 310-C
    # cutover: dispatch goes through the unified ``run_job`` runner —
    # the registered ``unit_sync_handler`` reads ``meta.config.target_year``
    # (set above) so the legacy ``SyncUnitRequest``-passing call is gone.
    fire_and_forget(
        run_job(created.id),
        name=f"run_job-{created.id}",
    )

    return SyncStatusResponse(
        job_id=created.id,
        state=IngestionState.NOT_STARTED,
        message="Unit sync from Accred API scheduled",
    )


@router.post("/jobs/{job_id}/recover", response_model=SyncJobResponse)
async def recover_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "sync")
    ),
):
    """
    Recover a job stuck in RUNNING after a pod crash.

    Resets the job to NOT_STARTED and clears the lock. Only allowed
    when ``locked_at`` is older than ``STALE_JOB_TIMEOUT_MINUTES`` (default 30 min).

    **Required Permission**: ``backoffice.data_management.sync``
    """
    settings = get_settings()
    repo = DataIngestionRepository(db)
    # TODO(#459): tighten when sub-perimeter scoping ships
    # Pull only the columns the scope check needs so the row is NOT hydrated
    # into the session's identity map — ``recover_job``'s ``UPDATE`` relies
    # on ``synchronize_session`` evaluation, which mis-handles a hydrated
    # tz-aware ``locked_at`` against a tz-naive value on SQLite.
    scope_row = (
        await db.execute(
            select(
                DataIngestionJob.module_type_id,
                DataIngestionJob.entity_type,
                DataIngestionJob.entity_id,
            ).where(DataIngestionJob.id == job_id)
        )
    ).first()
    if scope_row is not None:
        scope_job = DataIngestionJob(
            module_type_id=scope_row.module_type_id,
            entity_type=scope_row.entity_type,
            entity_id=scope_row.entity_id,
        )
        await _check_job_scope(scope_job, current_user, db, action="sync")
    recovered = await repo.recover_job(job_id, settings.STALE_JOB_TIMEOUT_MINUTES)
    if not recovered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job {job_id} cannot be recovered: not found, not in RUNNING state, "
                "or lock is not yet stale"
            ),
        )
    if recovered.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recovered job has no ID",
        )
    return SyncJobResponse(
        job_id=recovered.id,
        module_type_id=recovered.module_type_id,
        data_entry_type_id=recovered.data_entry_type_id,
        year=recovered.year,
        ingestion_method=recovered.ingestion_method,
        target_type=recovered.target_type,
        state=recovered.state,
        result=recovered.result,
        status_message=recovered.status_message,
        meta=recovered.meta,
        locked_by=recovered.locked_by,
        is_current=recovered.is_current,
    )


@router.get("/health/stale-stats", response_model=list[StaleStatsEntry])
async def get_stale_stats(
    older_than_minutes: int = Query(
        60,
        ge=1,
        description=(
            "Threshold (minutes) — successful aggregations whose ``finished_at`` "
            "is younger than this are considered fresh and excluded.  Pending and "
            "failed rows surface regardless of age."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.data_management", "view")
    ),
) -> list[StaleStatsEntry]:
    """Read-only backstop for the aggregation pipeline (Plan 310-D Follow-up 1
    / #1063).

    The interactive runner-driven chain surfaces failures via the recalc
    badge and pipeline diagnostic tooltip, but background failures with
    nobody watching (stuck NOT_STARTED rows, last-run errors, slow-burn
    drift) had no single owner.  This endpoint walks ``carbon_report_modules``
    × ``carbon_reports.year`` (the source-of-truth for "what should have an
    aggregation") and joins the latest ``job_type='aggregation'`` row per
    scope, returning one entry per stale or missing aggregation.

    Intended for Datadog / Prometheus scrape — emits a count per
    ``why_stale`` bucket and lets operator dashboards alert on
    non-zero values.  No auto-retry: the operator decides what to do
    based on which bucket lit up.

    **Required Permission**: ``backoffice.data_management.view``
    """
    rows = await DataIngestionRepository(db).find_stale_aggregations(older_than_minutes)
    return [StaleStatsEntry(**row) for row in rows]
