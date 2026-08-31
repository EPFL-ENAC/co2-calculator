"""User API endpoints.

NOTE: User management endpoints have been removed.
Users are managed internally through OAuth/OIDC authentication only.
User information is available via GET /v1/session endpoint.

This file is kept for potential future internal user management needs.
"""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.unit import UnitWithUserRole
from app.services.unit_service import UnitService

logger = get_logger(__name__)
router = APIRouter()

# All user management endpoints removed - users are read-only via GET /v1/session
# Users are auto-created and updated during OAuth login flow


@router.get("/units", response_model=list[UnitWithUserRole])
async def list_user_units(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List units with policy authorization.

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
    units = await UnitService(db).get_user_units(current_user)
    logger.info(
        "User requested unit list",
        extra={"user_id": sanitize(current_user.id), "count": len(units)},
    )
    return units
