"""Headcount repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.schemas.equipment import SubmoduleResponse, SubmoduleSummary

logger = get_logger(__name__)


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

    async def get_headcounts(
        self, unit_id, year, limit, offset, sort_by, sort_order
    ) -> list[HeadCount]:
        """Get headcount record by unit_id and year."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            # HeadCount.year == year,
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(HeadCount, sort_by).asc())
        else:
            statement = statement.order_by(getattr(HeadCount, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_summary_by_submodule(
        self, unit_id: str, year: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregated summary statistics grouped by submodule.

        Args:
            session: Database session
            unit_id: Filter by unit ID
            status: Filter by equipment status

        Returns:
            Dict mapping submodule to summary stats:
            {
                "scientific": {
                    "total_items": 10,
                    "annual_consumption_kwh": 1500.0,
                    "total_kg_co2eq": 187.5
                },
                ...
            }
        """
        # Build query with aggregation
        query = select(
            HeadCount.submodule,
            func.count(col(HeadCount.id)).label("total_items"),
            func.sum(HeadCount.fte).label("annual_fte"),
        ).group_by(HeadCount.submodule)

        # Apply filters
        if unit_id:
            query = query.where(col(HeadCount.unit_id) == unit_id)

        # Execute query
        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dict
        summary: Dict[str, Dict[str, Any]] = {}
        for submodule, total_items, annual_fte in rows:
            summary[submodule] = {
                "total_items": int(total_items),
                "annual_fte": float(annual_fte or 0),
                "annual_consumption_kwh": None,
                "total_kg_co2eq": None,
            }

        logger.debug(f"Retrieved summary for {len(summary)} submodules")

        return summary

    async def get_submodule_data(
        self,
        unit_id: str,
        year: int,
        submodule_key: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> SubmoduleResponse:
        """Get headcount record by unit_id, year, and submodule."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            HeadCount.submodule == submodule_key,
            # HeadCount.year == year,
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(HeadCount, sort_by).asc())
        else:
            statement = statement.order_by(getattr(HeadCount, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        # TODO: complete summary fields
        response = SubmoduleResponse(
            id=submodule_key,
            name=submodule_key,
            count=0,
            items=list(result.scalars().all()),
            summary=SubmoduleSummary(
                total_items=0,
                annual_consumption_kwh=0.0,
                total_kg_co2eq=0.0,
                annual_fte=0.0,
            ),
            has_more=False,
        )
        return response

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
