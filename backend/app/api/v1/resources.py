"""Resource API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate
from app.services import resource_service

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=List[ResourceRead])
async def list_resources(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List resources with OPA authorization.

    This endpoint demonstrates the complete authorization flow:
    1. User is authenticated via JWT (handled by dependency)
    2. Service layer queries OPA for filters
    3. Repository applies filters to database query
    4. Only authorized resources are returned

    The OPA policy determines which resources the user can see based on:
    - User roles
    - Unit membership
    - Resource visibility
    """
    resources = await resource_service.list_resources(
        db, current_user, skip=skip, limit=limit
    )
    logger.info(
        "User requested resource list",
        extra={"user_id": current_user.id, "count": len(resources)},
    )
    return resources


@router.get("/{resource_id}", response_model=ResourceRead)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific resource by ID.

    Returns 403 if user is not authorized to access this resource.
    Returns 404 if resource does not exist.
    """
    resource = await resource_service.get_resource(db, resource_id, current_user)
    logger.info(
        "User requested resource",
        extra={"user_id": current_user.id, "resource_id": sanitize(resource_id)},
    )
    return resource


@router.post("/", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new resource.

    The user must have permission to create resources in the specified unit.
    """
    created_resource = await resource_service.create_resource(
        db, resource, current_user
    )
    logger.info(
        "Resource created",
        extra={
            "user_id": current_user.id,
            "resource_id": sanitize(created_resource.id),
        },
    )
    return created_resource


@router.patch("/{resource_id}", response_model=ResourceRead)
async def update_resource(
    resource_id: int,
    resource_update: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a resource.

    Only the resource owner or users with appropriate roles can update.
    """
    updated_resource = await resource_service.update_resource(
        db, resource_id, resource_update, current_user
    )
    logger.info(
        "Resource updated",
        extra={
            "user_id": current_user.id,
            "resource_id": sanitize(updated_resource.id),
        },
    )
    return updated_resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a resource.

    Only the resource owner or users with appropriate roles can delete.
    """
    await resource_service.delete_resource(db, resource_id, current_user)
    logger.info(
        "Resource deleted",
        extra={"user_id": current_user.id, "resource_id": sanitize(resource_id)},
    )
    return None


@router.get("/count", response_model=dict)
async def count_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get count of accessible resources."""
    count = await resource_service.count_resources(db, current_user)
    logger.info(
        "User requested resource count",
        extra={"user_id": current_user.id, "count": count},
    )
    return {"count": count}
