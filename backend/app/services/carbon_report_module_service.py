"""CarbonReportModule service for business logic."""

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import (
    ALL_MODULE_TYPE_IDS,
    ModuleTypeEnum,
)
from app.modules.emissions import (
    get_children,
    get_subtree_leaves,
)
from app.modules.emissions.buckets import BucketNodes
from app.modules.emissions.registry import MODULE_STAT_BUCKETS
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.schemas.carbon_report import (
    CarbonReportModuleCreate,
    CarbonReportModuleRead,
    CarbonReportRead,
)

logger = get_logger(__name__)

# Per-module IT top-class detail persisted into module stats:
# stats key, data entry types to group, and the classification field.
_IT_TOP_CLASS_SPECS: dict[ModuleTypeEnum, tuple[str, list[DataEntryTypeEnum], str]] = {
    ModuleTypeEnum.equipment: (
        "equipment_it",
        [DataEntryTypeEnum.it],
        "equipment_class",
    ),
    ModuleTypeEnum.purchase: (
        "purchases_it",
        [DataEntryTypeEnum.it_equipment],
        "purchase_institutional_code",
    ),
    ModuleTypeEnum.research_facilities: (
        "research_facilities_it",
        [
            DataEntryTypeEnum.research_facilities,
            DataEntryTypeEnum.mice_and_fish_animal_facilities,
        ],
        "researchfacility_name",
    ),
}


def _compute_bucket_stats(
    bucket_nodes: BucketNodes,
    leaf_emissions: dict[str, float | None],
    additional_values: dict[str, float | None],
) -> dict:
    """Aggregate one stat bucket from leaf-level DB totals.

    ``by_emission_type`` holds leaf values plus subtree rollups; rollups are
    restricted to the bucket's node set so a split module (buildings) never
    counts an excluded subtree (heating_thermal) in its rooms rollup.
    """
    bucket = bucket_nodes.bucket
    node_values = {node.value for node in bucket_nodes.nodes}
    by_et: dict[str, float] = {}
    by_additional: dict[str, float] = {}
    total_kg = 0.0

    for node in bucket_nodes.nodes:
        key = str(node.value)
        val = leaf_emissions.get(key)
        if val:
            by_et[key] = val
            # Rollup rows persist their subtree sum; counting them again
            # would double the bucket total.
            if node in bucket_nodes.data_nodes:
                total_kg += val
        add_val = additional_values.get(key)
        if add_val:
            by_additional[key] = add_val

    for node in bucket_nodes.nodes:
        if not get_children(node):
            continue
        leaf_ids = [
            leaf_id for leaf_id in get_subtree_leaves(node) if leaf_id in node_values
        ]
        rollup = sum(leaf_emissions.get(str(lid), 0) or 0 for lid in leaf_ids)
        if rollup:
            by_et[str(node.value)] = rollup
        add_rollup = sum(additional_values.get(str(lid), 0) or 0 for lid in leaf_ids)
        if add_rollup:
            by_additional[str(node.value)] = add_rollup

    return {
        "scope": bucket.scope,
        "additional": bucket.additional,
        "total_kg": total_kg,
        "by_emission_type": by_et,
        "by_additional_value": by_additional,
    }


def compute_module_stats(
    leaf_emissions: dict[str, float | None],
    additional_values: dict[str, float | None],
    bucket_nodes: tuple[BucketNodes, ...],
    entry_count: int = 0,
    bucket_extras: dict[str, dict] | None = None,
    module_extras: dict | None = None,
) -> dict:
    """Build the stats dict from leaf-level emission totals.

    Args:
        leaf_emissions: {str(emission_type_id): kg_co2eq} from DB aggregation.
        additional_values: {str(emission_type_id): physical quantity}.
        bucket_nodes: the module's expanded stat buckets.
        entry_count: number of data entries in this module.
        bucket_extras: extra payload merged into a bucket by key (e.g. the
            embodied bucket's by_building detail).
        module_extras: extra top-level payload (e.g. headcount total_fte).

    Returns:
        {"buckets": {...}, "total": kg, "by_emission_type": merged,
         "by_additional_value": merged, "entry_count", "computed_at"}.
        ``total`` sums every bucket (headline behaviour); the per-bucket
        ``additional`` flag carries the informative/organisational split.
    """
    buckets: dict[str, dict] = {}
    merged_et: dict[str, float] = {}
    merged_additional: dict[str, float] = {}
    total_kg = 0.0

    for bn in bucket_nodes:
        bucket_stats = _compute_bucket_stats(bn, leaf_emissions, additional_values)
        extra = (bucket_extras or {}).get(bn.bucket.key)
        if extra:
            bucket_stats.update(extra)
        buckets[bn.bucket.key] = bucket_stats
        merged_et.update(bucket_stats["by_emission_type"])
        merged_additional.update(bucket_stats["by_additional_value"])
        total_kg += bucket_stats["total_kg"]

    return {
        "buckets": buckets,
        "total": total_kg,
        "by_emission_type": merged_et,
        "by_additional_value": merged_additional,
        "entry_count": entry_count,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        **(module_extras or {}),
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
        reports.  Each refreshed module is also marked IN_PROGRESS (data
        changed → prior validation is stale).  Returns the number of
        modules refreshed.
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

        fte_by_module = await self._headcount_fte_by_module(modules)
        year_by_report = await self._years_by_report(modules)

        now_utc = int(datetime.now(timezone.utc).timestamp())
        refreshed = 0
        report_ids: set[int] = set()
        for module in modules:
            if module.id is None:
                continue
            bucket_nodes = MODULE_STAT_BUCKETS.get(
                ModuleTypeEnum(module.module_type_id)
            )
            if not bucket_nodes:
                # Module type has no emission mapping (e.g. global_energy)
                continue
            leaf_emissions, additional_values = pairs.get(module.id, ({}, {}))
            module.stats = compute_module_stats(
                leaf_emissions=leaf_emissions,
                additional_values=additional_values,
                bucket_nodes=bucket_nodes,
                entry_count=counts.get(module.id, 0),
                bucket_extras=await self._collect_bucket_extras(module),
                module_extras=await self._collect_module_extras(
                    module,
                    report_year=year_by_report.get(module.carbon_report_id),
                    fte_by_module=fte_by_module,
                ),
            )
            module.last_updated = now_utc
            # Recomputing means the underlying data changed, so the module is
            # back in progress: any prior validation is now stale. The report
            # rollup below re-derives overall_status from these statuses.
            module.status = ModuleStatus.IN_PROGRESS
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
        """Recompute and persist the stats JSON for a single module.

        Thin wrapper over the set-based :meth:`recompute_stats_many` so the
        single- and many-module paths share one implementation: stats math,
        the IN_PROGRESS status bump, and the report rollup. A missing or
        unmapped module is skipped there (no stats written), matching the
        prior early-return behaviour.
        """
        await self.recompute_stats_many([carbon_report_module_id])

    async def _headcount_fte_by_module(
        self, modules: Sequence[CarbonReportModule]
    ) -> dict[int, float]:
        """Sum FTE per headcount module so its stats carry total_fte."""
        headcount_ids = [
            m.id
            for m in modules
            if m.id is not None and m.module_type_id == ModuleTypeEnum.headcount
        ]
        if not headcount_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    col(DataEntry.carbon_report_module_id),
                    func.sum(DataEntry.data["fte"].as_float()),
                )
                .where(col(DataEntry.carbon_report_module_id).in_(headcount_ids))
                .group_by(col(DataEntry.carbon_report_module_id))
            )
        ).all()
        return {module_id: float(total or 0.0) for module_id, total in rows}

    async def _years_by_report(
        self, modules: Sequence[CarbonReportModule]
    ) -> dict[int, int]:
        report_ids = {m.carbon_report_id for m in modules}
        if not report_ids:
            return {}
        rows = (
            await self.session.execute(
                select(col(CarbonReport.id), col(CarbonReport.year)).where(
                    col(CarbonReport.id).in_(report_ids)
                )
            )
        ).all()
        return {report_id: year for report_id, year in rows}

    async def _collect_bucket_extras(
        self, module: CarbonReportModule
    ) -> dict[str, dict]:
        """Buildings: persist embodied-energy by-building/by-category detail.

        Building names are entry-level data, not derivable from emission
        types, so they are queried once here instead of at read time.
        """
        if module.module_type_id != ModuleTypeEnum.buildings:
            return {}
        emission_repo = DataEntryEmissionRepository(self.session)
        building_rows = await emission_repo.get_embodied_energy_by_building(
            carbon_report_id=module.carbon_report_id
        )
        category_rows = await emission_repo.get_embodied_energy_by_category(
            carbon_report_id=module.carbon_report_id
        )
        return {
            "embodied_energy": {
                "by_building": [
                    {"building_name": name, "kg_co2eq": kg, "tonnes_co2eq": kg / 1000.0}
                    for name, kg in building_rows
                    if kg > 0
                ],
                "by_category": [
                    {"category": cat, "kg_co2eq": kg, "tonnes_co2eq": kg / 1000.0}
                    for cat, kg in category_rows
                    if kg > 0
                ],
            }
        }

    async def _collect_module_extras(
        self,
        module: CarbonReportModule,
        report_year: int | None,
        fte_by_module: dict[int, float],
    ) -> dict:
        if module.module_type_id == ModuleTypeEnum.headcount and module.id is not None:
            return {"total_fte": fte_by_module.get(module.id, 0.0)}
        spec = _IT_TOP_CLASS_SPECS.get(ModuleTypeEnum(module.module_type_id))
        if spec is None or module.id is None:
            return {}
        stats_key, data_entry_types, group_by_field = spec
        emission_repo = DataEntryEmissionRepository(self.session)
        rows = await emission_repo.get_top_class_breakdown(
            carbon_report_module_id=module.id,
            data_entry_types=data_entry_types,
            group_by_field=group_by_field,
            report_year=report_year,
        )
        return {"it_top_classes": {stats_key: rows}}

    async def delete_all_modules_for_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a carbon report. Returns count deleted."""
        return await self.repo.delete_by_report(carbon_report_id)
