"""CarbonReportModule service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ALL_MODULE_TYPE_IDS, ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.module_type import ModuleTypeEnum
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report import CarbonReportModuleRead

logger = get_logger(__name__)


class CarbonReportModuleService:
    """Service for carbon report module business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportModuleRepository(session)

    async def create_all_modules_for_report(
        self, carbon_report_id: int
    ) -> List[CarbonReportModuleRead]:
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
        carbon_report_modules = await self.repo.create_bulk(
            carbon_report_id=carbon_report_id,
            module_type_ids=module_type_ids,
            status=ModuleStatus.NOT_STARTED,
        )
        return [
            CarbonReportModuleRead.model_validate(crm) for crm in carbon_report_modules
        ]

    async def get_carbon_report_by_year_and_unit(
        self, year: int, unit_id: int, module_type_id: ModuleTypeEnum
    ) -> CarbonReportModuleRead:
        """Get a carbon report module by year and unit."""
        carbon_report_module = await self.repo.get_by_year_and_unit(
            year, unit_id, module_type_id
        )
        if carbon_report_module is None:
            raise ValueError(
                f"Carbon report module not found for year={year}, "
                f"unit_id={unit_id}, module_type_id={module_type_id}"
            )
        return CarbonReportModuleRead.model_validate(carbon_report_module)

    async def get_module(
        self, carbon_report_id: int, module_type_id: int
    ) -> Optional[CarbonReportModuleRead]:
        """Get a carbon report module by report and module type."""
        carbon_report_module = await self.repo.get_by_report_and_module_type(
            carbon_report_id, module_type_id
        )
        if carbon_report_module is None:
            return None
        return CarbonReportModuleRead.model_validate(carbon_report_module)

    async def list_modules(self, carbon_report_id: int) -> List[CarbonReportModuleRead]:
        """List all modules for a carbon report."""
        carbon_report_modules = await self.repo.list_by_report(carbon_report_id)
        return [
            CarbonReportModuleRead.model_validate(crm) for crm in carbon_report_modules
        ]

    async def update_status(
        self, carbon_report_id: int, module_type_id: int, status: int
    ) -> Optional[CarbonReportModuleRead]:
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
        carbon_report_module = await self.repo.update_status(
            carbon_report_id, module_type_id, status
        )
        if carbon_report_module is None:
            return None
        return CarbonReportModuleRead.model_validate(carbon_report_module)

    async def delete_all_modules_for_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a carbon report. Returns count deleted."""
        return await self.repo.delete_by_report(carbon_report_id)
