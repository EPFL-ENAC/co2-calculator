from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    FactorQuery,
    get_scope,
    get_subtree_leaves,
)
from app.models.factor import Factor
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.factor_service import FactorService
from app.utils.data_entry_emission_type_map import resolve_emission_types

settings = get_settings()
logger = get_logger(__name__)


class DataEntryEmissionService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryEmissionRepository(session)

    async def _get_year_from_data_entry(
        self, data_entry: DataEntry | DataEntryResponse
    ) -> Optional[int]:
        """Extract year from DataEntry via CarbonReportModule -> CarbonReport.

        The year is stored in the parent CarbonReport, which is linked
        through the carbon_report_module_id.
        """
        if (
            not hasattr(data_entry, "carbon_report_module_id")
            or not data_entry.carbon_report_module_id
        ):
            logger.warning("DataEntry missing carbon_report_module_id")
            return None

        # Fetch the CarbonReportModule to get carbon_report_id
        from app.models.carbon_report import CarbonReportModule

        stmt = select(CarbonReportModule).where(
            col(CarbonReportModule.id) == data_entry.carbon_report_module_id
        )
        result = await self.session.exec(stmt)
        module = result.one_or_none()

        if not module:
            logger.warning(
                f"CarbonReportModule not found for id "
                f"{data_entry.carbon_report_module_id}"
            )
            return None

        # Fetch the CarbonReport to get year
        stmt_cr = select(CarbonReport).where(
            col(CarbonReport.id) == module.carbon_report_id
        )
        result_cr = await self.session.exec(stmt_cr)
        report = result_cr.one_or_none()

        if not report:
            logger.warning(f"CarbonReport not found for id {module.carbon_report_id}")
            return None

        return report.year

    async def prepare_create(
        self,
        data_entry: DataEntry | DataEntryResponse,
    ) -> list[DataEntryEmission]:
        """Prepare emission records for any data entry type.

        Pure orchestrator — zero branching on DataEntryType:

        1. ``resolve_emission_types`` → which EmissionType leaves to produce
        2. ``handler.pre_compute``    → enrich ctx (DB calls, arithmetic)
        3. ``handler.resolve_computations`` → one EmissionComputation per factor
        4. ``_fetch_factors``          → look up Factor (Strategy A or B)
        5. ``_apply_formula``         → kg_co2eq = f(ctx, factor.values)

        Args:
            data_entry: Fully hydrated data entry with ``data_entry_type``.

        Returns:
            Ready-to-insert ``DataEntryEmission`` rows; empty on any failure.
        """
        if not data_entry or data_entry.data_entry_type is None:
            logger.error("DataEntry must have a data_entry_type.")
            return []

        emission_types = resolve_emission_types(
            data_entry.data_entry_type, data_entry.data
        )
        if emission_types is None:
            logger.warning(f"Unhandled type: {data_entry.data_entry_type}")
            return []
        if not emission_types:
            return []

        if data_entry.id is None:
            logger.error("DataEntry must have an ID before creating emissions.")
            return []

        handler = BaseModuleHandler.get_by_type(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )

        # Build context: data_entry.data enriched with pre-computed values
        ctx: dict = {**data_entry.data}
        # TBD Add year to context for time-sensitive factors
        # Relates to #697
        ctx["_year"] = 2025
        ctx.update(await handler.pre_compute(data_entry, self.session))

        # Get year from CarbonReport for year-aware factor lookup
        year = await self._get_year_from_data_entry(data_entry)
        if year is None:
            logger.warning(
                "Could not determine year for data entry, factors may not match"
            )

        results: list[DataEntryEmission] = []

        for emission_type in emission_types:
            computations = handler.resolve_computations(data_entry, emission_type, ctx)

            for comp in computations:
                factors = await self._fetch_factors(comp, year)
                kg_co2eq: float | None = None

                # Check if CSV provides an override value (takes precedence)
                csv_kg_co2eq = data_entry.data.get("kg_co2eq")
                if csv_kg_co2eq is not None:
                    # Use CSV-provided value as override
                    logger.info(
                        f"Using CSV-provided kg_co2eq={csv_kg_co2eq} override for "
                        f"emission_type={emission_type.name!r} "
                        f"data_entry_id={data_entry.id!r}"
                    )
                    kg_co2eq = float(csv_kg_co2eq)
                else:
                    # Compute kg_co2eq using factors and formulas
                    for factor in factors:
                        # If there are multiple factors for this computation,
                        # we sum their contributions
                        # only use case: headcount (multiple factors per emission)
                        kg_co2eq = 0 if kg_co2eq is None else kg_co2eq
                        temp_kg_co2eq: float | None = self._apply_formula(
                            ctx, factor.values or {}, comp
                        )
                        if temp_kg_co2eq is not None:
                            kg_co2eq = kg_co2eq + temp_kg_co2eq
                        if temp_kg_co2eq is None:
                            # Log which values are missing for debugging
                            missing_ctx_keys = [
                                key
                                for key in [comp.quantity_key, comp.multiplier_key]
                                if key and ctx.get(key) is None
                            ]
                            missing_factor_keys = [
                                key
                                for key in [comp.formula_key, comp.multiplier_key]
                                if key and factor.values.get(key) is None
                            ]
                            logger.warning(
                                f"Formula returned None for "
                                f"emission_type={emission_type.name!r} "
                                f"data_entry_id={data_entry.id!r} - "
                                f"Missing context keys: {missing_ctx_keys}, "
                                f"Missing factor keys: {missing_factor_keys}"
                            )
                            continue

                if kg_co2eq is not None:
                    results.append(
                        DataEntryEmission(
                            data_entry_id=data_entry.id,
                            emission_type_id=emission_type.value,
                            primary_factor_id=factor.id,
                            scope=get_scope(emission_type),
                            kg_co2eq=kg_co2eq,
                            meta={
                                "factors_used": [
                                    {"id": factor.id, "values": factor.values}
                                ],
                                **ctx,
                            },
                        )
                    )

        return results

    async def _fetch_factors(
        self, comp: EmissionComputation, year: Optional[int] = None
    ) -> list[Factor]:
        """Fetch factor(s) for an EmissionComputation.

        Two mutually exclusive strategies (see implementation plan §Factor
        Retrieval Strategies):

        **Strategy A** — Direct look-up by ``factor_id``.
          Used by equipment, purchases, process emissions, etc.
          Always returns 0 or 1 factor.

        **Strategy B** — Classification query via ``factor_query``.
          Used by headcount, travel, building.
          Progressively less specific look-ups are tried in order:

          1. Full classification (subkind / context / fallbacks)
             → e.g. train with country_code, plane with cabin_class
          2. Kind only (no subkind/context)
             → e.g. headcount food, headcount waste
          3. By emission_type → returns N factors
             → e.g. all food sub-factors (vegetarian + non-vegetarian)
          4. By data_entry_type → broadest, returns all factors for the type

        Args:
            comp: Emission computation with factor lookup criteria
            year: Optional year to filter factors by (enables year-specific factors)
        """
        factor_service = FactorService(self.session)
        result: list[Factor] = []

        # ── Strategy A: direct look-up ──────────────────────────────────
        if comp.factor_id is not None:
            factor = await factor_service.get(comp.factor_id)
            # Filter by year if factor exists and year is specified
            if factor and year is not None and factor.year != year:
                logger.warning(
                    f"Factor {comp.factor_id} year ({factor.year}) "
                    f"doesn't match data entry year ({year})"
                )
                return []
            result.append(factor) if factor else None
            return result

        # ── Strategy B: classification query ────────────────────────────
        if comp.factor_query is not None:
            q: FactorQuery = comp.factor_query

            # Build the classification dict from optional subkind + context
            # e.g. {"subkind": "business", "country_code": "CH"}
            classification: dict = {}
            if q.subkind is not None:
                classification["subkind"] = q.subkind
            if q.context is not None:
                classification.update(q.context)

            # B1: Most specific — subkind/context/fallbacks present
            #     e.g. plane(kind="plane", subkind="business", category="long_haul")
            #     with fallback {"country_code": "RoW"}
            if classification or q.fallbacks:
                factor = await factor_service.get_factor(
                    data_entry_type=q.data_entry_type,
                    fallbacks=q.fallbacks if q.fallbacks else None,
                    kind=q.kind,
                    year=year,
                    **classification,
                )
                result.append(factor) if factor else None

            # B2: Kind only — no subkind/context
            #     e.g. headcount(kind="food", subkind=None)
            elif q.kind is not None:
                factor = await factor_service.get_by_classification(
                    data_entry_type=q.data_entry_type,
                    kind=q.kind,
                    subkind=None,
                    year=year,
                )
                result.append(factor) if factor else None

            # B3: By emission_type — returns multiple factors
            #     e.g. all sub-factors for "food" (vegetarian, non-vegetarian)
            #     Used when handler doesn't specify kind/subkind
            elif q.emission_type is not None:
                all_nodes = get_subtree_leaves(q.emission_type)
                emission_factors = []
                for node in all_nodes:
                    node_factors = await factor_service.list_by_emission_type(
                        EmissionType(node)
                    )
                    emission_factors.extend(node_factors)
                # we should also filter by data_entry_type in case we have factors
                # for other types with the same emission_type in the subtree,
                # but for now we don't have this case in our seed data
                # so we can add it later if needed
                if q.data_entry_type is not None:
                    emission_factors = [
                        f
                        for f in emission_factors
                        if f.data_entry_type_id == q.data_entry_type
                    ]
                # should get all factors children of the emission type,
                # not just those with matching kind
                # factors = await factor_service.list_by_emission_type(q.emission_type)
                result.extend(emission_factors)

            # B4: Broadest — by data_entry_type only
            #     Returns all factors for this entry type
            elif q.data_entry_type is not None:
                result.extend(
                    await factor_service.list_by_data_entry_type(q.data_entry_type)
                )

        return result

    def _apply_formula(
        self,
        ctx: dict,
        factor_values: dict,
        comp: EmissionComputation,
    ) -> Optional[float]:
        """Compute kg_co2eq from context and factor values.

        If ``comp.formula_func`` is set it takes precedence (complex formulas).
        Otherwise uses the key-based approach:
            ``kg_co2eq = ctx[quantity_key] * factor_values[formula_key]
                         * factor_values.get(multiplier_key, multiplier_default)``
        # maybe too complex: we should always have a formula_func
        and the formula_func can decide to use or not the factor_values and ctx
        as it wants, and we can deprecate the key-based approach
        after a transition period

        # right now only Headcount use default
        """
        if comp.formula_func is not None:
            return comp.formula_func(ctx, factor_values)

        if not comp.quantity_key or not comp.formula_key:
            return None

        quantity = ctx.get(comp.quantity_key)
        ef = factor_values.get(comp.formula_key)
        if quantity is None or ef is None:
            logger.info(
                f"Missing required values for emission calculation "
                f"for key: {comp.quantity_key} or {comp.formula_key}"
            )
            return None

        result = float(quantity) * float(ef)
        if comp.multiplier_key:
            mult = factor_values.get(comp.multiplier_key, comp.multiplier_default)
            if mult is None:
                mult = comp.multiplier_default
            result *= float(mult)
        return result

    async def create(self, data_entry: DataEntryResponse) -> list[DataEntryEmission]:
        """Create emissions for a data entry, if applicable.

        Returns a list of created emission records.
        """
        emission_records = await self.prepare_create(data_entry)
        if not emission_records:
            return []

        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def bulk_create(
        self, emission_records: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        """Create emissions for multiple data entries, if applicable."""
        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def upsert_by_data_entry(
        self, data_entry_response: DataEntryResponse
    ) -> list[DataEntryEmission] | None:
        """Create or update emissions for a data entry, if applicable.

        First deletes existing emissions for this data entry, then creates new ones.
        Returns the list of created/updated emissions.
        """
        # Prepare the emission records
        prepared_emissions = await self.prepare_create(data_entry_response)
        if not prepared_emissions:
            await self.repo.delete_by_data_entry_id(data_entry_response.id)
            await self.session.flush()
            return None

        # Delete existing emissions
        await self.repo.delete_by_data_entry_id(data_entry_response.id)

        # Create new emissions
        created_emissions = await self.repo.bulk_create(prepared_emissions)
        return created_emissions

    async def get_stats(
        self,
        carbon_report_module_id: int,
        aggregate_by: str = "emission_type_id",
        aggregate_field: str = "kg_co2eq",
    ) -> dict[str, float | None]:
        """Get aggregated emission statistics for a carbon report module."""
        stats = await self.repo.get_stats(
            carbon_report_module_id,
            aggregate_by,
            aggregate_field,
        )
        return stats

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
    ) -> dict[str, float]:
        """Get validated emission totals per module for a carbon report."""
        return await self.repo.get_stats_by_carbon_report_id(
            carbon_report_id=carbon_report_id,
        )

    async def get_emission_breakdown(
        self,
        carbon_report_id: int,
    ) -> list[tuple[int, int, int | None, float | None]]:
        """Get emission breakdown by module, emission type, and scope.

        Returns list of (module_type_id, emission_type_id, scope, sum_kg_co2eq).
        """
        return await self.repo.get_emission_breakdown(
            carbon_report_id=carbon_report_id,
        )

    async def get_travel_stats_by_class(
        self,
        carbon_report_module_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by category and cabin_class."""
        return await self.repo.get_travel_stats_by_class(
            carbon_report_module_id,
        )

    async def get_travel_evolution_over_time(
        self,
        unit_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by year and category."""
        return await self.repo.get_travel_evolution_over_time(unit_id)

    # # Dict of dataEntryTypeEnum , func to calculation formulas
    # FORMULAS: dict[EmissionType, Callable] = {}

    # # create a decorator to register formulas
    # @classmethod
    # def register_formula(cls, name: EmissionType):
    #     # should register only for leaf!
    #     def decorator(func):
    #         cls.FORMULAS[name] = func
    #         return func

    #     return decorator

    # async def _prepare_headcount_emissions_old(
    #     self,
    #     data_entry: DataEntry | DataEntryResponse,
    #     emission_types: list[EmissionType],
    #     factor_service: FactorService,
    # ) -> list[DataEntryEmission]:
    #     """Prepare emissions for member/student types (one row per emission type).

    #     Each emission type (food, waste, commuting, grey_energy) uses its own factor.
    #     The kg_co2eq is calculated as: fte × factor_value.kg_co2eq_per_fte

    #     Args:
    #         data_entry: The data entry (member or student)
    #         emission_types: List of emission types (food, waste
    #  commuting, grey_energy)
    #         factor_service: FactorService for looking up factors

    #     Returns:
    #         List of DataEntryEmission objects (one per emission type)
    #     """
    #     emissions: list[DataEntryEmission] = []
    #     fte = data_entry.data.get("fte", 0)

    #     for emission_type in emission_types:
    #         # Look up the specific factor for this emission type
    #         factor = await factor_service.get_by_classification(
    #             data_entry_type=data_entry.data_entry_type,
    #             kind=emission_type.name,
    #             subkind=None,
    #         )

    #         if not factor or not factor.values:
    #             logger.warning(
    #                 f"Missing factor for emission_type={emission_type} "
    #                 f"for data_entry_id={data_entry.id}"
    #             )
    #             continue

    #         # Calculate kg_co2eq = fte × kg_co2eq_per_fte
    #         kg_co2eq_per_fte = factor.values.get("kg_co2eq_per_fte", 0)
    #         kg_co2eq = fte * kg_co2eq_per_fte

    #         emissions.append(
    #             DataEntryEmission(
    #                 data_entry_id=data_entry.id,
    #                 emission_type_id=emission_type.value,
    #                 primary_factor_id=factor.id,
    #                 scope=get_scope(emission_type),
    #                 kg_co2eq=kg_co2eq,
    #                 meta={
    #                     "fte": fte,
    #                     "kg_co2eq_per_fte": kg_co2eq_per_fte,
    #                 },
    #             )
    #         )

    #     return emissions

    # async def _calculate_emissions(
    #     self,
    #     data_entry: DataEntry | DataEntryResponse,
    #     factors: list[Factor],
    #     emission_type: EmissionType,
    # ) -> dict:
    #     """Placeholder method for emissions calculation logic."""
    #     # Implement actual calculation based on data_entry data
    #     if emission_type is None:
    #         raise ValueError("emission_type is required for emissions calculation")
    #     formula_func = self.FORMULAS.get(emission_type)
    #     if formula_func:
    #         return await formula_func(self, data_entry, factors, emission_type)
    #     else:
    #         raise ValueError(f"No formula registered for: {emission_type}")
