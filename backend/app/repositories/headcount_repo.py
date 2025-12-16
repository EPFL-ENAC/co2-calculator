"""Headcount repository for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate


class HeadCountRepository:
    """Repository for HeadCount database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_headcount(
        self, data: HeadCountCreate, provider_source: str, user_id: str
    ) -> HeadCount:
        """Create a new headcount record."""
        # 1. Convert Input Model to Table Model
        db_obj = HeadCount.model_validate(data)

        # 2. Add System-Determined Fields
        db_obj.provider = provider_source  # e.g., "csv_upload"
        db_obj.created_by = user_id
        db_obj.updated_by = user_id

        # 3. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update_headcount(
        self, headcount_id: int, data: HeadCountUpdate, user_id: str
    ) -> Optional[HeadCount]:
        """Update an existing headcount record."""
        # 1. Fetch the existing record
        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # 3. Add System-Determined Fields
        db_obj.updated_by = user_id
        db_obj.updated_at = datetime.now(timezone.utc)

        # 4. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete_headcount(self, headcount_id: int) -> bool:
        """Delete a headcount record."""
        # 1. Fetch the existing record
        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return False

        # 2. Delete
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def get_by_id(self, headcount_id: int) -> Optional[HeadCount]:
        """Get headcount record by ID."""
        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_unit_and_date(
        self, unit_id: str, date: str
    ) -> Optional[HeadCount]:
        """Get headcount record by unit_id and date."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            HeadCount.date == date,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
