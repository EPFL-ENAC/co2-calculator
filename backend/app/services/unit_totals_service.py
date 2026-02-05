"""Service for calculating unit-wide totals across all modules."""

from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.module_type import ModuleTypeEnum
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_service import DataEntryService
from app.services.headcount_service import HeadcountService

logger = get_logger(__name__)


class UnitTotalsService:
    """Service for calculating unit-wide carbon footprint totals."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _calculate_totals_for_year(
        self, unit_id: int, year: int, user
    ) -> tuple[float, float]:
        """
        Calculate totals for a specific year without recursion.

        Returns:
            Tuple of (total_kg_co2eq, total_fte)
        """
        total_kg_co2eq = 0.0

        # Equipment Electric Consumption
        try:
            # ? retrieve carbon_report_module_id
            carbon_report_module = await CarbonReportModuleService(
                self.session
            ).get_carbon_report_by_year_and_unit(
                unit_id=unit_id,
                year=year,
                module_type_id=ModuleTypeEnum["equipment_electric_consumption"],
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
        # - Infrastructure
        # - Purchase
        # - Internal Services
        # - External Cloud

        # Get FTE from headcount module
        try:
            headcount_service = HeadcountService(self.session, user=user)
            headcount_stats = await headcount_service.get_module_stats(
                unit_id=unit_id, year=year, aggregate_by="submodule"
            )
            # Sum all FTE values
            total_fte = sum(
                float(v)
                for v in headcount_stats.values()
                if isinstance(v, (int, float))
            )
            logger.debug(f"Total FTE: {total_fte}")
        except Exception as e:
            logger.warning(f"Error getting headcount stats: {e}")
            total_fte = 0.0

        return total_kg_co2eq, total_fte

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
            - total_fte: Total FTE count
            - kg_co2eq_per_fte: Carbon footprint per FTE
            - previous_year_total_kg_co2eq: Previous year's total (if available)
            - previous_year_total_tonnes_co2eq: Previous year's total in tonnes
            - year_comparison_percentage: Percentage change from previous year
        """
        logger.info(f"Calculating unit totals for unit={unit_id}, year={year}")

        # Calculate current year totals
        total_kg_co2eq, total_fte = await self._calculate_totals_for_year(
            unit_id=unit_id, year=year, user=user
        )

        # Calculate per FTE
        kg_co2eq_per_fte = total_kg_co2eq / total_fte if total_fte > 0 else None

        # Get previous year's total for comparison
        previous_year = year - 1
        previous_year_total_kg_co2eq = None
        year_comparison_percentage = None

        try:
            previous_kg_co2eq, _ = await self._calculate_totals_for_year(
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
            "total_fte": round(total_fte, 2) if total_fte else None,
            "kg_co2eq_per_fte": round(kg_co2eq_per_fte, 2)
            if kg_co2eq_per_fte
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

        logger.info(
            f"Unit totals calculated: {result['total_kg_co2eq']} kg CO2eq, "
            f"{result['total_fte']} FTE, "
            f"{result['kg_co2eq_per_fte']} kg CO2eq/FTE"
        )

        return result
