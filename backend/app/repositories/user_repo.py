"""User repository for database operations.

This repository handles internal user database operations.
Users are managed through OAuth authentication only.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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


async def upsert_user(
    db: AsyncSession,
    email: str,
    sciper: Optional[str] = None,
    roles: Optional[List[dict]] = None,
) -> User:
    """
    Create or update a user (internal operation for OAuth flow).

    Args:
        db: Database session
        email: User email (used as ID)
        sciper: SCIPER number
        roles: Hierarchical roles list

    Returns:
        Created or updated user
    """
    user = await get_user_by_email(db, email)

    if user:
        # Update existing user
        user.sciper = sciper
        user.roles = roles or []
        user.last_login = datetime.utcnow()
        user.updated_at = datetime.utcnow()
    else:
        # Create new user
        user = User(
            id=email,
            email=email,
            sciper=sciper,
            roles=roles or [],
            is_active=True,
            last_login=datetime.utcnow(),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


async def update_user_roles(
    db: AsyncSession, user_id: str, roles: List[dict]
) -> Optional[User]:
    """
    Update user roles (internal operation).

    Args:
        db: Database session
        user_id: User ID
        roles: New hierarchical roles list

    Returns:
        Updated user or None if not found
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    user.roles = roles
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


async def count_users(db: AsyncSession, filters: Optional[dict] = None) -> int:
    """Count users with optional filters (internal operation)."""
    query = select(func.count()).select_from(User)

    if filters:
        for key, value in filters.items():
            if hasattr(User, key):
                query = query.where(getattr(User, key) == value)

    result = await db.execute(query)
    return result.scalar_one()
