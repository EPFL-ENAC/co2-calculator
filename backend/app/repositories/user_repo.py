"""User repository for database operations.

This repository handles internal user database operations.
Users are managed through OAuth authentication only.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import Role, User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.exec(select(User).where(User.id == user_id))
        entity = result.one_or_none()
        return entity

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.exec(select(User).where(User.email == email))
        entity = result.one_or_none()
        return entity

    async def create(
        self,
        user_id: Optional[str] = None,
        email: str = "",
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        now = datetime.utcnow()
        entity = User(
            id=user_id,
            email=email,
            display_name=display_name,
            roles=roles or [],
            is_active=True,
            last_login=now,
            created_at=now,
            created_by=user_id,
            updated_at=now,
            updated_by=user_id,
            provider=provider,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[str] = None,
    ) -> User:
        """Update an existing user."""
        result = await self.session.exec(select(User).where(User.id == user_id))
        entity = result.one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="User not found")

        now = datetime.utcnow()

        if roles is not None:
            entity.roles = roles

        entity.last_login = now
        entity.updated_at = now

        entity.display_name = display_name or entity.display_name
        entity.updated_by = user_id
        entity.provider = provider or entity.provider
        # force revalidation
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count users with optional filters."""
        query = select(func.count()).select_from(User)

        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    query = query.where(getattr(User, key) == value)

        result = await self.session.execute(query)
        return result.scalar_one()
