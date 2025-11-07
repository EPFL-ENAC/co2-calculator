"""Resource service for business logic with OPA integration."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.opa_client import query_opa
from app.models.resource import Resource
from app.models.user import User
from app.repositories import resource_repo
from app.schemas.resource import ResourceCreate, ResourceUpdate

logger = get_logger(__name__)


def _build_opa_input(
    user: User, action: str, resource: Optional[Resource] = None
) -> dict:
    """
    Build OPA input data from user and resource context.

    Args:
        user: Current user
        action: Action to authorize (read, create, update, delete)
        resource: Optional resource being accessed

    Returns:
        OPA input dictionary
    """
    input_data = {
        "action": action,
        "resource_type": "resource",
        "user": {
            "id": user.id,
            "email": user.email,
            "roles": user.roles or [],
            "unit_id": user.unit_id,
            "is_superuser": user.is_superuser,
        },
    }

    if resource:
        input_data["resource"] = {
            "id": resource.id,
            "owner_id": resource.owner_id,
            "unit_id": resource.unit_id,
            "visibility": resource.visibility,
        }

    return input_data


async def list_resources(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 100
) -> List[Resource]:
    """
    List resources with OPA authorization.

    This is the core service method that demonstrates the authorization flow:
    1. Build OPA input with user context
    2. Query OPA for decision
    3. Apply filters from OPA decision
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
    # Build OPA input
    input_data = _build_opa_input(user, "read")

    # Query OPA for authorization decision
    decision = await query_opa("authz/resource/list", input_data)
    logger.info(
        "OPA decision requested",
        extra={
            "user_id": user.id,
            "action": "list_resources",
            "decision": decision,
            "input_data": input_data,
        },
    )

    # Check if action is allowed: Fail silently
    # if not decision.get("allow", False):
    #     reason = decision.get("reason", "Access denied")
    #     logger.warning(f"OPA denied resource list for user {user.id}: {reason}")
    #     return []
    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource list", extra={"user_id": user.id, "reason": reason}
        )
        raise HTTPException(status_code=403, detail=f"Access denied: {reason}")

    # Extract filters from OPA decision
    filters = decision.get("filters", {})

    # Query database with filters
    resources = await resource_repo.get_resources(
        db, skip=skip, limit=limit, filters=filters
    )

    return resources


async def get_resource(db: AsyncSession, resource_id: int, user: User) -> Resource:
    """
    Get a resource by ID with authorization.

    Args:
        db: Database session
        resource_id: Resource ID
        user: Current user

    Returns:
        Resource if authorized

    Raises:
        HTTPException: If resource not found or access denied
    """
    # Get resource
    resource = await resource_repo.get_resource_by_id(db, resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Build OPA input with resource context
    input_data = _build_opa_input(user, "read", resource)

    # Query OPA for authorization
    decision = await query_opa("authz/resource/read", input_data)
    logger.info(
        "OPA read decision requested",
        extra={
            "user_id": user.id,
            "action": "get_resource",
            "resource_id": resource_id,
        },
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource read",
            extra={
                "user_id": user.id,
                "resource_id": sanitize(resource_id),
                "reason": reason,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to access this resource: {reason}",
        )

    return resource


async def create_resource(
    db: AsyncSession, resource_in: ResourceCreate, user: User
) -> Resource:
    """
    Create a new resource with authorization.

    Args:
        db: Database session
        resource_in: Resource creation data
        user: Current user

    Returns:
        Created resource

    Raises:
        HTTPException: If not authorized to create
    """
    # Build OPA input
    input_data = _build_opa_input(user, "create")
    input_data["resource_data"] = {
        "unit_id": resource_in.unit_id,
        "visibility": resource_in.visibility,
    }

    # Query OPA for authorization
    decision = await query_opa("authz/resource/create", input_data)
    logger.info(
        "OPA create decision requested",
        extra={"user_id": user.id, "action": "create_resource"},
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource creation", extra={"user_id": user.id, "reason": reason}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to create resource: {reason}",
        )

    # Validate unit_id matches user's unit (unless superuser)
    if not user.is_superuser and resource_in.unit_id != user.unit_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create resources for other units",
        )

    # Create resource
    resource = await resource_repo.create_resource(db, resource_in, str(user.id))
    logger.info(
        "Resource created", extra={"user_id": user.id, "resource_id": str(resource.id)}
    )
    return resource


async def update_resource(
    db: AsyncSession, resource_id: int, resource_update: ResourceUpdate, user: User
) -> Resource:
    """
    Update a resource with authorization.

    Args:
        db: Database session
        resource_id: Resource ID
        resource_update: Resource update data
        user: Current user

    Returns:
        Updated resource

    Raises:
        HTTPException: If resource not found or not authorized
    """
    # Get existing resource
    resource = await resource_repo.get_resource_by_id(db, resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Build OPA input
    input_data = _build_opa_input(user, "update", resource)

    # Query OPA for authorization
    decision = await query_opa("authz/resource/update", input_data)
    logger.info(
        "OPA update decision requested",
        extra={
            "user_id": user.id,
            "action": "update_resource",
            "resource_id": resource_id,
        },
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource update",
            extra={
                "user_id": user.id,
                "resource_id": sanitize(resource_id),
                "reason": reason,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to update this resource: {reason}",
        )

    # Update resource
    updates = resource_update.model_dump(exclude_unset=True)
    updated_resource = await resource_repo.update_resource(db, resource_id, updates)

    if not updated_resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    logger.info(
        "Resource updated",
        extra={"user_id": user.id, "resource_id": sanitize(resource_id)},
    )
    return updated_resource


async def delete_resource(db: AsyncSession, resource_id: int, user: User) -> bool:
    """
    Delete a resource with authorization.

    Args:
        db: Database session
        resource_id: Resource ID
        user: Current user

    Returns:
        True if deleted

    Raises:
        HTTPException: If resource not found or not authorized
    """
    # Get existing resource
    resource = await resource_repo.get_resource_by_id(db, resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Build OPA input
    input_data = _build_opa_input(user, "delete", resource)

    # Query OPA for authorization
    decision = await query_opa("authz/resource/delete", input_data)
    logger.info(
        "OPA delete decision requested",
        extra={
            "user_id": user.id,
            "action": "delete_resource",
            "resource_id": sanitize(resource_id),
        },
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Access denied")
        logger.warning(
            "OPA denied resource delete",
            extra={
                "user_id": user.id,
                "resource_id": sanitize(resource_id),
                "reason": reason,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to delete this resource: {reason}",
        )

    # Delete resource
    success = await resource_repo.delete_resource(db, resource_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    logger.info(
        "Resource deleted",
        extra={"user_id": user.id, "resource_id": sanitize(resource_id)},
    )
    return success


async def count_resources(db: AsyncSession, user: User) -> int:
    """
    Count resources accessible to user.

    Args:
        db: Database session
        user: Current user

    Returns:
        Number of accessible resources
    """
    # Build OPA input
    input_data = _build_opa_input(user, "read")

    # Query OPA for authorization
    decision = await query_opa("authz/resource/list", input_data)

    if not decision.get("allow", False):
        return 0

    # Extract filters from OPA decision
    filters = decision.get("filters", {})

    # Count resources with filters
    return await resource_repo.count_resources(db, filters)
