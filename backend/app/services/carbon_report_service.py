"""Carbon report service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportRead,
    CarbonReportUpdate,
)
from app.services.carbon_report_module_service import CarbonReportModuleService

logger = get_logger(__name__)


class CarbonReportService:
    """Service for carbon report business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportRepository(session)
        self.module_service = CarbonReportModuleService(session)

    async def create(self, data: CarbonReportCreate) -> CarbonReportRead:
        """
        Create a new carbon report and auto-create all module records.

        After creating the report, this automatically creates one
        CarbonReportModule per module type (7 total) with status NOT_STARTED.
        """
        carbon_report = await self.repo.create(data)
        carbon_report_read = CarbonReportRead.model_validate(carbon_report)
        await self.module_service.create_all_modules_for_report(carbon_report_read.id)

        return carbon_report_read

    async def get(self, carbon_report_id: int) -> Optional[CarbonReportRead]:
        """Get a carbon report by ID."""
        carbon_report = await self.repo.get(carbon_report_id)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def list_by_unit(self, unit_id: int) -> List[CarbonReportRead]:
        """List all carbon reports for a unit."""
        carbon_reports = await self.repo.list_by_unit(unit_id)
        return [CarbonReportRead.model_validate(cr) for cr in carbon_reports]

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[CarbonReportRead]:
        """Get a carbon report by unit and year."""
        carbon_report = await self.repo.get_by_unit_and_year(unit_id, year)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def update(
        self, carbon_report_id: int, data: CarbonReportUpdate
    ) -> Optional[CarbonReportRead]:
        """Update a carbon report."""
        carbon_report = await self.repo.update(carbon_report_id, data)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def delete(self, carbon_report_id: int) -> bool:
        """
        Delete a carbon report and all its associated modules.
        """
        # First delete all associated modules
        await self.module_service.delete_all_modules_for_report(carbon_report_id)
        # Then delete the report
        return await self.repo.delete(carbon_report_id)
