"""Service for calculating unit-wide totals across all modules."""

from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReportModule
from app.models.module_type import ModuleTypeEnum
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_service import DataEntryService

logger = get_logger(__name__)


class UnitTotalsService:
    """Service for calculating unit-wide carbon footprint totals."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _calculate_totals_for_year(self, unit_id: int, year: int, user) -> float:
        """
        Calculate totals for a specific year without recursion.

        Returns:
            Total kg CO2eq
        """
        total_kg_co2eq = 0.0

        # Equipment Electric Consumption
        try:
            carbon_report_module = await CarbonReportModuleService(
                self.session
            ).get_carbon_report_by_year_and_unit(
                unit_id=unit_id,
                year=year,
                module_type_id=ModuleTypeEnum["equipment"],
            )
            equipment_stats = await DataEntryService(self.session).get_stats(
                carbon_report_module_id=carbon_report_module.id,
            )
            equipment_co2 = equipment_stats.get("total_kg_co2eq", 0.0)
            total_kg_co2eq += float(equipment_co2 or 0.0)
            logger.debug(f"Equipment module: {equipment_co2} kg CO2eq")
        except Exception as e:
            logger.warning(f"Error getting equipment stats: {e}")
            # Continue with other modules

        # TODO: Add other modules as they become available:
        # - Buildings
        # - Purchase
        # - Internal Services
        # - External Cloud
        # - Professional Travel

        return total_kg_co2eq

    async def get_unit_totals(
        self, unit_id: int, year: int, user
    ) -> dict[str, Optional[float]]:
        """
        Get total carbon footprint metrics for a unit across all modules.

        Args:
            unit_id: Unit identifier
            year: Year for the data
            user: Current user (for permission checks)

        Returns:
            Dict with:
            - total_kg_co2eq: Total carbon footprint in kg CO2eq
            - total_tonnes_co2eq: Total carbon footprint in tonnes CO2eq
            - previous_year_total_kg_co2eq: Previous year's total (if available)
            - previous_year_total_tonnes_co2eq: Previous year's total in tonnes
            - year_comparison_percentage: Percentage change from previous year
        """
        logger.info(f"Calculating unit totals for unit={unit_id}, year={year}")

        # Calculate current year totals
        total_kg_co2eq = await self._calculate_totals_for_year(
            unit_id=unit_id, year=year, user=user
        )

        # Get previous year's total for comparison
        previous_year = year - 1
        previous_year_total_kg_co2eq = None
        year_comparison_percentage = None

        try:
            previous_kg_co2eq = await self._calculate_totals_for_year(
                unit_id=unit_id, year=previous_year, user=user
            )
            previous_year_total_kg_co2eq = previous_kg_co2eq
            if previous_year_total_kg_co2eq and previous_year_total_kg_co2eq > 0:
                year_comparison_percentage = (
                    (total_kg_co2eq - previous_year_total_kg_co2eq)
                    / previous_year_total_kg_co2eq
                    * 100
                )
        except Exception as e:
            logger.debug(f"No previous year data available: {e}")

        result = {
            "total_kg_co2eq": round(total_kg_co2eq, 2) if total_kg_co2eq else None,
            "total_tonnes_co2eq": round(total_kg_co2eq / 1000, 2)
            if total_kg_co2eq
            else None,
            "previous_year_total_kg_co2eq": (
                round(previous_year_total_kg_co2eq, 2)
                if previous_year_total_kg_co2eq is not None
                else None
            ),
            "previous_year_total_tonnes_co2eq": (
                round(previous_year_total_kg_co2eq / 1000, 2)
                if previous_year_total_kg_co2eq is not None
                else None
            ),
            "year_comparison_percentage": (
                round(year_comparison_percentage, 1)
                if year_comparison_percentage is not None
                else None
            ),
        }

        logger.info(f"Unit totals calculated: {result['total_kg_co2eq']} kg CO2eq")

        return result

    async def get_validated_emissions_by_unit(self, unit_id: int) -> list[dict]:
        """Get validated emission totals per year for a unit.

        Returns:
            [{"year": 2023, "kg_co2eq": 61700.0}, ...]
        """
        return await DataEntryEmissionRepository(
            self.session
        ).get_validated_totals_by_unit(unit_id=unit_id)

    async def _validated_module_totals(
        self, carbon_report_id: int
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Per-module (emission kg, FTE) totals from persisted module stats."""
        rows = (
            await self.session.execute(
                select(
                    col(CarbonReportModule.module_type_id),
                    col(CarbonReportModule.status),
                    col(CarbonReportModule.stats),
                ).where(col(CarbonReportModule.carbon_report_id) == carbon_report_id)
            )
        ).all()
        emissions: dict[str, float] = {}
        fte: dict[str, float] = {}
        for module_type_id, module_status, stats in rows:
            if module_status != ModuleStatus.VALIDATED or not isinstance(stats, dict):
                continue
            emissions[str(module_type_id)] = stats.get("total", 0.0) or 0.0
            if stats.get("total_fte"):
                fte[str(module_type_id)] = stats["total_fte"]
        return emissions, fte

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

        current_emissions, current_fte = await self._validated_module_totals(
            carbon_report_id
        )

        prev_emissions: dict[str, float] = {}
        if prev_report and prev_report.id is not None:
            prev_emissions, _ = await self._validated_module_totals(prev_report.id)

        return {
            "current_emissions": current_emissions,
            "current_fte": current_fte,
            "prev_emissions": prev_emissions,
        }
