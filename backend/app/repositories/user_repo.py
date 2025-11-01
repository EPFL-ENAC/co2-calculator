"""User repository for database operations."""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, func
from app.core.crypto import get_password_hash  # Import from crypto module instead
from app.models.user import User
from app.schemas.user import UserCreate


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalars().first()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalars().first()


async def get_user_by_sciper(db: AsyncSession, sciper: str) -> Optional[User]:
    """Get user by SCIPER number."""
    query = select(User).where(User.sciper == sciper)
    result = await db.execute(query)
    return result.scalars().first()


async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
) -> List[User]:
    """
    Get list of users with optional filters.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        filters: Dictionary of filters to apply

    Returns:
        List of users
    """
    query = select(User)

    if filters:
        for key, value in filters.items():
            if hasattr(User, key):
                query = query.where(getattr(User, key) == value)

    result = await db.execute(query.offset(skip).limit(limit))
    return list(result.scalars().all())


async def get_users_by_unit(db: AsyncSession, unit_id: str) -> List[User]:
    """Get all users in a specific unit."""
    result = await db.execute(select(User).where(User.unit_id == unit_id))
    return list(result.scalars().all())


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        user: User creation schema

    Returns:
        Created user
    """
    hashed_password = get_password_hash(user.password)

    db_user = User(
        id=user.email,  # Using email as ID for simplicity
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        unit_id=user.unit_id,
        sciper=user.sciper,
        roles=user.roles or [],
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


async def update_user(db: AsyncSession, user_id: str, updates: dict) -> Optional[User]:
    """
    Update user fields.

    Args:
        db: Database session
        user_id: User ID
        updates: Dictionary of fields to update

    Returns:
        Updated user or None if not found
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(user, key):
            if key == "password":
                setattr(user, "hashed_password", get_password_hash(value))
            else:
                setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    return user


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """
    Delete a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        True if deleted, False if not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    await db.delete(user)
    await db.commit()

    return True


async def count_users(db: AsyncSession, filters: Optional[dict] = None) -> int:
    """Count users with optional filters."""
    query = select(func.count()).select_from(User)

    if filters:
        for key, value in filters.items():
            if hasattr(User, key):
                query = query.where(getattr(User, key) == value)

    result = await db.execute(query)
    return result.scalar_one()
