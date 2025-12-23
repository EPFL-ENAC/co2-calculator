"""User API endpoints.

NOTE: User management endpoints have been removed.
Users are managed internally through OAuth/OIDC authentication only.
User information is available via /auth/me endpoint.

This file is kept for potential future internal user management needs.
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.unit import UnitWithUserRole
from app.services.unit_service import UnitService

logger = get_logger(__name__)
router = APIRouter()

# All user management endpoints removed - users are read-only via /auth/me
# Users are auto-created and updated during OAuth login flow


@router.get("/units", response_model=List[UnitWithUserRole])
async def list_user_units(
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
        extra={"user_id": sanitize(current_user.id), "count": len(units)},
    )
    return units
