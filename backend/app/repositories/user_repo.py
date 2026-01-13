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

    async def get_by_id(self, id: int) -> Optional[User]:
        """Get user by ID (integer)."""
        result = await self.session.exec(select(User).where(User.id == id))
        entity = result.one_or_none()
        return entity

    async def get_by_code(self, code: str) -> Optional[User]:
        """Get user by code."""
        result = await self.session.exec(select(User).where(User.code == code))
        entity = result.one_or_none()
        return entity

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.exec(select(User).where(User.email == email))
        entity = result.one_or_none()
        return entity

    async def create(
        self,
        code: str,
        email: str = "",
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[str] = None,
        function: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        now = datetime.utcnow()
        entity = User(
            code=code,
            email=email,
            display_name=display_name,
            roles=roles or [],
            provider=provider,
            function=function,
            last_login=now,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        id: int,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[str] = None,
        function: Optional[str] = None,
    ) -> User:
        """Update an existing user by ID."""
        result = await self.session.exec(select(User).where(User.id == id))
        entity = result.one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="User not found")

        now = datetime.utcnow()

        if roles is not None:
            entity.roles = roles

        entity.last_login = now
        entity.display_name = display_name or entity.display_name
        entity.provider = provider or entity.provider
        entity.function = function or entity.function
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
