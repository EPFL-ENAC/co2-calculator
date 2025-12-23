"""Resource repository for database operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.models.resource import Resource
from app.schemas.resource import ResourceCreate


async def get_resource_by_id(db: AsyncSession, resource_id: int) -> Optional[Resource]:
    """Get resource by ID."""
    result = await db.execute(select(Resource).where((Resource.id == resource_id)))
    return result.scalars().first()


async def get_resources(
    db: AsyncSession, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
) -> List[Resource]:
    """
    Get list of resources with optional filters.

    This is the core repository method that applies filters.
    Filters typically come from OPA policy decisions.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        filters: Dictionary of filters (e.g., {"unit_id": "14", "owner_id": "user123"})

    Returns:
        List of resources matching filters

    Example:
        # Get resources owned by specific user
        resources = get_resources(db, filters={"owner_id": "user@example.com"})

        # Get resources in specific unit
        resources = get_resources(db, filters={"unit_id": "ENAC"})
    """
    query = select(Resource)

    if filters:
        for key, value in filters.items():
            if hasattr(Resource, key):
                if isinstance(value, list):
                    # Handle list filters (e.g., visibility in ['public', 'unit'])
                    query = query.where(getattr(Resource, key).in_(value))
                else:
                    query = query.where(getattr(Resource, key) == value)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_resource(
    db: AsyncSession, resource: ResourceCreate, user_id: str
) -> Resource:
    """
    Create a new resource.

    Args:
        db: Database session
        resource: Resource creation schema
        user_id: created_by user ID

    Returns:
        Created resource
    """
    db_resource = Resource(
        name=resource.name,
        description=resource.description,
        unit_id=resource.unit_id,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        updated_by=user_id,
        visibility=resource.visibility,
        data=resource.data,
        resource_metadata=resource.resource_metadata,
    )

    db.add(db_resource)
    await db.commit()
    await db.refresh(db_resource)

    return db_resource


async def update_resource(
    db: AsyncSession, resource_id: int, updates: dict
) -> Optional[Resource]:
    """
    Update resource fields.

    Args:
        db: Database session
        resource_id: Resource ID
        updates: Dictionary of fields to update

    Returns:
        Updated resource or None if not found
    """
    resource = await get_resource_by_id(db, resource_id)
    if not resource:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(resource, key):
            setattr(resource, key, value)

    await db.commit()
    await db.refresh(resource)

    return resource


async def delete_resource(db: AsyncSession, resource_id: int) -> bool:
    """
    Delete a resource.

    Args:
        db: Database session
        resource_id: Resource ID

    Returns:
        True if deleted, False if not found
    """
    resource = get_resource_by_id(db, resource_id)
    if not resource:
        return False

    await db.delete(resource)
    await db.commit()

    return True


async def count_resources(db: AsyncSession, filters: Optional[dict] = None) -> int:
    """
    Count resources with optional filters.

    Args:
        db: Database session
        filters: Dictionary of filters

    Returns:
        Number of resources matching filters
    """
    query = select(func.count()).select_from(Resource)

    if filters:
        for key, value in filters.items():
            if hasattr(Resource, key):
                if isinstance(value, list):
                    query = query.where(getattr(Resource, key).in_(value))
                else:
                    query = query.where(getattr(Resource, key) == value)

    result = await db.execute(query)
    return result.scalar_one()
