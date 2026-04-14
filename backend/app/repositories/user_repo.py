"""User repository for database operations.

This repository handles internal user database operations.
Users are managed through OAuth authentication only.
"""

from datetime import datetime, timezone
from typing import List, Optional

from attr import dataclass
from fastapi import HTTPException
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import Role, User, UserProvider


@dataclass
class UpsertUserResult:
    created: int
    updated: int
    total: int
    data: List[User]

    def __str__(self) -> str:
        return (
            f"{self.total} processed ({self.created} created, {self.updated} updated)"
        )


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[User]:
        """Get user by ID (integer)."""
        result = await self.session.exec(select(User).where(User.id == id))
        entity = result.one_or_none()
        return entity

    async def get_by_code(self, institutional_id: str) -> Optional[User]:
        """Get user by institutional_id.

        Deprecated: use get_by_institutional_id_and_provider instead.
        """
        result = await self.session.exec(
            select(User).where(User.institutional_id == institutional_id)
        )
        entity = result.one_or_none()
        return entity

    async def get_by_institutional_id_and_provider(
        self,
        institutional_id: str,
        provider: UserProvider,
    ) -> Optional[User]:
        """Get user by institutional_id scoped to provider.

        This is the primary lookup method to prevent cross-provider collisions.
        """
        result = await self.session.exec(
            select(User).where(
                User.institutional_id == institutional_id,
                User.provider == provider,
            )
        )
        entity = result.one_or_none()
        return entity

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.exec(select(User).where(User.email == email))
        entity = result.one_or_none()
        return entity

    async def create(
        self,
        institutional_id: str,
        email: str = "",
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[UserProvider] = None,
        function: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        now = datetime.now(timezone.utc)
        entity = User(
            institutional_id=institutional_id,
            email=email,
            display_name=display_name,
            roles=roles or [],
            provider=provider,
            function=function,
            last_login=now,
        )
        # ensure setter is called
        entity.roles = roles or []
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        id: int,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[UserProvider] = None,
        function: Optional[str] = None,
    ) -> User:
        """Update an existing user by ID."""
        result = await self.session.exec(select(User).where(User.id == id))
        entity = result.one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="User not found")

        now = datetime.now(timezone.utc)

        if roles is not None:
            entity.roles = roles

        entity.last_login = now
        entity.display_name = display_name or entity.display_name
        entity.provider = provider or entity.provider
        entity.function = function or entity.function
        # force revalidation
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def bulk_create(self, users: List[User]) -> List[User]:
        """Bulk create users."""
        # db_objs = [User.model_validate(user) for user in users]
        self.session.add_all(users)
        await self.session.flush()
        return users

    async def bulk_upsert(self, users: List[User]) -> UpsertUserResult:
        if not users:
            return UpsertUserResult(created=0, updated=0, total=0, data=[])
        rows = (await self.session.exec(select(User.institutional_id, User.id))).all()
        existing: dict[str, int] = {code: uid for code, uid in rows if uid is not None}

        created = len(users) - len(existing)
        updated = len(existing)
        merged = []
        for user in users:
            user.id = existing.get(user.institutional_id)
            result = await self.session.merge(user)
            merged.append(result)
        return UpsertUserResult(
            created=created, updated=updated, total=len(users), data=merged
        )

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
    ) -> List[User]:
        """List users with optional filters."""
        query = select(User)

        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    if isinstance(value, list):
                        query = query.where(getattr(User, key).in_(value))
                    else:
                        query = query.where(getattr(User, key) == value)

        query = query.offset(skip).limit(limit)
        result = await self.session.exec(query)
        return list(result.all())

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count users with optional filters."""
        query = select(func.count()).select_from(User)

        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    query = query.where(getattr(User, key) == value)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def delete(self, id: int) -> bool:
        """Delete a user by ID."""
        result = await self.session.exec(select(User).where(User.id == id))
        entity = result.one_or_none()
        if not entity:
            return False

        await self.session.delete(entity)
        await self.session.flush()
        return True
