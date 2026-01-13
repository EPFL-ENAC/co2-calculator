"""Carbon report service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate
from app.services.carbon_report_module_service import CarbonReportModuleService

logger = get_logger(__name__)


class CarbonReportService:
    """Service for carbon report business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportRepository(session)
        self.module_service = CarbonReportModuleService(session)

    async def create(self, data: CarbonReportCreate) -> CarbonReport:
        """
        Create a new carbon report and auto-create all module records.

        After creating the report, this automatically creates one
        CarbonReportModule per module type (7 total) with status NOT_STARTED.
        """
        report = await self.repo.create(data)
        logger.info(
            f"Created carbon report {sanitize(report.id)} for unit "
            f"{sanitize(data.unit_id)} year {sanitize(data.year)}"
        )

        # Auto-create all carbon report modules with default status
        assert report.id is not None
        await self.module_service.create_all_modules_for_report(report.id)

        return report

    async def get(self, carbon_report_id: int) -> Optional[CarbonReport]:
        """Get a carbon report by ID."""
        return await self.repo.get(carbon_report_id)

    async def list_by_unit(self, unit_id: int) -> List[CarbonReport]:
        """List all carbon reports for a unit."""
        return await self.repo.list_by_unit(unit_id)

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[CarbonReport]:
        """Get a carbon report by unit and year."""
        return await self.repo.get_by_unit_and_year(unit_id, year)

    async def update(
        self, carbon_report_id: int, data: CarbonReportUpdate
    ) -> Optional[CarbonReport]:
        """Update a carbon report."""
        return await self.repo.update(carbon_report_id, data)

    async def delete(self, carbon_report_id: int) -> bool:
        """
        Delete a carbon report and all its associated modules.
        """
        # First delete all associated modules
        await self.module_service.delete_all_modules_for_report(carbon_report_id)
        # Then delete the report
        return await self.repo.delete(carbon_report_id)
