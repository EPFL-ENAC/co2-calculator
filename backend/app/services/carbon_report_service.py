"""Carbon report service for business logic."""

from datetime import UTC, datetime

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
    CarbonReportType,
)
from app.modules.emissions.registry import ORDERED_STAT_BUCKETS
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportRead,
    CarbonReportUpdate,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.utils.report_stats import derive_report_sections

logger = get_logger(__name__)


def _merge_module_stats(modules) -> dict:
    """Merge child module stats into ordered report buckets + flat maps."""
    buckets: dict[str, dict] = {}
    by_emission_type: dict[str, float] = {}
    by_additional_value: dict[str, float] = {}
    it_top_classes: dict[str, list] = {}
    total_kg = 0.0
    total_fte = 0.0
    total_entry_count = 0

    stats_by_module_type = {
        module.module_type_id: module.stats
        for module in modules
        if isinstance(module.stats, dict)
    }
    for module_type, bucket_nodes in ORDERED_STAT_BUCKETS:
        module_stats = stats_by_module_type.get(module_type.value)
        if not module_stats:
            continue
        bucket = module_stats.get("buckets", {}).get(bucket_nodes.bucket.key)
        if bucket is None:
            continue
        buckets[bucket_nodes.bucket.key] = bucket
        total_kg += bucket.get("total_kg", 0.0) or 0.0
        for et_id_str, kg in bucket.get("by_emission_type", {}).items():
            by_emission_type[et_id_str] = by_emission_type.get(et_id_str, 0.0) + kg
        for et_id_str, add_val in bucket.get("by_additional_value", {}).items():
            by_additional_value[et_id_str] = by_additional_value.get(
                et_id_str, 0.0
            ) + float(add_val)

    for module_stats in stats_by_module_type.values():
        total_fte += module_stats.get("total_fte", 0.0) or 0.0
        total_entry_count += module_stats.get("entry_count", 0) or 0
        it_top_classes.update(module_stats.get("it_top_classes", {}))

    return {
        "buckets": buckets,
        "by_emission_type": by_emission_type,
        "by_additional_value": by_additional_value,
        "it_top_classes": it_top_classes,
        "total": total_kg,
        "total_fte": total_fte,
        "entry_count": total_entry_count,
    }


def _build_report_stats(modules, is_simulator: bool = False) -> dict:
    """Aggregate a report's stats JSON from its modules' stats dicts.

    Pure function shared by the single-report and batched recompute paths;
    ``modules`` only needs ``.stats``, ``.status`` and ``.module_type_id``
    attributes. Neither simulator report type has a validation step, so every
    module counts as validated there.
    """
    merged = _merge_module_stats(modules)
    buckets: dict[str, dict] = merged["buckets"]
    total_kg: float = merged["total"]
    total_fte: float = merged["total_fte"]

    validated_module_type_ids = {
        module.module_type_id
        for module in modules
        if is_simulator or module.status == ModuleStatus.VALIDATED
    }
    validated_buckets = [
        bucket_nodes.bucket.key
        for module_type, bucket_nodes in ORDERED_STAT_BUCKETS
        if module_type.value in validated_module_type_ids
        and bucket_nodes.bucket.key in buckets
    ]
    validated_total_kg = sum(
        (module.stats or {}).get("total", 0.0) or 0.0
        for module in modules
        if module.module_type_id in validated_module_type_ids
    )

    derived = derive_report_sections(
        buckets,
        merged["by_emission_type"],
        total_kg,
        total_fte,
        top_class_detail=merged["it_top_classes"],
        validated_buckets=validated_buckets,
    )

    highest_category_module_id: int | None = None
    highest_category_total = 0.0
    for module in modules:
        if module.module_type_id not in validated_module_type_ids:
            continue
        module_total = module.stats.get("total", 0) if module.stats else 0
        if module_total and module_total > highest_category_total:
            highest_category_total = module_total
            highest_category_module_id = module.module_type_id

    return {
        "buckets": buckets,
        "validated_buckets": validated_buckets,
        **derived,
        "total": total_kg,
        "validated_total": validated_total_kg,
        "total_fte": total_fte,
        "by_emission_type": merged["by_emission_type"],
        "by_additional_value": merged["by_additional_value"],
        "computed_at": datetime.now(UTC).isoformat(),
        "entry_count": merged["entry_count"],
        "highest_category_module_id": highest_category_module_id,
    }


def _build_report_progress(modules) -> tuple[str, ModuleStatus]:
    """Derive (completion_progress, overall_status) from a module list."""
    total_modules = len(modules)
    completed_modules = sum(1 for m in modules if m.status == ModuleStatus.VALIDATED)
    if completed_modules == 0:
        overall_status = ModuleStatus.NOT_STARTED
    elif completed_modules == total_modules:
        overall_status = ModuleStatus.VALIDATED
    else:
        overall_status = ModuleStatus.IN_PROGRESS
    return f"{completed_modules}/{total_modules}", overall_status


class CarbonReportService:
    """Service for carbon report business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportRepository(session)
        self.module_service = CarbonReportModuleService(session)

    async def _get_project(
        self, unit_id: int, report_type: CarbonReportType
    ) -> CarbonProject | None:
        """Return the existing CarbonProject for a unit+type, or None.

        Idempotent: never creates or mutates any data.

        Must not be called with SIMULATOR_PLAN: a unit can have many plan
        projects, so ``scalar_one_or_none`` would raise MultipleResultsFound.
        Use :class:`app.services.simulator_plan_service.SimulatorPlanService`
        for plans.
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
        """Create a new carbon report and auto-create all module records.

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

    async def set_budget(
        self,
        carbon_report_id: int,
        budget: float | None,
        budget_currency: str | None,
    ) -> CarbonReportRead | None:
        """Set a Project Grant report's total budget (#1978); None if missing."""
        report = await self.repo.get(carbon_report_id)
        if report is None:
            return None
        report.budget = budget
        report.budget_currency = budget_currency
        self.session.add(report)
        await self.session.flush()
        return CarbonReportRead.model_validate(report)

    async def get_explore(
        self,
        *,
        unit_id: int,
        reference_year: int,
    ) -> CarbonReportRead | None:
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
        now_ts = int(datetime.now(UTC).timestamp())
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
                if project.id is None:
                    raise ValueError("project must be persisted before use")
                unit_project[item.unit_id] = project.id
            enriched.append(
                item.model_copy(
                    update={"carbon_project_id": unit_project[item.unit_id]}
                )
            )
        carbon_reports = await self.repo.bulk_upsert(enriched)
        return [CarbonReportRead.model_validate(cr) for cr in carbon_reports]

    async def get(self, carbon_report_id: int) -> CarbonReportRead | None:
        """Get a carbon report by ID."""
        carbon_report = await self.repo.get(carbon_report_id)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def get_reporting_overview(self, args) -> list[CarbonReportRead]:
        results = await self.repo.get_reporting_overview(*args)
        return [CarbonReportRead.model_validate(cr) for cr in results]

    async def list_by_unit(self, unit_id: int) -> list[CarbonReportRead]:
        """List all Calculator carbon reports for a unit."""
        carbon_reports = await self.repo.list_by_unit(unit_id)
        return [CarbonReportRead.model_validate(cr) for cr in carbon_reports]

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> CarbonReportRead | None:
        """Get a Calculator carbon report by unit and year."""
        carbon_report = await self.repo.get_by_unit_and_year(unit_id, year)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def update(
        self, carbon_report_id: int, data: CarbonReportUpdate
    ) -> CarbonReportRead | None:
        """Update a carbon report."""
        carbon_report = await self.repo.update(carbon_report_id, data)
        if carbon_report is None:
            return None
        return CarbonReportRead.model_validate(carbon_report)

    async def delete(self, carbon_report_id: int) -> bool:
        """Delete a carbon report and all its associated modules."""
        await self.module_service.delete_all_modules_for_report(carbon_report_id)
        return await self.repo.delete(carbon_report_id)

    async def ensure_modules_for_reports(
        self, carbon_reports: list[CarbonReportRead]
    ) -> None:
        await self.module_service.ensure_modules_for_reports(carbon_reports)

    async def recompute_report_stats(self, carbon_report_id: int) -> None:
        """Recompute and persist the aggregated stats JSON for a carbon report.

        Aggregates child ``CarbonReportModule`` stats (scope sums, merged
        ``by_emission_type``, entry counts) and refreshes the report's
        ``completion_progress`` / ``overall_status``.  Thin wrapper over the
        set-based :meth:`recompute_report_stats_many` so the single- and
        many-report paths share one implementation.
        """
        await self.recompute_report_stats_many([carbon_report_id])

    async def recompute_report_stats_many(self, carbon_report_ids: list[int]) -> None:
        """Batched report rollup for the aggregation job.

        Two SELECTs (all child modules, all reports) + one flush for the
        whole set, instead of ~4 queries + 2 flushes per report.  Applies
        the same stats AND progress derivations as the single-report
        functions, from one module load.
        """
        if not carbon_report_ids:
            return
        modules_by_report: dict[int, list[CarbonReportModule]] = {}
        module_rows = (
            (
                await self.session.execute(
                    select(CarbonReportModule).where(
                        col(CarbonReportModule.carbon_report_id).in_(carbon_report_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        for m in module_rows:
            modules_by_report.setdefault(m.carbon_report_id, []).append(m)
        reports = (
            (
                await self.session.execute(
                    select(CarbonReport).where(
                        col(CarbonReport.id).in_(carbon_report_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        type_rows = (
            await self.session.execute(
                select(col(CarbonReport.id), col(CarbonProject.carbon_report_type))
                .join(
                    CarbonProject,
                    col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
                )
                .where(col(CarbonReport.id).in_(carbon_report_ids))
            )
        ).all()
        report_types: dict[int, CarbonReportType] = {
            report_id: report_type for report_id, report_type in type_rows
        }

        now_ts = int(datetime.now(UTC).timestamp())
        updated = 0
        for report in reports:
            modules = modules_by_report.get(report.id or -1)
            if not modules:
                logger.warning(
                    f"recompute_report_stats_many: no modules for report "
                    f"{sanitize(report.id)}, skipping"
                )
                continue
            # Inactive modules (Simulator Plan 'Active' checkbox off) are
            # excluded from sums, stats and completion alike.
            active_modules = [m for m in modules if m.is_active]
            report.stats = _build_report_stats(
                active_modules,
                is_simulator=report_types.get(report.id)
                in (
                    CarbonReportType.SIMULATOR_EXPLORE,
                    CarbonReportType.SIMULATOR_PLAN,
                ),
            )
            progress, status = _build_report_progress(active_modules)
            report.completion_progress = progress
            report.overall_status = status
            report.last_updated = now_ts
            self.session.add(report)
            updated += 1
        await self.session.flush()
        logger.info(
            f"Report stats recomputed for {updated}/{len(carbon_report_ids)} "
            "report(s) (batched)"
        )

    async def recompute_report_progress(self, carbon_report_id: int) -> None:
        """Recompute completion_progress and overall_status for a carbon report.

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

        # Inactive modules are excluded from completion, matching the
        # stats recompute path.
        completion_progress, overall_status = _build_report_progress(
            [m for m in modules if m.is_active]
        )

        report = await self.repo.get(carbon_report_id)
        report_id_sanitized = sanitize(carbon_report_id)
        status_name = ModuleStatus(overall_status).name
        if report:
            report.completion_progress = completion_progress
            report.overall_status = overall_status
            report.last_updated = int(datetime.now(UTC).timestamp())
            await self.session.flush()
            logger.info(
                f"Report progress updated for carbon_report_id={report_id_sanitized}: "
                f"{completion_progress}, status={status_name}"
            )
        else:
            logger.warning(
                f"recompute_report_progress: report {report_id_sanitized} not found"
            )
