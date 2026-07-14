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
    SimulatorPlanUpdate,
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
async def rename_simulator_plan(
    plan_id: int,
    plan: SimulatorPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a simulator plan."""
    service = await _require_plan_unit_access(db, current_user, plan_id)
    try:
        result = await service.rename_plan(plan_id, plan.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
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
