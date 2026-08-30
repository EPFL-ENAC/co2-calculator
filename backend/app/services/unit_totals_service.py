"""Service for calculating unit-wide totals across all modules."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.utils.report_computations import ModuleStatsRow

logger = get_logger(__name__)


def _fold_results_summary(
    rows: list[ModuleStatsRow], current_ids: set[int]
) -> dict[str, dict[str, float]]:
    """Split validated module stats into current-year and previous-year sums.

    Unlike ``fold_validated_totals``, a validated module keeps its key even
    when its total is 0.0 — that key set is what ``compute_results_summary``
    turns into per-module rows, so dropping it would silently shrink the
    response.
    """
    current_emissions: dict[str, float] = {}
    current_fte: dict[str, float] = {}
    prev_emissions: dict[str, float] = {}
    for report_id, module_type_id, module_status, stats, _report_type in rows:
        if module_status != ModuleStatus.VALIDATED:
            continue
        module_stats = stats if isinstance(stats, dict) else {}
        key = str(module_type_id)
        is_current = report_id in current_ids
        target = current_emissions if is_current else prev_emissions
        target[key] = target.get(key, 0.0) + (module_stats.get("total", 0.0) or 0.0)
        if is_current and module_stats.get("total_fte"):
            current_fte[key] = current_fte.get(key, 0.0) + module_stats["total_fte"]
    return {
        "current_emissions": current_emissions,
        "current_fte": current_fte,
        "prev_emissions": prev_emissions,
    }


class UnitTotalsService:
    """Service for calculating unit-wide carbon footprint totals."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_validated_emissions_by_unit(self, unit_id: int) -> list[dict]:
        """Get validated emission totals per year for a unit.

        Returns:
            [{"year": 2023, "kg_co2eq": 61700.0}, ...]
        """
        return await DataEntryEmissionRepository(
            self.session
        ).get_validated_totals_by_unit(unit_id=unit_id)

    async def get_merged_results_summary(
        self, reports: list[CarbonReport], year: int
    ) -> dict:
        """Results-summary inputs summed over several reports of one year.

        Two statements whatever the report count (#2527 task 4): the same
        units' previous-year reports in one query, then every module row of
        both years in one more. Each unit therefore contributes its own
        comparison basis, as the per-report loop this replaces did.
        """
        repo = CarbonReportRepository(self.session)
        unit_ids = sorted({report.unit_id for report in reports})
        prev_reports = await repo.list_by_units(unit_ids, year - 1)
        current_ids = [r.id for r in reports if r.id is not None]
        prev_ids = [r.id for r in prev_reports if r.id is not None]
        rows = await repo.module_stats_by_report(current_ids + prev_ids)
        return _fold_results_summary(rows, set(current_ids))

    async def get_results_summary(self, carbon_report_id: int) -> dict:
        """Fetch per-module emission and FTE totals for a carbon report.

        Thin read over the persisted ``carbon_report_module.stats`` of the
        current and previous-year reports (previous-year data can change
        after this report's recompute, so it is read fresh here).

        Returns:
            Dict with raw data for the endpoint to format:
            - current_emissions: {module_type_id_str: kg_co2eq}
            - current_fte: {module_type_id_str: fte}
            - prev_emissions: {module_type_id_str: kg_co2eq} (empty if no prev year)
        """
        logger.info(
            f"Computing results summary for carbon_report_id={carbon_report_id}"
        )

        report_repo = CarbonReportRepository(self.session)
        report = await report_repo.get(carbon_report_id)
        if not report:
            raise ValueError(f"CarbonReport {carbon_report_id} not found")

        prev_report = None
        if report.year is not None:
            prev_report = await report_repo.get_by_unit_and_year(
                unit_id=report.unit_id, year=report.year - 1
            )

        report_ids = [carbon_report_id]
        if prev_report and prev_report.id is not None:
            report_ids.append(prev_report.id)
        rows = await report_repo.module_stats_by_report(report_ids)
        return _fold_results_summary(rows, {carbon_report_id})
