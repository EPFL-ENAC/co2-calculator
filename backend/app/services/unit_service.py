"""Unit service for business logic with Policy integration."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.models.unit import Unit
from app.models.user import User
from app.repositories import unit_repo

logger = get_logger(__name__)


def _build_policy_input(user: User, action: str, unit: Optional[Unit] = None) -> dict:
    """
    Build OPA input data from user and unit context.

    Args:
        user: Current user
        action: Action to authorize (read, create, update, delete)
        unit: Optional unit being accessed

    Returns:
        input dictionary
    """
    input_data = {
        "action": action,
        "resource_type": "unit",
        "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
    }

    if unit:
        input_data["resource"] = {
            "id": unit.id,
            "created_by": unit.created_by,
            "visibility": unit.visibility,
        }

    return input_data


async def list_units(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 100
) -> List[Unit]:
    """
    List units with policy authorization.

    This is the core service method that demonstrates the authorization flow:
    1. Build policy input with user context
    2. Query policy for decision
    3. Apply filters from policy decision
    4. Query database with filters

    Args:
        db: Database session
        user: Current user
        skip: Number of records to skip
        limit: Maximum number of records

    Returns:
        List of authorized resources

    Example OPA decision:
        {
            "allow": true,
            "filters": {
                "unit_id": "ENAC",
                "visibility": ["public", "unit"]
            }
        }
    """
    # Build policy input
    input_data = _build_policy_input(user, "read")

    # Query policy for authorization decision
    decision = await query_policy("authz/unit/list", input_data)
    logger.info(
        "Policy decision requested",
        extra={
            "user_id": user.id,
            "action": "list_units",
            "decision": decision,
            "input_data": input_data,
        },
    )

    # implement deny logic
    # if not decision.get("allow", False):
    #     reason = decision.get("reason", "Access denied")
    #     logger.warning(
    #         "Policy denied list", extra={"user_id": user.id, "reason": reason}
    #     )
    #     raise HTTPException(status_code=403, detail=f"Access denied: {reason}")

    # Extract filters from policy decision
    filters = decision.get("filters", {})

    # Query database with filters
    units = await unit_repo.get_units(db, skip=skip, limit=limit, filters=filters)

    return units


async def get_unit(db: AsyncSession, unit_id: int, user: User) -> Unit:
    """
    Get a unit by ID with authorization.
    Args:
        db: Database session
        unit_id: Unit ID
        user: Current user

    Returns:
        Unit if authorized

    Raises:
        HTTPException: If resource not found or access denied
    """
    # Get unit
    unit = await unit_repo.get_unit_by_id(db, unit_id)
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found"
        )

    # Build policy input with unit context
    input_data = _build_policy_input(user, "read", unit)
    # Query policy for authorization
    decision = await query_policy("authz/resource/read", input_data)
    logger.info(
        "Policy read decision requested",
        extra={
            "user_id": user.id,
            "action": "get_unit",
            "unit_id": sanitize(unit_id),
        },
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource read",
            extra={
                "user_id": user.id,
                "unit_id": sanitize(unit_id),
                "reason": reason,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to access this resource: {reason}",
        )

    return unit
