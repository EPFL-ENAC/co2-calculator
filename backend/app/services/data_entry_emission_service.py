from typing import Optional

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    FactorQuery,
    get_subtree_leaves,
)
from app.models.factor import Factor
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.factor_service import FactorService
from app.utils.data_entry_emission_type_map import (
    DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION,
    resolve_emission_types,
)
from app.utils.emission_category import additional_value_unit, build_year_comparison
from app.utils.it_breakdown import ITSqlTotals

settings = get_settings()
logger = get_logger(__name__)

# B-H1 — reserved key on ``DataEntry.data`` for the per-row ``kg_co2eq``
# override carrier (Tableau's ``OUT_CO2_CORRECTED`` for the travel API,
# parsed CSV-side ``kg_co2eq`` column for ``base_csv_provider``).  The
# double-underscore prefix marks it internal and keeps it from clashing
# with handler-defined kind/subkind keys.  Bulk-path providers persist
# the override here so the async recalc workflow's
# ``upsert_by_data_entry`` (which has no ``kg_co2eq_override`` parameter)
# still honors it via ``prepare_create``'s data-keyed fallback.
KG_CO2EQ_OVERRIDE_KEY = "__kg_co2eq_override__"


def _emission_depth(et: EmissionType) -> int:
    """Count parent chain length (0 = root)."""
    depth = 0
    p = et.parent
    while p is not None:
        depth += 1
        p = p.parent
    return depth


def _pick_emission_type_id(
    comp_emission_type: EmissionType, factor_emission_type_id: int
) -> int:
    """Return the more specific emission_type_id between computation and factor.

    When a factor stores a generic parent (e.g. buildings__rooms,
    professional_travel__plane) but the computation targets a specific leaf,
    the computation's type must be used so the emission has a known scope/category.
    When the factor is more specific (e.g. headcount food sub-types), the
    factor's type is preferred.
    """
    try:
        factor_et = EmissionType(factor_emission_type_id)
        if _emission_depth(factor_et) > _emission_depth(comp_emission_type):
            return factor_emission_type_id
    except ValueError:
        logger.debug(
            "Unknown factor_emission_type_id=%s; "
            "falling back to computation emission type=%s",
            factor_emission_type_id,
            comp_emission_type.value,
        )
    return comp_emission_type.value


class DataEntryEmissionService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryEmissionRepository(session)

    async def _get_report_for_data_entry(
        self, data_entry: DataEntry | DataEntryResponse
    ) -> CarbonReport | None:
        """Fetch the CarbonReport for a DataEntry via CarbonReportModule."""
        if (
            not hasattr(data_entry, "carbon_report_module_id")
            or not data_entry.carbon_report_module_id
        ):
            logger.warning("DataEntry missing carbon_report_module_id")
            return None

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

        stmt_cr = select(CarbonReport).where(
            col(CarbonReport.id) == module.carbon_report_id
        )
        result_cr = await self.session.exec(stmt_cr)
        report = result_cr.one_or_none()
        if report is None:
            logger.warning(f"CarbonReport not found for id {module.carbon_report_id}")
        return report

    async def _get_year_from_data_entry(
        self, data_entry: DataEntry | DataEntryResponse
    ) -> Optional[int]:
        report = await self._get_report_for_data_entry(data_entry)
        if report is None:
            return None
        return report.year if report.year is not None else report.reference_year

    async def _get_percentage_override_kg(
        self,
        data_entry: DataEntry | DataEntryResponse,
        emission_type: EmissionType,
        report: CarbonReport,
    ) -> float | None:
        """If percentage_of_last_year is present, compute kg_co2eq from base year.

        The override matches the previous-year DataEntry within the same module type
        and data_entry_type, using stable identifiers when available.
        """
        raw = data_entry.data.get("percentage_of_last_year")
        if raw is None:
            return None
        try:
            percentage = float(raw)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid percentage_of_last_year=%r for data_entry_id=%r",
                raw,
                data_entry.id,
            )
            return None

        base_year = report.reference_year if report.reference_year is not None else None
        if base_year is None:
            if report.year is None:
                return None
            base_year = report.year - 1

        if report.unit_id is None:
            return None

        # Resolve current module_type_id so we can match the prior-year module.
        stmt_mod = select(CarbonReportModule).where(
            col(CarbonReportModule.id) == data_entry.carbon_report_module_id
        )
        cur_mod = (await self.session.exec(stmt_mod)).one_or_none()
        if cur_mod is None:
            return None

        # Find the prior-year Calculator report for the same unit.
        stmt_prev_report = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                col(CarbonReport.unit_id) == report.unit_id,
                col(CarbonReport.year) == base_year,
                CarbonProject.carbon_report_type == CarbonReportType.CALCULATOR,
            )
        )
        prev_report = (await self.session.exec(stmt_prev_report)).one_or_none()
        if prev_report is None:
            return None

        # Find the matching prior-year module (same module_type_id).
        stmt_prev_mod = select(CarbonReportModule).where(
            col(CarbonReportModule.carbon_report_id) == prev_report.id,
            col(CarbonReportModule.module_type_id) == cur_mod.module_type_id,
        )
        prev_mod = (await self.session.exec(stmt_prev_mod)).one_or_none()
        if prev_mod is None:
            return None

        # Match prior-year DataEntry for the same data_entry_type_id.
        stmt_prev_entry = select(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == prev_mod.id,
            col(DataEntry.data_entry_type_id) == data_entry.data_entry_type_id,
        )

        # Prefer stable identifiers when present.
        uid = data_entry.data.get("user_institutional_id")
        if isinstance(uid, str) and uid.strip():
            stmt_prev_entry = stmt_prev_entry.where(
                DataEntry.data["user_institutional_id"].as_string() == uid.strip()
            )
        name = data_entry.data.get("name")
        if uid is None and isinstance(name, str) and name.strip():
            stmt_prev_entry = stmt_prev_entry.where(
                DataEntry.data["name"].as_string() == name.strip()
            )

        prev_entry = (await self.session.exec(stmt_prev_entry.limit(1))).one_or_none()
        if prev_entry is None:
            return None

        leaf_ids = get_subtree_leaves(emission_type)
        stmt_prev_em = select(
            func.coalesce(func.sum(DataEntryEmission.kg_co2eq), 0.0)
        ).where(
            col(DataEntryEmission.data_entry_id) == prev_entry.id,
            col(DataEntryEmission.emission_type_id).in_(leaf_ids),
        )
        prev_kg = float((await self.session.exec(stmt_prev_em)).one())

        return prev_kg * (percentage / 100.0)

    async def prepare_create(
        self,
        data_entry: DataEntry | DataEntryResponse,
        kg_co2eq_override: float | None = None,
        *,
        year: int | None = None,
        factor_cache: dict[int, Factor] | None = None,
        factor_query_cache: dict | None = None,
        slice_cache: dict | None = None,
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
            kg_co2eq_override: When set (legacy inline ingestion path),
                short-circuits the formula and produces a single emission
                with this kg_co2eq and ``primary_factor_id=None``. Takes
                precedence over the ``KG_CO2EQ_OVERRIDE_KEY`` carrier in
                ``data_entry.data`` (see B-H1).

                Under ``BULK_PATH_PURE_ASYNC`` the ingest providers persist
                the override on the data entry under ``KG_CO2EQ_OVERRIDE_KEY``,
                which survives the inline-write skip and is honored here
                when the function-arg override is absent.  The runner-driven
                recalc workflow's ``upsert_by_data_entry`` therefore
                preserves Tableau's ``OUT_CO2_CORRECTED`` (and CSV-side
                overrides) across the async path instead of formula-recomputing.

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

        # B-H1 — fallback to the persisted ``KG_CO2EQ_OVERRIDE_KEY`` carrier
        # (set by the bulk-path providers) when the caller did not pass an
        # explicit ``kg_co2eq_override``.  The function arg wins so the
        # legacy inline path (which already routes via the arg) keeps its
        # existing semantics.
        effective_override: float | None = kg_co2eq_override
        if effective_override is None:
            persisted_override = data_entry.data.get(KG_CO2EQ_OVERRIDE_KEY)
            if persisted_override is not None:
                try:
                    effective_override = float(persisted_override)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid {KG_CO2EQ_OVERRIDE_KEY} value "
                        f"{persisted_override!r} on data_entry_id="
                        f"{data_entry.id!r}, ignoring override"
                    )

        # Build context: data_entry.data enriched with pre-computed values.
        # Strip the reserved override carrier so it never leaks into the
        # ``meta`` blobs spread from ``ctx`` below; the source dict on the
        # data entry is left intact so re-runs remain idempotent.
        ctx: dict = {**data_entry.data}
        ctx.pop(KG_CO2EQ_OVERRIDE_KEY, None)
        # Forward the slice prefetch only when a caller (the recalc workflow)
        # actually preloaded one — keeps handlers whose pre_compute takes no
        # slice_cache (the base + non-plane modules) callable as-is.
        pre_compute_kwargs = {"slice_cache": slice_cache} if slice_cache else {}
        ctx.update(
            await handler.pre_compute(data_entry, self.session, **pre_compute_kwargs)
        )

        # Prefer using the lightweight hook that tests commonly patch.
        # This avoids unnecessary DB calls to fetch the report when tests
        # replace `_get_year_from_data_entry` with an AsyncMock.
        report = None
        # Bulk callers (the recalc workflow) pass ``year`` directly —
        # they already know the slice's year, so the per-entry
        # module→report lookup is skipped entirely.
        if year is None:
            year = await self._get_year_from_data_entry(data_entry)
        if year is None:
            # Fallback to loading the full report only when year couldn't be
            # resolved via the helper. This keeps behavior unchanged for
            # production while making unit tests easier to mock.
            report = await self._get_report_for_data_entry(data_entry)
            if report is not None:
                year = report.year if report.year is not None else report.reference_year
        if year is None:
            logger.warning(
                "Could not determine year for data entry, factors may not match"
            )
        # Also load the report when the percentage override is requested, since
        # _get_percentage_override_kg needs reference_year and unit_id.
        if (
            report is None
            and data_entry.data.get("percentage_of_last_year") is not None
        ):
            report = await self._get_report_for_data_entry(data_entry)
        # Add factor year to context for year-specific formulas
        ctx["_year"] = year

        results: list[DataEntryEmission] = []

        for emission_type in emission_types:
            computations = handler.resolve_computations(data_entry, emission_type, ctx)

            for comp in computations:
                factors = await self._fetch_factors(
                    comp,
                    year,
                    factor_cache=factor_cache,
                    factor_query_cache=factor_query_cache,
                )

                if report is not None:
                    override_kg = await self._get_percentage_override_kg(
                        data_entry=data_entry,
                        emission_type=emission_type,
                        report=report,
                    )
                    if override_kg is not None:
                        results.append(
                            DataEntryEmission(
                                data_entry_id=data_entry.id,
                                emission_type_id=emission_type.value,
                                primary_factor_id=None,
                                scope=emission_type.scope,
                                kg_co2eq=float(override_kg),
                                meta={
                                    "factors_used": [],
                                    "percentage_of_last_year": data_entry.data.get(
                                        "percentage_of_last_year"
                                    ),
                                    "reference_year": report.reference_year,
                                    **ctx,
                                },
                            )
                        )
                        continue

                # Check if CSV provides an override value (takes precedence)
                if effective_override is not None:
                    logger.info(
                        f"Using kg_co2eq={effective_override} override for "
                        f"emission_type={emission_type.name!r} "
                        f"data_entry_id={data_entry.id!r}"
                    )
                    results.append(
                        DataEntryEmission(
                            data_entry_id=data_entry.id,
                            emission_type_id=comp.emission_type.value,
                            primary_factor_id=None,
                            kg_co2eq=float(effective_override),
                            scope=comp.emission_type.scope,
                            meta={
                                "factors_used": [
                                    {"id": factor.id, "values": factor.values}
                                    for factor in factors
                                ],
                                **ctx,
                            },
                        )
                    )
                    continue

                for factor in factors:
                    per_factor_kg = self._apply_formula(ctx, factor.values or {}, comp)
                    if per_factor_kg is None:
                        missing_ctx_keys = [
                            key
                            for key in [comp.quantity_key, comp.multiplier_key]
                            if key and ctx.get(key) is None
                        ]
                        missing_factor_keys = [
                            key
                            for key in [comp.formula_key, comp.multiplier_key]
                            if key and (factor.values or {}).get(key) is None
                        ]
                        logger.warning(
                            f"Formula returned None for "
                            f"emission_type={emission_type.name!r} "
                            f"data_entry_id={data_entry.id!r} - "
                            f"Missing context keys: {missing_ctx_keys}, "
                            f"Missing factor keys: {missing_factor_keys}"
                        )
                        continue
                    quantity: float | None = None
                    if comp.quantity_key and ctx.get(comp.quantity_key) is not None:
                        base_qty = float(ctx[comp.quantity_key])
                        multiplier = float(
                            (factor.values or {}).get(
                                comp.multiplier_key, comp.multiplier_default
                            )
                            if comp.multiplier_key
                            else comp.multiplier_default
                        )
                        quantity = base_qty * multiplier
                    quantity_unit: str | None = (factor.values or {}).get("unit")
                    _et_id = _pick_emission_type_id(
                        comp.emission_type, factor.emission_type_id
                    )
                    additional_value: float | None = (
                        quantity
                        if (
                            quantity is not None
                            and additional_value_unit(comp.emission_type) is not None
                        )
                        else None
                    )
                    results.append(
                        DataEntryEmission(
                            data_entry_id=data_entry.id,
                            emission_type_id=_et_id,
                            primary_factor_id=factor.id,
                            kg_co2eq=per_factor_kg,
                            additional_value=additional_value,
                            scope=EmissionType(_et_id).scope,
                            meta={
                                "factors_used": [
                                    {"id": factor.id, "values": factor.values}
                                ],
                                "quantity": quantity,
                                "quantity_unit": quantity_unit,
                                **ctx,
                            },
                        )
                    )

        rollup_type = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION.get(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )
        if rollup_type is not None and len(results) > 1:
            total_kg = sum(r.kg_co2eq or 0.0 for r in results)
            primary_factor_id = min(
                (
                    r.primary_factor_id
                    for r in results
                    if r.primary_factor_id is not None
                ),
                default=None,
            )
            results.append(
                DataEntryEmission(
                    data_entry_id=data_entry.id,
                    emission_type_id=rollup_type.value,
                    primary_factor_id=primary_factor_id,
                    kg_co2eq=total_kg,
                    scope=None,
                    meta={"is_rollup": True},
                )
            )

        return results

    async def _fetch_factors(
        self,
        comp: EmissionComputation,
        year: Optional[int] = None,
        *,
        factor_cache: dict[int, Factor] | None = None,
        factor_query_cache: dict | None = None,
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
            # Bulk callers prefetch the slice's factors once; a cache
            # miss still falls back to the DB so semantics (including
            # the year-mismatch warning below) are unchanged.
            factor = None
            if factor_cache is not None:
                factor = factor_cache.get(comp.factor_id)
            if factor is None:
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

            # Slice-scoped memo (opt-in via factor_query_cache): Strategy B
            # hits the DB on every computation, and a recalc slice resolves the
            # same criteria across thousands of entries while the factor table
            # is held stable by the recalc lock. One query per distinct
            # criteria instead of one per emission per entry. Callers that pass
            # no cache (single-entry paths) are unchanged.
            cache_key = None
            if factor_query_cache is not None:
                cache_key = (
                    q.data_entry_type,
                    q.kind,
                    q.subkind,
                    q.emission_type,
                    tuple(sorted(q.context.items())),
                    tuple(sorted(q.fallbacks.items())),
                    year,
                )
                if cache_key in factor_query_cache:
                    return factor_query_cache[cache_key]

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
                factors = await factor_service.get_factors(
                    data_entry_type=q.data_entry_type,
                    fallbacks=q.fallbacks if q.fallbacks else None,
                    kind=q.kind,
                    year=year,
                    **classification,
                )
                if factors:
                    result.extend(factors)

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
                        EmissionType(node), year=year
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
                    await factor_service.list_by_data_entry_type(
                        q.data_entry_type, year=year
                    )
                )

            if factor_query_cache is not None and cache_key is not None:
                factor_query_cache[cache_key] = result

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

    async def bulk_replace_for_entries(
        self,
        data_entry_ids: list[int],
        emissions: list[DataEntryEmission],
    ) -> int:
        """Replace the emissions of a whole recalc slice in two set
        operations: one chunked DELETE over ``data_entry_ids``, one COPY
        of the freshly computed ``emissions``.

        Entries whose recompute produced no emissions must still be in
        ``data_entry_ids`` so their stale rows are deleted — the same
        contract ``upsert_by_data_entry`` honors per entry.
        """
        if not data_entry_ids:
            return 0
        await self.repo.delete_by_data_entry_ids(data_entry_ids)
        return await self.repo.bulk_copy(emissions)

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
        *,
        validated_only: bool = True,
    ) -> dict[str, float]:
        """Get emission totals per module for a carbon report."""
        return await self.repo.get_stats_by_carbon_report_id(
            carbon_report_id=carbon_report_id,
            validated_only=validated_only,
        )

    async def get_emission_breakdown(
        self,
        carbon_report_id: int,
    ) -> list[tuple[int, int, float, float | None]]:
        """Get emission breakdown by module and emission type.

        Returns list of
        (
            module_type_id,
            emission_type_id,
            sum_kg_co2eq,
            sum_additional_value,
        ).
        """
        return await self.repo.get_emission_breakdown_with_quantity(
            carbon_report_id=carbon_report_id,
        )

    async def get_year_comparison_by_unit(
        self,
        unit_id: int,
    ) -> list[dict]:
        """Build per-year emission comparison buckets for a unit.

        Returns one entry per year (ascending) shaped for the Compare Years
        charts::

            [
                {
                    "year": 2023,
                    "total_tonnes_co2eq": 61.7,
                    "modules": {"equipment": 41.7, "buildings_room": 12.3, ...},
                    "scopes": {"1": 8.1, "2": 20.4, "3": 33.2},
                },
                ...
            ]
        """
        rows = await self.repo.get_emission_breakdown_by_unit(unit_id=unit_id)

        per_year: dict[int, list[tuple[int, float]]] = {}
        for year, emission_type_id, kg_co2eq in rows:
            per_year.setdefault(year, []).append((emission_type_id, kg_co2eq))

        result: list[dict] = []
        for year in sorted(per_year):
            comparison = build_year_comparison(per_year[year])
            result.append({"year": year, **comparison})
        return result

    async def get_it_emission_sql_totals(
        self,
        carbon_report_id: int,
        it_emission_type_ids: list[int],
        validated_source_module_type_ids: list[int],
        exclude_module_type_ids: set[int] | frozenset[int] = frozenset(),
    ) -> ITSqlTotals:
        """Compute IT emission totals in SQL.

        Delegates to the repository. Returns a dict with
        ``it_total_kg``, ``overall_total_kg``, ``validated_source_total_kg``,
        and ``validated_it_kg``.
        """
        return await self.repo.get_it_emission_sql_totals(
            carbon_report_id=carbon_report_id,
            it_emission_type_ids=it_emission_type_ids,
            validated_source_module_type_ids=validated_source_module_type_ids,
            exclude_module_type_ids=exclude_module_type_ids,
        )

    async def get_embodied_energy_by_building(
        self,
        carbon_report_id: int,
    ) -> list[tuple[str, float]]:
        """Get embodied-energy emissions grouped by building name."""
        return await self.repo.get_embodied_energy_by_building(
            carbon_report_id=carbon_report_id,
        )

    async def get_embodied_energy_by_category(
        self,
        carbon_report_id: int,
    ) -> list[tuple[str, float]]:
        """Get embodied-energy emissions grouped by factor category."""
        return await self.repo.get_embodied_energy_by_category(
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

    async def get_top_class_breakdown(
        self,
        carbon_report_module_id: int,
        data_entry_types: list[DataEntryTypeEnum],
        group_by_field: str,
        top_n: int = 3,
        label_field: str | None = None,
        report_year: int | None = None,
        emission_type_ids: list[int] | None = None,
    ) -> list[dict]:
        """Get emissions aggregated by subcategory and a grouping field.

        Generic method that returns top N items per subcategory plus a "rest" bucket.
        """
        return await self.repo.get_top_class_breakdown(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_types=data_entry_types,
            group_by_field=group_by_field,
            top_n=top_n,
            label_field=label_field,
            report_year=report_year,
            emission_type_ids=emission_type_ids,
        )

    async def enrich_breakdown_with_factor_labels(
        self,
        breakdown: list[dict],
        data_entry_types: list[DataEntryTypeEnum],
        group_by_field: str,
        factor_label_field: str,
    ) -> list[dict]:
        """Add a ``translation_key`` field to each non-rest child in breakdown.

        Looks up ``Factor.values[factor_label_field]`` for each unique
        ``group_by_field`` code and attaches it to the child dict so the
        frontend can resolve the human-readable label via i18n.
        """
        codes = {
            child["name"]
            for group in breakdown
            for child in group.get("children", [])
            if child.get("name") != "rest"
        }
        if not codes:
            return breakdown

        stmt = (
            select(
                Factor.classification[group_by_field].as_string().label("code"),
                Factor.values[factor_label_field].as_string().label("label"),
            )
            .where(
                col(Factor.data_entry_type_id).in_(
                    [det.value for det in data_entry_types]
                ),
                Factor.classification[group_by_field].as_string().in_(list(codes)),
            )
            .distinct()
        )
        rows = (await self.session.execute(stmt)).all()
        code_to_label: dict[str, str] = {
            row.code: row.label for row in rows if row.code and row.label
        }

        for group in breakdown:
            for child in group.get("children", []):
                label = code_to_label.get(child.get("name", ""))
                if label:
                    child["translation_key"] = label

        return breakdown

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

    #     Each emission type (food, waste, commuting) uses its own factor.
    #     The kg_co2eq is calculated as: fte × factor_value.kg_co2eq_per_fte

    #     Args:
    #         data_entry: The data entry (member or student)
    #         emission_types: List of emission types (food, waste
    #  commuting)
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
