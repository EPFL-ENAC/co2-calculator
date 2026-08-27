"""Factor update provider for research facilities common (DE type 70) factors.

Recomputes kg_co2eq_sum on each factor by summing ALL DataEntryEmission
totals from the corresponding facility's CarbonReport regardless of module
type or emission type.
"""

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.factor import Factor
from app.modules.emissions import EmissionType, get_subtree_leaves
from app.repositories.carbon_report_repo import CarbonReportRepository
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
    ) -> dict[str, Any] | None:
        """Compute updated kg_co2eq_sum from actual emission data.

        Args:
            factor: The factor record whose classification holds
                    ``researchfacility_id``.
            year: Reference year for the CarbonReport lookup.
            session: Database session (read-only; writes batched by caller).

        Returns:
            ``{"kg_co2eq_sum": <total float>}``, or ``None`` if
            ``researchfacility_id`` is absent (factor is skipped, not errored).
            A closed unit (``is_active=False``) with no CarbonReport for the
            year gets an explicit ``0.0`` — it has stopped reporting, so it
            has nothing left to sum, not an unknown value.

        Raises:
            ValueError: When the Unit cannot be found, or an active unit has
                        no CarbonReport for the year — these are surfaced as
                        errors, not silent skips.
        """
        # Skip if kg_co2eq_sum is not missing (already computed)
        if factor.values.get("kg_co2eq_sum") is not None:
            logger.info(
                f"Factor {factor.id} already has kg_co2eq_sum; skipping computation"
            )
            return None

        researchfacility_id: str | None = factor.classification.get(
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
            if not unit.is_active:
                # A closed unit not having a report for this year is the
                # expected case, not a gap: it stopped reporting, so its
                # research facility has no more emissions to sum.
                return {"kg_co2eq_sum": 0.0}
            raise ValueError(
                f"CarbonReport not found for unit_id={unit.id}, year={year} "
                f"(researchfacility_id={researchfacility_id!r})"
            )
        if carbon_report.id is None:
            raise ValueError(
                f"CarbonReport has no database id for unit_id={unit.id}, year={year}"
            )

        # 3. Aggregate some emissions across the entire CarbonReport into one
        #    total. Leaves only: non-leaf entries in by_emission_type are
        #    subtree rollups and would double-count.
        stats = carbon_report.stats or {}
        by_emission_type = stats.get("by_emission_type", {})
        included_leaf_ids = {
            leaf_id
            for root in (
                EmissionType.process_emissions,
                EmissionType.buildings,
                EmissionType.equipment,
                EmissionType.purchases,
            )
            for leaf_id in get_subtree_leaves(root)
        }
        total: float = sum(
            float(kg_co2eq_sum)
            for emission_type_id, kg_co2eq_sum in by_emission_type.items()
            if int(emission_type_id) in included_leaf_ids
        )

        return {"kg_co2eq_sum": total}
