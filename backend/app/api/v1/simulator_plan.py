"""Simulator plan (project planner) API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.policy import require_unit_access
from app.models.unit import Unit
from app.models.user import User
from app.schemas.simulator_plan import (
    SimulatorPlanCreate,
    SimulatorPlanRead,
    SimulatorPlanReferenceYearUpdate,
    SimulatorPlanUpdate,
    SimulatorPlanYearRead,
)
from app.services.simulator_plan_service import SimulatorPlanService

logger = get_logger(__name__)
router = APIRouter()


async def _require_plan_unit_access(
    db: AsyncSession, current_user: User, plan_id: int
) -> SimulatorPlanService:
    """Load the plan's unit and enforce access; 404 if the plan is missing."""
    service = SimulatorPlanService(db)
    plan = await service.repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    unit = await db.get(Unit, plan.unit_id)
    require_unit_access(current_user, unit)
    return service


@router.get("/unit/{unit_id}/", response_model=List[SimulatorPlanRead])
async def list_simulator_plans(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all simulator plans for a unit, newest first."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = SimulatorPlanService(db)
    return await service.list_plans(unit_id)


@router.post(
    "/unit/{unit_id}/",
    response_model=SimulatorPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_plan(
    unit_id: int,
    plan: Optional[SimulatorPlanCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a simulator plan; without a name, the next default is assigned."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = SimulatorPlanService(db)
    try:
        result = await service.create_plan(
            unit_id=unit_id,
            user=current_user,
            name=plan.name if plan else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return result


@router.get("/unit/{unit_id}/by-name/{name}", response_model=SimulatorPlanRead)
async def get_simulator_plan_by_name(
    unit_id: int,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a simulator plan of a unit by its name."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = SimulatorPlanService(db)
    result = await service.get_plan_by_name(unit_id, name)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


@router.patch("/{plan_id}", response_model=SimulatorPlanRead)
async def update_simulator_plan(
    plan_id: int,
    plan: SimulatorPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a simulator plan (name, year range, lab visibility).

    Setting/changing the year range syncs the plan's per-year reports:
    missing years are created with their modules, out-of-range years are
    deleted together with their entries.
    """
    service = await _require_plan_unit_access(db, current_user, plan_id)
    try:
        result = await service.update_plan(plan_id, plan)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.commit()
    return result


@router.get("/{plan_id}/years", response_model=List[SimulatorPlanYearRead])
async def list_simulator_plan_years(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the plan's per-year reports (with modules and stats), by year."""
    service = await _require_plan_unit_access(db, current_user, plan_id)
    result = await service.list_plan_years(plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


@router.patch("/{plan_id}/years/{year}", response_model=SimulatorPlanYearRead)
async def set_simulator_plan_reference_year(
    plan_id: int,
    year: int,
    update: SimulatorPlanReferenceYearUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the reference (baseline) year of one plan-year report.

    All factors and prefill data of the simulation year are sourced from
    the reference year; existing entries get their emissions recomputed.
    """
    service = await _require_plan_unit_access(db, current_user, plan_id)
    result = await service.set_reference_year(plan_id, year, update.reference_year)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan year not found")
    await db.commit()
    return result


@router.post(
    "/{plan_id}/duplicate",
    response_model=SimulatorPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_simulator_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Duplicate a simulator plan under the next free `<name>-N` name."""
    service = await _require_plan_unit_access(db, current_user, plan_id)
    result = await service.duplicate_plan(plan_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.commit()
    return result


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulator_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a simulator plan (and any carbon reports attached to it)."""
    service = await _require_plan_unit_access(db, current_user, plan_id)
    deleted = await service.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
