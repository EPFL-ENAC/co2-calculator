"""Unit API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User

# from app.repositories.unit_repo import upsert_unit
from app.schemas.unit import UnitRead
from app.services.unit_service import UnitService

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=List[UnitRead])
async def list_units(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List units with policy authorization.

    This endpoint
    1. User is authenticated via JWT (handled by dependency)
    2. Service layer queries policy engine for filters
    3. Repository applies filters to database query
    4. Only authorized resources are returned

    The policy engine determines which resources the user can see based on:
    - User roles
    - Unit membership
    - Unit visibility
    """
    units = await UnitService(db).get_user_units(current_user, skip=skip, limit=limit)
    logger.info(
        "User requested unit list",
        extra={"user_id": current_user.id, "count": len(units)},
    )
    return units


@router.get("/{unit_id}", response_model=UnitRead)
async def get_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific resource by ID.

    Returns 403 if user is not authorized to access this resource.
    Returns 404 if resource does not exist.
    """
    unit = await UnitService(db).get_by_id(unit_id, current_user)
    logger.info(
        "User requested unit",
        extra={"user_id": current_user.id, "unit_id": sanitize(unit_id)},
    )
    return unit
