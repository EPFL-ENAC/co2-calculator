"""User repository for database operations.

This repository handles internal user database operations.
Users are managed through OAuth authentication only.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.models.user import Role, User
from app.repositories.unit_repo import upsert_unit
from app.repositories.unit_user_repo import upsert_unit_user


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
    user = result.scalars().first()
    if user:
        user = User.model_validate(user.model_dump())
    return user


async def upsert_user(
    db: AsyncSession,
    email: str,
    sciper: Optional[str] = None,
    roles: Optional[List[Role]] = None,
    units: Optional[List[str]] = None,
    affiliations: Optional[List[str]] = None,
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

    #  1. Upsert units
    for unit_id in units or []:
        await upsert_unit(db, unit_id)

    def _serialize_roles(roles):
        return [r.dict() if hasattr(r, "dict") else r for r in roles]

    roles = _serialize_roles(roles) if roles else None
    now = datetime.utcnow()
    if user:
        # Update existing user
        user.sciper = str(sciper) if sciper is not None else None
        user.roles = roles or []
        user.last_login = now
        user.updated_at = now
    else:
        # Create new user
        user = User(
            id=email,
            email=email,
            sciper=str(sciper) if sciper is not None else None,
            roles=roles or [],
            is_active=True,
            last_login=now,
            created_at=now,
            created_by=str(sciper) if sciper is not None else None,
            updated_at=now,
            updated_by=str(sciper) if sciper is not None else None,
        )
        db.add(user)

    # 2. Upsert user
    await db.commit()
    await db.refresh(user)

    # 3. Upsert UnitUser associations
    for unit_id in units or []:
        await upsert_unit_user(db, unit_id=unit_id, user_id=user.id)

    return user


async def update_user_roles(
    db: AsyncSession, user_id: str, roles: List[Role]
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

    payload = user.model_copy()
    payload.roles = roles
    payload.updated_at = datetime.utcnow()
    user = User(**payload.model_dump())
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
