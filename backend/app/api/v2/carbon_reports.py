"""Carbon Report API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportModuleRead,
    CarbonReportModuleUpdate,
    CarbonReportRead,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/unit/{unit_id}/", response_model=List[CarbonReportRead])
async def list_carbon_reports_by_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all carbon reports for a given unit."""
    service = CarbonReportService(db)
    return await service.list_by_unit(unit_id)


@router.get("/unit/{unit_id}/year/{year}/", response_model=CarbonReportRead)
async def get_carbon_report_by_unit_and_year(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return 404 if not found, else retrieve carbon report for unit and year."""
    service = CarbonReportService(db)
    report = await service.get_by_unit_and_year(unit_id, year)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    return report


@router.post("/", response_model=CarbonReportRead, status_code=status.HTTP_201_CREATED)
async def create_carbon_report(
    report: CarbonReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new carbon report for a given unit and year."""
    service = CarbonReportService(db)
    return await service.create(report)


@router.get("/{carbon_report_id}", response_model=CarbonReportRead)
async def get_carbon_report(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a carbon report by ID."""
    service = CarbonReportService(db)
    report = await service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    return report


# --- CarbonReportModule endpoints ---


@router.get("/{carbon_report_id}/modules/", response_model=List[CarbonReportModuleRead])
async def list_carbon_report_modules(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all modules for a carbon report with their statuses."""
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
    current_user: User = Depends(get_current_active_user),
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
                f"Module type {module_type_id} not found for carbon report {carbon_report_id}"
            ),
        )
    return result
