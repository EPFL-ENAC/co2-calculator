"""Headcount service for business logic."""

from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.repositories.headcount_repo import HeadCountRepository


class HeadcountService:
    """Service for headcount business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = HeadCountRepository(session)

    async def create_headcount(
        self,
        data: HeadCountCreate,
        provider_source: str,
        user_id: str,
    ) -> HeadCount:
        """Create a new headcount record."""
        return await self.repo.create_headcount(
            data=data,
            provider_source=provider_source,
            user_id=user_id,
        )

    async def update_headcount(
        self,
        headcount_id: int,
        data: HeadCountUpdate,
        user_id: str,
    ) -> Optional[HeadCount]:
        """Update an existing headcount record."""
        return await self.repo.update_headcount(
            headcount_id=headcount_id,
            data=data,
            user_id=user_id,
        )

    async def delete_headcount(self, headcount_id: int) -> bool:
        """Delete a headcount record."""
        return await self.repo.delete_headcount(headcount_id)

    async def get_by_id(self, headcount_id: int) -> Optional[HeadCount]:
        """Get headcount record by ID."""
        return await self.repo.get_by_id(headcount_id)

    async def get_by_unit_and_date(
        self, unit_id: str, date: str
    ) -> Optional[HeadCount]:
        """Get headcount record by unit_id and date."""
        return await self.repo.get_by_unit_and_date(unit_id, date)
