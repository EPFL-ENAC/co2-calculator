"""Resource repository for database operations."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.resource import Resource
from app.schemas.resource import ResourceCreate


def get_resource_by_id(db: Session, resource_id: int) -> Optional[Resource]:
    """Get resource by ID."""
    return db.query(Resource).filter(Resource.id == resource_id).first()


def get_resources(
    db: Session, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
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
    query = db.query(Resource)

    if filters:
        for key, value in filters.items():
            if hasattr(Resource, key):
                if isinstance(value, list):
                    # Handle list filters (e.g., visibility in ['public', 'unit'])
                    query = query.filter(getattr(Resource, key).in_(value))
                else:
                    query = query.filter(getattr(Resource, key) == value)

    return query.offset(skip).limit(limit).all()


def get_resources_by_owner(db: Session, owner_id: str) -> List[Resource]:
    """Get all resources owned by a specific user."""
    return db.query(Resource).filter(Resource.owner_id == owner_id).all()


def get_resources_by_unit(db: Session, unit_id: str) -> List[Resource]:
    """Get all resources in a specific unit."""
    return db.query(Resource).filter(Resource.unit_id == unit_id).all()


def get_public_resources(db: Session) -> List[Resource]:
    """Get all public resources."""
    return db.query(Resource).filter(Resource.visibility == "public").all()


def create_resource(db: Session, resource: ResourceCreate, owner_id: str) -> Resource:
    """
    Create a new resource.

    Args:
        db: Database session
        resource: Resource creation schema
        owner_id: Owner user ID

    Returns:
        Created resource
    """
    db_resource = Resource(
        name=resource.name,
        description=resource.description,
        unit_id=resource.unit_id,
        owner_id=owner_id,
        visibility=resource.visibility,
        data=resource.data,
        resource_metadata=resource.metadata,
    )

    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)

    return db_resource


def update_resource(db: Session, resource_id: int, updates: dict) -> Optional[Resource]:
    """
    Update resource fields.

    Args:
        db: Database session
        resource_id: Resource ID
        updates: Dictionary of fields to update

    Returns:
        Updated resource or None if not found
    """
    resource = get_resource_by_id(db, resource_id)
    if not resource:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(resource, key):
            setattr(resource, key, value)

    db.commit()
    db.refresh(resource)

    return resource


def delete_resource(db: Session, resource_id: int) -> bool:
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

    db.delete(resource)
    db.commit()

    return True


def count_resources(db: Session, filters: Optional[dict] = None) -> int:
    """
    Count resources with optional filters.

    Args:
        db: Database session
        filters: Dictionary of filters

    Returns:
        Number of resources matching filters
    """
    query = db.query(Resource)

    if filters:
        for key, value in filters.items():
            if hasattr(Resource, key):
                if isinstance(value, list):
                    query = query.filter(getattr(Resource, key).in_(value))
                else:
                    query = query.filter(getattr(Resource, key) == value)

    return query.count()
