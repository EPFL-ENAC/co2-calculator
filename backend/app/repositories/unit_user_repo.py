"""User repository for database operations.

This repository handles internal user database operations.
Users are managed through OAuth authentication only.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.unit_user import UnitUser


async def get_user_by_unit(
    db: AsyncSession, unit_id: str, user_id: str
) -> Optional[UnitUser]:
    """Get user by unit ID and user ID."""
    query = select(UnitUser).where(
        (UnitUser.user_id == user_id) & (UnitUser.unit_id == unit_id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def upsert_unit_user(
    db: AsyncSession,
    unit_id: str,
    user_id: str,
) -> UnitUser:
    """
    Create or update a UnitUser association.

    Args:
        db: Database session
        unit_id: Unit ID
        user_id: User ID
    """
    unit_user = await get_user_by_unit(db, unit_id, user_id)

    if unit_user:
        # Update existing user
        # unit_user.updated_at = datetime.utcnow()
        # maybe role ?
        pass
    else:
        # Create new user
        unit_user = UnitUser(
            user_id=user_id,
            unit_id=unit_id,
        )
        db.add(unit_user)

    await db.commit()
    await db.refresh(unit_user)

    return unit_user
