"""CarbonReportModule service for business logic."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import (
    EmissionType,
    get_all_nodes,
    get_children,
    get_subtree_leaves,
)
from app.models.module_type import (
    ALL_MODULE_TYPE_IDS,
    MODULE_TYPE_TO_EMISSION_ROOTS,
    ModuleTypeEnum,
)
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.schemas.carbon_report import (
    CarbonReportModuleCreate,
    CarbonReportModuleRead,
    CarbonReportRead,
)

logger = get_logger(__name__)


def compute_module_stats(
    leaf_emissions: dict[str, float | None],
    additional_values: dict[str, float | None],
    emission_roots: list[EmissionType],
    entry_count: int = 0,
) -> dict:
    """Build the stats dict from leaf-level emission totals.

    Args:
        leaf_emissions: {str(emission_type_id): kg_co2eq} from DB aggregation.
        emission_roots: EmissionType roots for this module.
        entry_count: Number of data entries in this module.

    Returns:
        Stats dict with scope totals, by_emission_type (leaves + rollups),
        computed_at, and entry_count.
    """
    by_et: dict[str, float] = {}
    by_additional: dict[str, float] = {}
    scope_totals: dict[str, float] = {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0}

    # Collect all nodes across all roots for this module
    all_nodes: list[EmissionType] = []
    for root in emission_roots:
        all_nodes.extend(get_all_nodes(root))

    # 1. Populate leaf values from DB results + accumulate scope totals
    for node in all_nodes:
        val = leaf_emissions.get(str(node.value))
        if val is not None and val != 0:
            by_et[str(node.value)] = val
            # Scope totals only for actual leaves (data rows)
            if node.scope is not None:
                scope_totals[f"scope{int(node.scope)}"] += val
        add_val = additional_values.get(str(node.value))
        if add_val is not None and add_val != 0:
            by_additional[str(node.value)] = add_val

    # 2. Compute rollups for non-leaf nodes from their subtree leaves
    for node in all_nodes:
        if get_children(node):  # non-leaf
            leaf_ids = get_subtree_leaves(node)
            rollup = sum(leaf_emissions.get(str(lid), 0) or 0 for lid in leaf_ids)
            if rollup != 0:
                by_et[str(node.value)] = rollup
            add_rollup = sum(
                additional_values.get(str(lid), 0) or 0 for lid in leaf_ids
            )
            if add_rollup != 0:
                by_additional[str(node.value)] = add_rollup

    total = scope_totals["scope1"] + scope_totals["scope2"] + scope_totals["scope3"]

    return {
        **scope_totals,
        "total": total,
        "by_emission_type": by_et,
        "by_additional_value": by_additional,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": entry_count,
    }


class CarbonReportModuleService:
    """Service for carbon report module business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonReportModuleRepository(session)

    async def bulk_create(
        self, carbon_reports: list[CarbonReportRead]
    ) -> list[CarbonReportModule]:
        carbon_report_modules_to_create = [
            CarbonReportModuleCreate(
                carbon_report_id=cr.id,
                module_type_id=int(mt),
                status=ModuleStatus.NOT_STARTED,
            )
            for cr in carbon_reports
            for mt in ALL_MODULE_TYPE_IDS
        ]
        return await self.repo.bulk_create(carbon_report_modules_to_create)

    async def ensure_modules_for_reports(
        self, carbon_reports: list[CarbonReportRead]
    ) -> None:
        for cr in carbon_reports:
            existing = await self.repo.list_by_report(cr.id)
            existing_types = {m.module_type_id for m in existing}
            missing_types = [
                mt for mt in ALL_MODULE_TYPE_IDS if mt not in existing_types
            ]
            if not missing_types:
                continue
            carbon_report_modules_to_create = [
                CarbonReportModuleCreate(
                    carbon_report_id=cr.id,
                    module_type_id=int(mt),
                    status=ModuleStatus.NOT_STARTED,
                )
                for mt in missing_types
            ]
            await self.repo.bulk_create(carbon_report_modules_to_create)

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
        carbon_report_modules = (
            await self.repo.bulk_create_carbon_report_modules_of_carbon_report(
                carbon_report_id=carbon_report_id,
                module_type_ids=module_type_ids,
                status=ModuleStatus.NOT_STARTED,
            )
        )
        return [
            CarbonReportModuleRead.model_validate(crm) for crm in carbon_report_modules
        ]

    async def get_carbon_report_by_year_and_unit(
        self,
        year: int,
        unit_id: int,
        module_type_id: ModuleTypeEnum,
        *,
        report_type: CarbonReportType = CarbonReportType.CALCULATOR,
    ) -> CarbonReportModuleRead:
        """Get a carbon report module by year and unit.

        Args:
            year: Report year to look up.
            unit_id: Unit ID to filter by.
            module_type_id: Module type to retrieve.
            report_type: The CarbonReportType to resolve against (CALCULATOR,
                SIMULATOR_EXPLORE, or SIMULATOR_PLAN). Derived from the
                ``?carbon_project_type`` query parameter by the caller.

        Returns:
            The matching CarbonReportModuleRead.

        Raises:
            ValueError: If no matching module is found.
        """
        carbon_report_module = await self.repo.get_by_year_and_unit(
            year, unit_id, module_type_id, report_type=report_type
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

    async def list_modules(
        self,
        carbon_report_id: int,
    ) -> List[CarbonReportModuleRead]:
        """List all modules for a carbon report.

        Plan 310-D / Issue #1062 — ``current_pipeline_id`` enrichment
        moved to the dedicated ``GET /v1/sync/active-pipelines``
        endpoint consumed by the frontend ``pipelineStateStore``.
        """
        carbon_report_modules = await self.repo.list_by_report(carbon_report_id)
        return [
            CarbonReportModuleRead.model_validate(crm) for crm in carbon_report_modules
        ]

    async def list_modules_for(
        self, module_type_id: int, year: int
    ) -> List[CarbonReportModule]:
        """Return all CarbonReportModule rows for a (module_type_id, year) slice.

        Used by the Plan 310-D ``aggregation`` handler to identify which
        modules need their stats recomputed after a bulk recalc / ingest
        pipeline writes new emissions for that scope.
        """
        return await self.repo.list_by_module_type_and_year(
            module_type_id=module_type_id, year=year
        )

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

    async def recompute_stats_many(self, carbon_report_module_ids: list[int]) -> int:
        """Set-based stats recompute for the aggregation job.

        Replaces N sequential ``recompute_stats`` calls (~8 queries per
        module) with: 1 module load, 1 grouped emissions query, 1 grouped
        entry-count query, then one batched report rollup
        (``recompute_report_stats_many``) over the distinct parent
        reports.  Returns the number of modules refreshed.
        """
        if not carbon_report_module_ids:
            return 0
        # Local import mirrors ``recompute_stats`` below — top-level would
        # be circular (CarbonReportService imports this module).
        from app.services.carbon_report_service import CarbonReportService

        modules = (
            (
                await self.session.execute(
                    select(CarbonReportModule).where(
                        col(CarbonReportModule.id).in_(carbon_report_module_ids)
                    )
                )
            )
            .scalars()
            .all()
        )

        emission_repo = DataEntryEmissionRepository(self.session)
        pairs = await emission_repo.get_stats_pair_many(carbon_report_module_ids)

        count_rows = (
            await self.session.execute(
                select(
                    col(DataEntry.carbon_report_module_id),
                    func.count(),
                )
                .where(
                    col(DataEntry.carbon_report_module_id).in_(carbon_report_module_ids)
                )
                .group_by(col(DataEntry.carbon_report_module_id))
            )
        ).all()
        counts = {module_id: count for module_id, count in count_rows}

        now_utc = int(datetime.now(timezone.utc).timestamp())
        refreshed = 0
        report_ids: set[int] = set()
        for module in modules:
            if module.id is None:
                continue
            emission_roots = MODULE_TYPE_TO_EMISSION_ROOTS.get(
                ModuleTypeEnum(module.module_type_id)
            )
            if not emission_roots:
                # Module type has no emission mapping (e.g. global_energy)
                continue
            leaf_emissions, additional_values = pairs.get(module.id, ({}, {}))
            module.stats = compute_module_stats(
                leaf_emissions=leaf_emissions,
                additional_values=additional_values,
                emission_roots=emission_roots,
                entry_count=counts.get(module.id, 0),
            )
            module.last_updated = now_utc
            self.session.add(module)
            report_ids.add(module.carbon_report_id)
            refreshed += 1
        await self.session.flush()
        logger.info(
            f"Stats recomputed for {refreshed} module(s) (batched), "
            f"{len(report_ids)} report rollup(s) pending"
        )

        report_service = CarbonReportService(self.session)
        await report_service.recompute_report_stats_many(sorted(report_ids))
        return refreshed

    async def recompute_stats(self, carbon_report_module_id: int) -> None:
        """Recompute and persist the stats JSON for a module."""
        module = await self.repo.get(carbon_report_module_id)
        if module is None:
            logger.warning(
                f"recompute_stats: module {sanitize(carbon_report_module_id)} "
                "not found, skipping"
            )
            return

        emission_roots = MODULE_TYPE_TO_EMISSION_ROOTS.get(
            ModuleTypeEnum(module.module_type_id)
        )
        if not emission_roots:
            # Module type has no emission mapping (e.g. global_energy)
            return

        emission_repo = DataEntryEmissionRepository(self.session)
        leaf_emissions, additional_values = await emission_repo.get_stats_pair(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by="emission_type_id",
            primary_field="kg_co2eq",
            secondary_field="additional_value",
        )

        # entry_count: count data entries for this module
        from sqlmodel import func, select

        from app.models.data_entry import DataEntry

        result = await self.session.execute(
            select(func.count()).where(
                DataEntry.carbon_report_module_id == carbon_report_module_id
            )
        )
        entry_count = result.scalar_one()

        stats = compute_module_stats(
            leaf_emissions=leaf_emissions,
            additional_values=additional_values,
            emission_roots=emission_roots,
            entry_count=entry_count,
        )

        await self.repo.update_stats(carbon_report_module_id, stats)

        now_utc = int(datetime.now(timezone.utc).timestamp())
        module.last_updated = now_utc
        self.session.add(module)

        logger.info(
            f"Stats recomputed for module {sanitize(carbon_report_module_id)}: "
            f"total={stats['total']:.2f} kgCO2eq, "
            f"{len(stats['by_emission_type'])} emission types, "
            f"last_updated={now_utc}"
        )

        from app.services.carbon_report_service import CarbonReportService

        report_service = CarbonReportService(self.session)
        await report_service.recompute_report_stats(module.carbon_report_id)

    async def delete_all_modules_for_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a carbon report. Returns count deleted."""
        return await self.repo.delete_by_report(carbon_report_id)
