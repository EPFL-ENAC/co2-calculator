"""Resource API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate
from app.services import resource_service

logger = logging.getLogger(__name__)
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
    logger.info(f"User {current_user.id} requesting resource list")
    resources = await resource_service.list_resources(
        db, current_user, skip=skip, limit=limit
    )
    logger.info(f"Returning {len(resources)} resources to user {current_user.id}")
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
    logger.info(f"User {current_user.id} requesting resource {resource_id}")
    resource = await resource_service.get_resource(db, resource_id, current_user)
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
    logger.info(f"User {current_user.id} creating resource")
    created_resource = await resource_service.create_resource(
        db, resource, current_user
    )
    logger.info(f"Created resource {created_resource.id}")
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
    logger.info(f"User {current_user.id} updating resource {resource_id}")
    updated_resource = await resource_service.update_resource(
        db, resource_id, resource_update, current_user
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
    logger.info(f"User {current_user.id} deleting resource {resource_id}")
    await resource_service.delete_resource(db, resource_id, current_user)
    return None


@router.get("/count", response_model=dict)
async def count_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get count of accessible resources."""
    count = await resource_service.count_resources(db, current_user)
    return {"count": count}
