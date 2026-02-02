"""CarbonReportModule repository for database operations."""

from typing import List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.module_type import ModuleTypeEnum

logger = get_logger(__name__)


class CarbonReportModuleRepository:
    """Repository for CarbonReportModule database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        carbon_report_id: int,
        module_type_id: int,
        status: int = ModuleStatus.NOT_STARTED,
    ) -> CarbonReportModule:
        """Create a new carbon report module record."""
        db_obj = CarbonReportModule(
            carbon_report_id=carbon_report_id,
            module_type_id=module_type_id,
            status=status,
        )
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def bulk_create(
        self,
        carbon_report_id: int,
        module_type_ids: List[int],
        status: int = ModuleStatus.NOT_STARTED,
    ) -> List[CarbonReportModule]:
        """Create multiple carbon report module records in one transaction."""
        db_objects = [
            CarbonReportModule(
                carbon_report_id=carbon_report_id,
                module_type_id=module_type_id,
                status=status,
            )
            for module_type_id in module_type_ids
        ]
        self.session.add_all(db_objects)
        await self.session.commit()
        for obj in db_objects:
            await self.session.refresh(obj)
        return db_objects

    async def get_by_year_and_unit(
        self, year: int, unit_id: int, module_type_id: ModuleTypeEnum
    ) -> Optional[CarbonReportModule]:
        statement = (
            select(CarbonReportModule)
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReport.year == year,
                CarbonReport.unit_id == unit_id,
                CarbonReportModule.module_type_id == module_type_id,
            )
        )
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def get(self, id: int) -> Optional[CarbonReportModule]:
        """Get a carbon report module by ID."""
        statement = select(CarbonReportModule).where(CarbonReportModule.id == id)
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def get_module_type(self, carbon_report_module_id: int) -> Optional[int]:
        """Get the module type ID for a given carbon report module ID."""
        statement = select(CarbonReportModule.module_type_id).where(
            CarbonReportModule.id == carbon_report_module_id
        )
        result = await self.session.exec(statement)
        row = result.one_or_none()
        if row is not None:
            return row
        return None

    async def get_by_report_and_module_type(
        self, carbon_report_id: int, module_type_id: int
    ) -> Optional[CarbonReportModule]:
        """Get a carbon report module by report ID and module type ID."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id,
            CarbonReportModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_report(self, carbon_report_id: int) -> List[CarbonReportModule]:
        """List all modules for a given carbon report."""
        statement = (
            select(CarbonReportModule)
            .where(CarbonReportModule.carbon_report_id == carbon_report_id)
            .order_by("module_type_id")
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self, carbon_report_id: int, module_type_id: int, status: int
    ) -> Optional[CarbonReportModule]:
        """Update the status of a carbon report module."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id,
            CarbonReportModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        db_obj.status = status
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, carbon_report_module_id: int) -> bool:
        """Delete a carbon report module by ID."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.id == carbon_report_module_id
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def delete_by_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a given carbon report. Returns count deleted."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id
        )
        result = await self.session.execute(statement)
        db_objects = list(result.scalars().all())
        count = len(db_objects)
        for obj in db_objects:
            await self.session.delete(obj)
        await self.session.commit()
        return count
