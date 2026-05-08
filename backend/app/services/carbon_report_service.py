"""Carbon report service for business logic."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportRead,
    CarbonReportUpdate,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.utils.it_breakdown import IT_EMISSION_TYPES

logger = get_logger(__name__)


class CarbonReportService:
    """Service for carbon report business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportRepository(session)
        self.module_service = CarbonReportModuleService(session)

    async def _get_project(
        self, unit_id: int, report_type: CarbonReportType
    ) -> Optional[CarbonProject]:
        """Return the existing CarbonProject for a unit+type, or None.

        Idempotent: never creates or mutates any data.
        """
        stmt = select(CarbonProject).where(
            CarbonProject.unit_id == unit_id,
            CarbonProject.carbon_report_type == report_type,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _create_project(
        self, unit_id: int, report_type: CarbonReportType
    ) -> CarbonProject:
        """Create and flush a new CarbonProject for a unit+type."""
        project = CarbonProject(unit_id=unit_id, carbon_report_type=report_type)
        self.session.add(project)
        await self.session.flush()
        return project

    async def create(self, data: CarbonReportCreate) -> CarbonReportRead:
        """
        Create a new carbon report and auto-create all module records.

        Automatically resolves the Calculator carbon project for the unit
        (creating it if it doesn't yet exist).
        """
        project_id = data.carbon_project_id
        if project_id is None:
            project = await self._get_project(
                data.unit_id, CarbonReportType.CALCULATOR
            ) or await self._create_project(data.unit_id, CarbonReportType.CALCULATOR)
            project_id = project.id
        carbon_report = await self.repo.create(
            data.model_copy(update={"carbon_project_id": project_id})
        )
        carbon_report_read = CarbonReportRead.model_validate(carbon_report)
        await self.module_service.create_all_modules_for_report(carbon_report_read.id)
        return carbon_report_read

    async def get_explore(
        self,
        *,
        unit_id: int,
        reference_year: int,
    ) -> Optional[CarbonReportRead]:
        """Return the existing Simulator Explore report for a unit/year, or None.

        Idempotent: never creates or mutates any data.
        """
        existing = await self.repo.get_explore_by_unit_and_reference_year(
            unit_id=unit_id, reference_year=reference_year
        )
        if existing is None:
            return None
        return CarbonReportRead.model_validate(existing)

    async def create_explore(
        self,
        *,
        unit_id: int,
        reference_year: int,
    ) -> CarbonReportRead:
        """Create a new Simulator Explore report for the given unit and year.

        The explore report uses ``year = reference_year`` (year is always non-null).
        """
        project = await self._get_project(
            unit_id, CarbonReportType.SIMULATOR_EXPLORE
        ) or await self._create_project(unit_id, CarbonReportType.SIMULATOR_EXPLORE)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        created = await self.repo.create(
            CarbonReportCreate(
                unit_id=unit_id,
                year=reference_year,
                reference_year=None,
                carbon_project_id=project.id,
            )
        )
        created.last_updated = now_ts
        await self.session.flush()
        created_read = CarbonReportRead.model_validate(created)
        await self.module_service.create_all_modules_for_report(created_read.id)
        return created_read

    async def bulk_upsert(
        self, data: list[CarbonReportCreate]
    ) -> list[CarbonReportRead]:
        """Bulk upsert carbon reports (Calculator type only).

        Resolves the Calculator project for each unique unit_id before upserting.
        """
        # Resolve project IDs for all unique unit_ids
        unit_project: dict[int, int] = {}
        enriched: list[CarbonReportCreate] = []
        for item in data:
            if item.unit_id not in unit_project:
                project = await self._get_project(
                    item.unit_id, CarbonReportType.CALCULATOR
                ) or await self._create_project(
                    item.unit_id, CarbonReportType.CALCULATOR
                )
                unit_project[item.unit_id] = project.id  # type: ignore[assignment]
            enriched.append(
                item.model_copy(
                    update={"carbon_project_id": unit_project[item.unit_id]}
                )
            )
        carbon_reports = await self.repo.bulk_upsert(enriched)
        return [CarbonReportRead.model_validate(cr) for cr in carbon_reports]

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
        """List all Calculator carbon reports for a unit."""
        carbon_reports = await self.repo.list_by_unit(unit_id)
        return [CarbonReportRead.model_validate(cr) for cr in carbon_reports]

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[CarbonReportRead]:
        """Get a Calculator carbon report by unit and year."""
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
        await self.module_service.delete_all_modules_for_report(carbon_report_id)
        return await self.repo.delete(carbon_report_id)

    async def ensure_modules_for_reports(
        self, carbon_reports: list[CarbonReportRead]
    ) -> None:
        await self.module_service.ensure_modules_for_reports(carbon_reports)

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
        modules = await self.module_service.list_modules(carbon_report_id)

        if not modules:
            logger.warning(
                f"recompute_report_stats: no modules found for report "
                f"{sanitize(carbon_report_id)}, skipping"
            )
            return

        scope1_total = 0.0
        scope2_total = 0.0
        scope3_total = 0.0
        by_emission_type: dict[str, float] = {}
        by_additional_value: dict[str, float] = {}
        total_entry_count = 0

        for module in modules:
            module_stats = module.stats
            if not module_stats:
                continue

            scope1_total += module_stats.get("scope1", 0.0) or 0.0
            scope2_total += module_stats.get("scope2", 0.0) or 0.0
            scope3_total += module_stats.get("scope3", 0.0) or 0.0

            module_by_et = module_stats.get("by_emission_type", {})
            if isinstance(module_by_et, dict):
                for et_id_str, kg_co2eq in module_by_et.items():
                    if kg_co2eq:
                        current = by_emission_type.get(et_id_str, 0.0)
                        by_emission_type[et_id_str] = current + kg_co2eq

            module_by_add = module_stats.get("by_additional_value", {})
            if isinstance(module_by_add, dict):
                for et_id_str, add_val in module_by_add.items():
                    if add_val:
                        current = by_additional_value.get(et_id_str, 0.0)
                        by_additional_value[et_id_str] = current + float(add_val)

            total_entry_count += module_stats.get("entry_count", 0) or 0

        total = scope1_total + scope2_total + scope3_total

        _it_et_id_strs = {str(et.value) for et in IT_EMISSION_TYPES}
        it_total_kg = sum(v for k, v in by_emission_type.items() if k in _it_et_id_strs)

        highest_category_module_id: Optional[int] = None
        highest_category_total = 0.0
        for module in modules:
            if module.status != ModuleStatus.VALIDATED:
                continue
            module_total = module.stats.get("total", 0) if module.stats else 0
            if module_total and module_total > highest_category_total:
                highest_category_total = module_total
                highest_category_module_id = module.module_type_id

        stats = {
            "scope1": scope1_total,
            "scope2": scope2_total,
            "scope3": scope3_total,
            "total": total,
            "it_total_kg": it_total_kg,
            "by_emission_type": by_emission_type,
            "by_additional_value": by_additional_value,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": total_entry_count,
            "highest_category_module_id": highest_category_module_id,
        }

        report = await self.repo.get(carbon_report_id)
        report_id_sanitized = sanitize(carbon_report_id)
        if report:
            report.stats = stats
            report.last_updated = int(datetime.now(timezone.utc).timestamp())
            await self.session.flush()
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

        if completed_modules == 0:
            overall_status = ModuleStatus.NOT_STARTED
        elif completed_modules == total_modules:
            overall_status = ModuleStatus.VALIDATED
        else:
            overall_status = ModuleStatus.IN_PROGRESS

        completion_progress = f"{completed_modules}/{total_modules}"

        report = await self.repo.get(carbon_report_id)
        report_id_sanitized = sanitize(carbon_report_id)
        status_name = ModuleStatus(overall_status).name
        if report:
            report.completion_progress = completion_progress
            report.overall_status = overall_status
            report.last_updated = int(datetime.now(timezone.utc).timestamp())
            await self.session.flush()
            logger.info(
                f"Report progress updated for carbon_report_id={report_id_sanitized}: "
                f"{completion_progress}, status={status_name}"
            )
        else:
            logger.warning(
                f"recompute_report_progress: report {report_id_sanitized} not found"
            )
