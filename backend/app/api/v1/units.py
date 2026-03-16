"""Unit API endpoints."""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.unit import UnitRead
from app.services.unit_service import UnitService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}", response_model=UnitRead)
async def get_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific resource by ID.

    Returns 403 if user is not authorized to access this resource.
    Returns 404 if resource does not exist.
    """
    unit = await UnitService(db).get_by_id(unit_id, current_user)
    logger.info(
        "User requested unit",
        extra={"user_id": current_user.id, "unit_id": unit_id},
    )
    return unit
