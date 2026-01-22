"""CarbonReportModule service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ALL_MODULE_TYPE_IDS, ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReportModule
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository

logger = get_logger(__name__)


class CarbonReportModuleService:
    """Service for carbon report module business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportModuleRepository(session)

    async def create_all_modules_for_report(
        self, carbon_report_id: int
    ) -> List[CarbonReportModule]:
        """
        Create all module records for a new carbon report.

        Creates one CarbonReportModule per module type (7 total) with
        status NOT_STARTED.
        This is called automatically when a new carbon report is created.
        """
        module_type_ids = [int(mt) for mt in ALL_MODULE_TYPE_IDS]
        logger.info(
            f"Creating {sanitize(len(module_type_ids))} report modules "
            f"for carbon report {sanitize(carbon_report_id)}"
        )
        return await self.repo.create_bulk(
            carbon_report_id=carbon_report_id,
            module_type_ids=module_type_ids,
            status=ModuleStatus.NOT_STARTED,
        )

    async def get_module(
        self, carbon_report_id: int, module_type_id: int
    ) -> Optional[CarbonReportModule]:
        """Get a carbon report module by report and module type."""
        return await self.repo.get_by_report_and_module_type(
            carbon_report_id, module_type_id
        )

    async def list_modules(self, carbon_report_id: int) -> List[CarbonReportModule]:
        """List all modules for a carbon report."""
        return await self.repo.list_by_report(carbon_report_id)

    async def update_status(
        self, carbon_report_id: int, module_type_id: int, status: int
    ) -> Optional[CarbonReportModule]:
        """
        Update the status of a carbon report module.

        Args:
            carbon_report_id: The carbon report ID
            module_type_id: The module type ID (1-7)
            status: The new status (0=not_started, 1=in_progress, 2=validated)

        Returns:
            The updated CarbonReportModule or None if not found
        """
        # Validate status value
        if status not in [s.value for s in ModuleStatus]:
            raise ValueError(
                f"Invalid status {status}. Must be one of: "
                f"{[s.value for s in ModuleStatus]}"
            )

        logger.info(
            f"Updating report {sanitize(carbon_report_id)} module "
            f"status to {sanitize(ModuleStatus(status).name)}"
        )
        return await self.repo.update_status(carbon_report_id, module_type_id, status)

    async def delete_all_modules_for_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a carbon report. Returns count deleted."""
        return await self.repo.delete_by_report(carbon_report_id)
