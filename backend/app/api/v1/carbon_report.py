"""Carbon Report API endpoints."""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.policy import require_unit_access
from app.db import SessionLocal
from app.models.unit import Unit
from app.models.user import User
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportModuleRead,
    CarbonReportModuleUpdate,
    CarbonReportRead,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService

_EXPLORE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


async def _refresh_explore_background(
    unit_id: int, old_report_id: int, reference_year: int
) -> None:
    """Delete a stale Simulator Explore report and create a fresh one.

    Runs as a FastAPI background task after the response has been sent.
    Opens its own session so the request session lifetime is not a concern.
    The new report starts empty — Simulator Explore is not seeded from Calculator.
    """
    async with SessionLocal() as db:
        service = CarbonReportService(db)
        await service.delete(old_report_id)
        await service.create_explore(unit_id=unit_id, reference_year=reference_year)
        await db.commit()


logger = get_logger(__name__)
router = APIRouter()


@router.get("/unit/{unit_id}/", response_model=List[CarbonReportRead])
async def list_carbon_reports_by_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all carbon reports for a given unit."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    return await service.list_by_unit(unit_id)


@router.get("/unit/{unit_id}/year/{year}/", response_model=CarbonReportRead)
async def get_carbon_report_by_unit_and_year(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return 404 if not found, else retrieve carbon report for unit and year."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    report = await service.get_by_unit_and_year(unit_id, year)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    return report


@router.post("/", response_model=CarbonReportRead, status_code=status.HTTP_201_CREATED)
async def create_carbon_report(
    report: CarbonReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new carbon report for a given unit and year."""
    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    result = await service.create(report)
    await db.commit()
    return result


@router.get(
    "/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/",
    response_model=CarbonReportRead,
)
async def get_simulator_explore_carbon_report(
    unit_id: int,
    reference_year: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an existing Simulator Explore carbon report.

    If the report has exceeded its TTL (24 h) a background task is scheduled
    to delete the stale report and seed a fresh one — the current (stale)
    report is returned immediately so the user is not blocked.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    result = await service.get_explore(unit_id=unit_id, reference_year=reference_year)
    if result is None:
        raise HTTPException(
            status_code=404, detail="Simulator Explore report not found"
        )

    now_ts = int(datetime.now(timezone.utc).timestamp())
    age = now_ts - int(result.last_updated or 0)
    if result.last_updated is None or age > _EXPLORE_TTL_SECONDS:
        background_tasks.add_task(
            _refresh_explore_background,
            unit_id=unit_id,
            old_report_id=result.id,
            reference_year=reference_year,
        )

    return result


@router.post(
    "/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/",
    response_model=CarbonReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_explore_carbon_report(
    unit_id: int,
    reference_year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Simulator Explore carbon report seeded from the Calculator report.

    The explore report is seeded from the unit's Calculator report.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    result = await service.create_explore(
        unit_id=unit_id,
        reference_year=reference_year,
    )
    await db.commit()
    return result


@router.get("/{carbon_report_id}", response_model=CarbonReportRead)
async def get_carbon_report(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a carbon report by ID."""
    service = CarbonReportService(db)
    report = await service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    return report


# --- CarbonReportModule endpoints ---


@router.get("/{carbon_report_id}/modules/", response_model=List[CarbonReportModuleRead])
async def list_carbon_report_modules(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all modules for a carbon report with their statuses.

    Plan 310-D / Issue #1062 — pipeline state lives in the unified
    frontend ``pipelineStateStore`` driven by
    ``GET /v1/sync/active-pipelines``.  This endpoint returns the
    pure module-status read.
    """
    # First verify carbon report exists
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")

    module_service = CarbonReportModuleService(db)
    return await module_service.list_modules(carbon_report_id)


@router.patch(
    "/{carbon_report_id}/modules/{module_type_id}/status",
    response_model=CarbonReportModuleRead,
)
async def update_carbon_report_module_status(
    carbon_report_id: int,
    module_type_id: int,
    update: CarbonReportModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of a carbon report module.

    Status values:
    - 0: not_started
    - 1: in_progress
    - 2: validated
    """
    # First verify carbon report exists
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")

    module_service = CarbonReportModuleService(db)
    try:
        result = await module_service.update_status(
            carbon_report_id, module_type_id, update.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"""Module type {module_type_id} not found for
                carbon report {carbon_report_id}"""
            ),
        )

    await report_service.recompute_report_stats(carbon_report_id)
    await report_service.recompute_report_progress(carbon_report_id)
    await db.commit()
    return result
