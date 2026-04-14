"""Factor update provider for research facilities common (DE type 70) factors.

Recomputes kg_co2eq_sum on each factor by summing ALL DataEntryEmission
totals from the corresponding facility's CarbonReport regardless of module
type or emission type.
"""

from typing import Any, Dict, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.factor import Factor
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.repositories.unit_repo import UnitRepository
from app.services.data_ingestion.factor_update_provider import BaseFactorUpdateProvider

logger = get_logger(__name__)


class ResearchFacilitiesCommonFactorUpdateProvider(BaseFactorUpdateProvider):
    """Recomputes kg_co2eq_sum for research_facilities (data_entry_type=70) factors.

    For each factor, uses ``classification.researchfacility_id`` to resolve
    the corresponding Unit, then sums ALL DataEntryEmission totals across the
    whole CarbonReport for the requested year into a single ``kg_co2eq_sum``.

    Only ``kg_co2eq_sum`` is overwritten; ``use_unit`` and ``total_use`` are
    left untouched (handled by base-class merge logic).
    """

    async def compute_factor_values(
        self,
        factor: Factor,
        year: int,
        session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """Compute updated kg_co2eq_sum from actual emission data.

        Args:
            factor: The factor record whose classification holds
                    ``researchfacility_id``.
            year: Reference year for the CarbonReport lookup.
            session: Database session (read-only; writes batched by caller).

        Returns:
            ``{"kg_co2eq_sum": <total float>}``, or ``None`` if
            ``researchfacility_id`` is absent (factor is skipped, not errored).

        Raises:
            ValueError: When the Unit or CarbonReport cannot be found — these
                        are surfaced as errors, not silent skips.
        """
        researchfacility_id: Optional[str] = factor.classification.get(
            "researchfacility_id"
        )
        if not researchfacility_id:
            logger.warning(
                f"Factor {factor.id} has no researchfacility_id in classification; "
                "skipping"
            )
            return None

        # 1. Resolve Unit by institutional_id (= researchfacility_id)
        unit = await UnitRepository(session).get_by_institutional_id(
            researchfacility_id
        )
        if unit is None:
            raise ValueError(
                f"Unit not found for researchfacility_id={researchfacility_id!r}"
            )
        if unit.id is None:
            raise ValueError(
                f"Unit has no database id for "
                f"researchfacility_id={researchfacility_id!r}"
            )

        # 2. Resolve CarbonReport for this unit and year
        carbon_report = await CarbonReportRepository(session).get_by_unit_and_year(
            unit.id, year
        )
        if carbon_report is None:
            raise ValueError(
                f"CarbonReport not found for unit_id={unit.id}, year={year} "
                f"(researchfacility_id={researchfacility_id!r})"
            )
        if carbon_report.id is None:
            raise ValueError(
                f"CarbonReport has no database id for unit_id={unit.id}, year={year}"
            )

        # 3. Aggregate ALL emissions across the entire CarbonReport into one total
        breakdown = await DataEntryEmissionRepository(session).get_emission_breakdown(
            carbon_report.id
        )
        # breakdown: list of (module_type_id, emission_type_id, kg_co2eq_sum)
        total: float = sum(kg for _module_type_id, _emission_type_id, kg in breakdown)

        return {"kg_co2eq_sum": total}
