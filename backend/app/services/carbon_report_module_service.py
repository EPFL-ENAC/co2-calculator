"""CarbonReportModule service for business logic."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry_emission import (
    EmissionType,
    get_all_nodes,
    get_subtree_leaves,
)
from app.models.module_type import (
    ALL_MODULE_TYPE_IDS,
    MODULE_TYPE_TO_EMISSION_ROOTS,
    ModuleTypeEnum,
)
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.schemas.carbon_report import CarbonReportModuleRead
from app.utils.emission_category import EMISSION_SCOPE

logger = get_logger(__name__)


def compute_module_stats(
    leaf_emissions: dict[str, float | None],
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
            scope = EMISSION_SCOPE.get(node)
            if scope is not None:
                scope_val = scope["scope"] if isinstance(scope, dict) else scope
                scope_totals[f"scope{int(scope_val)}"] += val

    # 2. Compute rollups for non-leaf nodes from their subtree leaves
    for node in all_nodes:
        if node.children():  # non-leaf
            leaf_ids = get_subtree_leaves(node)
            rollup = sum(leaf_emissions.get(str(lid), 0) or 0 for lid in leaf_ids)
            if rollup != 0:
                by_et[str(node.value)] = rollup

    total = scope_totals["scope1"] + scope_totals["scope2"] + scope_totals["scope3"]

    return {
        **scope_totals,
        "total": total,
        "by_emission_type": by_et,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": entry_count,
    }


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
        carbon_report_modules = await self.repo.bulk_create(
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
        leaf_emissions = await emission_repo.get_stats(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by="emission_type_id",
            aggregate_field="kg_co2eq",
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
            emission_roots=emission_roots,
            entry_count=entry_count,
        )

        await self.repo.update_stats(carbon_report_module_id, stats)
        logger.info(
            f"Stats recomputed for module {sanitize(carbon_report_module_id)}: "
            f"total={stats['total']:.2f} kgCO2eq, "
            f"{len(stats['by_emission_type'])} emission types"
        )

        # Trigger parent carbon report stats recomputation
        from app.services.carbon_report_service import CarbonReportService

        report_service = CarbonReportService(self.session)
        await report_service.recompute_report_stats(module.carbon_report_id)

    async def delete_all_modules_for_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a carbon report. Returns count deleted."""
        return await self.repo.delete_by_report(carbon_report_id)
