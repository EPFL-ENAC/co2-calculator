"""Factor update provider for research facilities animal (mice & fish) factors.

Recomputes the kg_co2eq_sum_* fields on each factor by aggregating
DataEntryEmission totals from the corresponding Unit's CarbonReport.
"""

from typing import Any, Dict, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry_emission import EmissionType, get_all_nodes
from app.models.factor import Factor
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.repositories.unit_repo import UnitRepository
from app.services.data_ingestion.factor_update_provider import BaseFactorUpdateProvider

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Build a frozen mapping from source name → set of valid emission_type_id ints.
# This covers every node in each sub-tree (root + intermediates + leaves) so
# that emissions stored at any granularity level are correctly classified.
# ---------------------------------------------------------------------------
_purchases_additional_ids: frozenset[int] = frozenset(
    e.value for e in get_all_nodes(EmissionType.purchases__additional)
)
_purchases_all_ids: frozenset[int] = frozenset(
    e.value for e in get_all_nodes(EmissionType.purchases)
)

# Mapping: factor value-field source name → frozenset of valid emission_type_ids
SOURCE_EMISSION_MAP: Dict[str, frozenset[int]] = {
    "processemissions": frozenset(
        e.value for e in get_all_nodes(EmissionType.process_emissions)
    ),
    "building_energycombustions": frozenset(
        e.value for e in get_all_nodes(EmissionType.buildings__combustion)
    ),
    "building_rooms": frozenset(
        e.value for e in get_all_nodes(EmissionType.buildings__rooms)
    ),
    # purchases_additional is a sub-tree of purchases; common = all - additional
    "purchases_common": _purchases_all_ids - _purchases_additional_ids,
    "purchases_additional": _purchases_additional_ids,
    "equipments": frozenset(e.value for e in get_all_nodes(EmissionType.equipment)),
}


class ResearchFacilitiesAnimalFactorUpdateProvider(BaseFactorUpdateProvider):
    """Recomputes kg_co2eq_sum_* factor values for mice & fish animal facilities.

    For each factor, uses ``classification.researchfacility_id`` to resolve
    the corresponding Unit, then aggregates DataEntryEmission totals across
    the whole CarbonReport (all module types) for the requested year.

    Only the ``kg_co2eq_sum_*`` keys are overwritten; shares, use_unit, and
    total_use are left untouched.
    """

    async def compute_factor_values(
        self,
        factor: Factor,
        year: int,
        session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """Compute updated kg_co2eq_sum_* values from actual emission data.

        Args:
            factor: The factor record whose classification holds
                    ``researchfacility_id``.
            year: Reference year for the CarbonReport lookup.
            session: Database session (read-only; writes batched by caller).

        Returns:
            Dict of ``{"kg_co2eq_sum_<source>": <float>}`` for every source
            that has non-zero totals, or ``None`` if
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

        # 3. Aggregate all emissions across the entire CarbonReport, broken
        #    down by (module_type_id, emission_type_id).  We use all modules so
        #    that process, buildings, equipment, and purchase contributions are
        #    captured regardless of which CarbonReportModule they live in.
        breakdown = await DataEntryEmissionRepository(session).get_emission_breakdown(
            carbon_report.id
        )
        # breakdown: list of (module_type_id, emission_type_id, kg_co2eq_sum)

        # 4. Aggregate per source using the SOURCE_EMISSION_MAP
        source_totals: Dict[str, float] = {src: 0.0 for src in SOURCE_EMISSION_MAP}
        for _module_type_id, emission_type_id, kg in breakdown:
            for source, valid_ids in SOURCE_EMISSION_MAP.items():
                if emission_type_id in valid_ids:
                    source_totals[source] += kg
                    break  # each emission type belongs to exactly one source bucket

        # 5. Return only keys with actual data
        return {f"kg_co2eq_sum_{src}": total for src, total in source_totals.items()}
