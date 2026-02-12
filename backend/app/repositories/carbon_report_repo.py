"""Carbon report repository for database operations."""

from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate

logger = get_logger(__name__)


class CarbonReportRepository:
    """Repository for CarbonReport database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CarbonReportCreate) -> CarbonReport:
        """Create a new carbon report."""
        db_obj = CarbonReport.model_validate(data.model_dump())
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def get(self, carbon_report_id: int) -> Optional[CarbonReport]:
        """Get a carbon report by ID."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_unit(self, unit_id: int) -> list[CarbonReport]:
        """List all carbon reports for a unit."""
        statement = select(CarbonReport).where(CarbonReport.unit_id == unit_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[CarbonReport]:
        """Get a carbon report by unit and year."""
        statement = select(CarbonReport).where(
            (CarbonReport.unit_id == unit_id) & (CarbonReport.year == year)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(
        self, carbon_report_id: int, data: CarbonReportUpdate
    ) -> Optional[CarbonReport]:
        """Update a carbon report."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, carbon_report_id: int) -> bool:
        """Delete a carbon report."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.flush()
        return True
