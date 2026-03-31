"""Carbon report service for business logic."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
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

    async def get_reporting_overview(self, args) -> list[CarbonReportRead]:
        results = await self.repo.get_reporting_overview(*args)
        return [CarbonReportRead.model_validate(cr) for cr in results]

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

    async def recompute_report_stats(self, carbon_report_id: int) -> None:
        """
        Recompute and persist the aggregated stats JSON for a carbon report.

        Aggregates stats from all child CarbonReportModule records:
        - Sum scope1, scope2, scope3, total across all modules
        - Merge by_emission_type dicts (grouping by emission_type_id)
        - Sum entry_count across all modules
        - Update computed_at timestamp

        Args:
            carbon_report_id: The carbon report ID to recompute stats for
        """
        # Get all modules for this report
        modules = await self.module_service.list_modules(carbon_report_id)

        if not modules:
            logger.warning(
                f"recompute_report_stats: no modules found for report "
                f"{sanitize(carbon_report_id)}, skipping"
            )
            return

        # Aggregate stats across all modules
        scope1_total = 0.0
        scope2_total = 0.0
        scope3_total = 0.0
        by_emission_type: dict[str, float] = {}
        total_entry_count = 0

        for module in modules:
            module_stats = module.stats
            if not module_stats:
                continue

            # Sum scope totals
            scope1_total += module_stats.get("scope1", 0.0) or 0.0
            scope2_total += module_stats.get("scope2", 0.0) or 0.0
            scope3_total += module_stats.get("scope3", 0.0) or 0.0

            # Merge by_emission_type
            module_by_et = module_stats.get("by_emission_type", {})
            if isinstance(module_by_et, dict):
                for et_id_str, kg_co2eq in module_by_et.items():
                    if kg_co2eq:
                        current = by_emission_type.get(et_id_str, 0.0)
                        by_emission_type[et_id_str] = current + kg_co2eq

            # Sum entry counts
            total_entry_count += module_stats.get("entry_count", 0) or 0

        # Calculate grand total
        total = scope1_total + scope2_total + scope3_total

        # Build aggregated stats dict
        stats = {
            "scope1": scope1_total,
            "scope2": scope2_total,
            "scope3": scope3_total,
            "total": total,
            "by_emission_type": by_emission_type,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": total_entry_count,
        }

        # Update carbon_report with aggregated stats and progress
        report = await self.repo.get(carbon_report_id)
        report_id_sanitized = sanitize(carbon_report_id)
        if report:
            report.stats = stats
            await self.session.flush()
            # Also recompute progress and overall status
            await self.recompute_report_progress(carbon_report_id)
            logger.info(
                f"Report stats recomputed for carbon_report_id={report_id_sanitized}: "
                f"total={total:.2f} kgCO2eq, "
                f"{len(by_emission_type)} emission types, "
                f"{total_entry_count} entries"
            )
        else:
            logger.warning(
                f"recompute_report_stats: report {report_id_sanitized} not found"
            )

    async def recompute_report_progress(self, carbon_report_id: int) -> None:
        """
        Recompute completion_progress and overall_status for a carbon report.

        completion_progress: String like '5/7' showing completed modules vs total
        overall_status: Inferred from child modules:
            - NOT_STARTED (0): No modules started
            - IN_PROGRESS (1): Some modules started but not all validated
            - VALIDATED (2): All modules validated

        Args:
            carbon_report_id: The carbon report ID to update
        """
        # Get all modules for this report
        modules = await self.module_service.list_modules(carbon_report_id)

        if not modules:
            logger.warning(
                f"recompute_report_progress: no modules found for report "
                f"{sanitize(carbon_report_id)}, skipping"
            )
            return

        total_modules = len(modules)
        completed_modules = sum(
            1 for m in modules if m.status == ModuleStatus.VALIDATED
        )

        # Determine overall status
        if completed_modules == 0:
            overall_status = ModuleStatus.NOT_STARTED
        elif completed_modules == total_modules:
            overall_status = ModuleStatus.VALIDATED
        else:
            overall_status = ModuleStatus.IN_PROGRESS

        # Build completion progress string
        completion_progress = f"{completed_modules}/{total_modules}"

        # Update carbon_report
        report = await self.repo.get(carbon_report_id)
        report_id_sanitized = sanitize(carbon_report_id)
        status_name = ModuleStatus(overall_status).name
        if report:
            report.completion_progress = completion_progress
            report.overall_status = overall_status
            await self.session.flush()
            logger.info(
                f"Report progress updated for carbon_report_id={report_id_sanitized}: "
                f"{completion_progress}, status={status_name}"
            )
        else:
            logger.warning(
                f"recompute_report_progress: report {report_id_sanitized} not found"
            )
