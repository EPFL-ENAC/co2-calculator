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
    DataEntryEmissionRow,
    EmissionComputation,
    FactorQuery,
)
from app.models.factor import Factor
from app.modules.emissions import (
    EmissionType,
    additional_value_unit,
    get_subtree_leaves,
)
from app.modules.emissions.registry import (
    DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION,
    emission_type_scope,
    resolve_emission_types,
)
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.carbon_report import CarbonReportRead
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.schemas.write_scope import WriteScope
from app.services.factor_resolver import FactorResolver
from app.services.factor_service import FactorService
from app.utils.factor_year import resolve_factor_year

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
        # Memoizes _get_report_for_data_entry by carbon_report_module_id for
        # this instance's lifetime. The module→report relationship is
        # immutable within a request, so this is always safe, and it turns
        # repeated lookups (e.g. many entries of the same module, as in a
        # Simulator Plan prefill or a recalc slice with percentage-of-
        # reference-year entries) from one query each into a single query.
        self._report_by_module_id: dict[
            int, CarbonReport | CarbonReportRead | None
        ] = {}

    async def _get_report_for_data_entry(
        self, data_entry: DataEntry | DataEntryResponse
    ) -> CarbonReport | CarbonReportRead | None:
        """Fetch the CarbonReport for a DataEntry via CarbonReportModule."""
        if (
            not hasattr(data_entry, "carbon_report_module_id")
            or not data_entry.carbon_report_module_id
        ):
            logger.warning("DataEntry missing carbon_report_module_id")
            return None

        module_id = data_entry.carbon_report_module_id
        if module_id in self._report_by_module_id:
            return self._report_by_module_id[module_id]

        stmt = select(CarbonReportModule).where(col(CarbonReportModule.id) == module_id)
        result = await self.session.exec(stmt)
        module = result.one_or_none()

        if not module:
            logger.warning(f"CarbonReportModule not found for id {module_id}")
            self._report_by_module_id[module_id] = None
            return None

        stmt_cr = select(CarbonReport).where(
            col(CarbonReport.id) == module.carbon_report_id
        )
        result_cr = await self.session.exec(stmt_cr)
        report = result_cr.one_or_none()
        if report is None:
            logger.warning(f"CarbonReport not found for id {module.carbon_report_id}")
        self._report_by_module_id[module_id] = report
        return report

    async def _get_year_from_data_entry(
        self, data_entry: DataEntry | DataEntryResponse
    ) -> int | None:
        report = await self._get_report_for_data_entry(data_entry)
        if report is None:
            return None
        return await resolve_factor_year(self.session, report)

    async def _get_percentage_override_kg(
        self,
        data_entry: DataEntry | DataEntryResponse,
        emission_type: EmissionType,
        # #2050 J4: an interactive write hands over the read model the route
        # already resolved. Only reference_year/year/unit_id are read here, and
        # CarbonReportRead carries all three.
        report: CarbonReport | CarbonReportRead,
        *,
        override_cache: dict[int, dict[int, tuple[float, int | None]]] | None = None,
    ) -> tuple[float, int | None] | None:
        """If percentage_of_reference_year is present, compute kg_co2eq from base year.

        Returns ``(kg, primary_factor_id)`` — the factor id is the source
        leaf's, carried through so a copied planner row keeps its provenance
        (plan #2050 F3).

        The override matches the previous-year DataEntry within the same module type
        and data_entry_type, using stable identifiers when available.

        ``override_cache`` (see ``prefetch_percentage_override_cache``) maps
        ``source_data_entry_id`` to its prefetched per-leaf kg sums, letting a
        batch caller short-circuit the fast path below — one PK fetch + one
        sum query per entry otherwise, the shape every Simulator Plan prefill
        copy carries.
        """
        raw = data_entry.data.get("percentage_of_reference_year")
        if raw is None:
            return None
        try:
            percentage = float(raw)
        except TypeError, ValueError:
            logger.warning(
                "Invalid percentage_of_reference_year=%r for data_entry_id=%r",
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

        # Planner snapshot entries carry the exact source entry id — match it
        # directly instead of walking the prior-year report tree. A deleted
        # source falls back to the normal compute path (snapshot data at its
        # stored quantities), as documented in the #1556 plan.
        source_entry_id = data_entry.data.get("source_data_entry_id")
        if source_entry_id is not None:
            leaf_sums = (
                override_cache.get(int(source_entry_id)) if override_cache else None
            )
            if leaf_sums is not None:
                leaf_ids = get_subtree_leaves(emission_type)
                prev_kg = sum(leaf_sums.get(lid, (0.0, None))[0] for lid in leaf_ids)
                factor_id = min(
                    (
                        fid
                        for lid in leaf_ids
                        if (fid := leaf_sums.get(lid, (0.0, None))[1]) is not None
                    ),
                    default=None,
                )
                return prev_kg * (percentage / 100.0), factor_id
            source_entry = await self.session.get(DataEntry, int(source_entry_id))
            if source_entry is None:
                return None
            # Ownership gate: the source must belong to the same unit as this
            # report. Without it, a crafted source_data_entry_id could scale
            # another unit's emissions into this report (cross-tenant read).
            source_report = await self._get_report_for_data_entry(source_entry)
            if source_report is None or source_report.unit_id != report.unit_id:
                logger.warning(
                    "Ignoring cross-unit source_data_entry_id=%r on data_entry_id=%r",
                    source_entry_id,
                    data_entry.id,
                )
                return None
            prev_kg, factor_id = await self._sum_entry_emissions(
                source_entry, emission_type
            )
            return prev_kg * (percentage / 100.0), factor_id

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

        prev_kg, factor_id = await self._sum_entry_emissions(prev_entry, emission_type)
        return prev_kg * (percentage / 100.0), factor_id

    async def _sum_entry_emissions(
        self, entry: DataEntry, emission_type: EmissionType
    ) -> tuple[float, int | None]:
        """Sum an entry's persisted kg_co2eq over the emission type's leaves.

        Returns ``(kg, primary_factor_id)``. The factor id must travel with
        the sum here exactly as it does in ``_sum_leaves_by_source``: if only
        the cached path carried it, the same planner row would render
        differently depending on whether the cache hit (plan #2050 F3).
        """
        leaf_ids = get_subtree_leaves(emission_type)
        stmt = select(
            func.coalesce(func.sum(DataEntryEmission.kg_co2eq), 0.0),
            func.min(DataEntryEmission.primary_factor_id),
        ).where(
            col(DataEntryEmission.data_entry_id) == entry.id,
            col(DataEntryEmission.emission_type_id).in_(leaf_ids),
        )
        kg, factor_id = (await self.session.exec(stmt)).one()
        return float(kg), factor_id

    async def prefetch_percentage_override_cache(
        self, entries: list[DataEntry] | list[DataEntryResponse], *, unit_id: int | None
    ) -> dict[int, dict[int, tuple[float, int | None]]]:
        """Bulk-preload ``source_data_entry_id`` sums for a batch of entries.

        Maps ``source_data_entry_id`` -> {leaf emission_type_id:
        (summed kg, primary_factor_id)}
        for ``_get_percentage_override_kg``'s ``override_cache`` param. Skips
        (and leaves to the per-entry fallback, which re-checks and rejects)
        any source belonging to another unit — same ownership gate as the
        single-entry path, just applied once per source instead of per call.
        """
        if unit_id is None:
            return {}
        source_ids = {
            int(sid)
            for entry in entries
            if (sid := entry.data.get("source_data_entry_id")) is not None
        }
        if not source_ids:
            return {}

        sources = (
            await self.session.exec(
                select(DataEntry).where(col(DataEntry.id).in_(source_ids))
            )
        ).all()

        same_unit_ids: set[int] = set()
        for source in sources:
            if source.id is None:
                continue
            source_report = await self._get_report_for_data_entry(source)
            if source_report is not None and source_report.unit_id == unit_id:
                same_unit_ids.add(source.id)

        return await self._sum_leaves_by_source(same_unit_ids)

    async def _sum_leaves_by_source(
        self, source_ids: set[int]
    ) -> dict[int, dict[int, tuple[float, int | None]]]:
        """GROUP BY sum of persisted kg_co2eq per (source entry, leaf type).

        Also carries the source leaf's ``primary_factor_id`` so a copied
        planner row keeps its factor provenance — without it the row renders
        with no ``active_power_w``/``standby_power_w`` and the table marks it
        incomplete (plan #2050 F3). ``min`` picks one deterministic id when a
        leaf resolved through several factors, matching what
        ``prepare_create``'s rollup row and ``DataEntryRepository``'s
        aggregate already do.
        """
        if not source_ids:
            return {}
        stmt = (
            select(
                DataEntryEmission.data_entry_id,
                DataEntryEmission.emission_type_id,
                func.sum(DataEntryEmission.kg_co2eq),
                func.min(DataEntryEmission.primary_factor_id),
            )
            .where(col(DataEntryEmission.data_entry_id).in_(source_ids))
            .group_by(
                col(DataEntryEmission.data_entry_id),
                col(DataEntryEmission.emission_type_id),
            )
        )
        # Seed every requested id so a source with no persisted emissions yet
        # (e.g. not yet recalculated) still hits the cache with an empty sum
        # instead of falling back to the per-entry path.
        sums: dict[int, dict[int, tuple[float, int | None]]] = {
            sid: {} for sid in source_ids
        }
        for data_entry_id, leaf_type_id, kg, factor_id in await self.session.exec(stmt):
            sums.setdefault(data_entry_id, {})[leaf_type_id] = (float(kg), factor_id)
        return sums

    async def prepare_create(
        self,
        data_entry: DataEntry | DataEntryResponse,
        kg_co2eq_override: float | None = None,
        *,
        year: int | None = None,
        factor_query_cache: dict | None = None,
        slice_cache: dict | None = None,
        factor_resolver: FactorResolver | None = None,
        override_cache: dict[int, dict[int, tuple[float, int | None]]] | None = None,
        scope: WriteScope | None = None,
    ) -> list[DataEntryEmissionRow]:
        """Prepare emission records for any data entry type.
        TODO: Make this function readable!
        Orchestrates the pipeline below. The resolver-derived primary factor
        is handed to ``resolve_emission_types`` so a module can pick its
        leaves from the matched factor (buildings: the factor's energy_type
        selects the single heating leaf, #1575); other types ignore it:

        1. ``FactorResolver.resolve`` → the primary factor from classification
        2. ``resolve_emission_types`` → which EmissionType leaves to produce
           (reads the factor: buildings' energy_type picks the heating leaf)
        3. ``handler.pre_compute``    → enrich ctx (DB calls, arithmetic)
        4. ``handler.resolve_computations`` → one EmissionComputation per factor
        5. ``_fetch_factors``          → look up Factor (Strategy A or B)
        6. ``_apply_formula``         → kg_co2eq = f(ctx, factor.values)

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
            factor_resolver: Memoized per-instance resolver (plan 1661) that
                derives the primary factor from ``data_entry.data``'s
                classification fields instead of a stored id. Recalc slices
                pass one shared instance across entries; single-entry callers
                get a fresh one built here.

        Returns:
            Ready-to-insert emission rows (lightweight, not the real ORM
            model — see ``DataEntryEmissionRow``).

        Raises:
            ValueError: whenever emissions cannot be computed correctly —
                unresolvable year, unmapped type, missing factor key. #2050
                Track I: every one of these used to log and return partial
                or empty results, publishing a number that looked complete.
                Recalc records the failure per entry and carries on
                (``emission_recalculation.py:173``), so raising surfaces
                the bad data without stalling the batch.
        """
        # ``data_entry_type`` is a property over a non-nullable int and
        # ``DataEntryResponse.id`` is ``int``, so only the ORM model's
        # pre-flush ``id`` is genuinely reachable here.
        if data_entry.id is None:
            raise ValueError(
                "DataEntry must be flushed (id assigned) before computing emissions"
            )

        # #2050 J4: the route already resolved this module's report. Seeding
        # the memo this service already keeps means _get_report_for_data_entry
        # and the year resolution below cost nothing, instead of re-reading the
        # module, report and project.
        if scope is not None and scope.module.id is not None:
            self._report_by_module_id.setdefault(scope.module.id, scope.report)

        # A memo scoped to one invocation cannot go stale — factors do not
        # change mid-call — so interactive callers get one too (#2050 J4).
        if factor_query_cache is None:
            factor_query_cache = {}

        resolver = factor_resolver or FactorResolver(self.session)
        handler = BaseModuleHandler.get_by_type(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )

        # Prefer using the lightweight hook that tests commonly patch.
        # This avoids unnecessary DB calls to fetch the report when tests
        # replace `_get_year_from_data_entry` with an AsyncMock. Year is
        # needed below to resolve the primary factor, so this must run
        # before factor/emission-type resolution.
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
                # Same precedence as _get_year_from_data_entry: the plan's
                # reference year drives factor lookup.
                year = await resolve_factor_year(self.session, report)
        if year is None:
            # #2050 Track J: this used to warn "factors may not match" and
            # then use them anyway — naming its own defect in a log line.
            # Year selects the factor, so an unresolvable year means every
            # number below is priced off an arbitrary year's factor.
            raise ValueError(
                f"Cannot determine the factor year for data_entry_id="
                f"{data_entry.id!r} (carbon_report_module_id="
                f"{data_entry.carbon_report_module_id!r}); refusing to "
                f"compute emissions against an unknown year"
            )
        # Also load the report when the percentage override is requested, since
        # _get_percentage_override_kg needs reference_year and unit_id.
        if (
            report is None
            and data_entry.data.get("percentage_of_reference_year") is not None
        ):
            report = await self._get_report_for_data_entry(data_entry)

        # The primary factor is derived state: resolved from the entry's
        # classification fields, never read from a stored id. The resolver
        # itself short-circuits when the handler has no kind field or the
        # entry carries no kind value (Strategy-B handlers like plane).
        primary_factor: Factor | None = None
        if year is not None:
            primary_factor = await resolver.resolve(
                handler,
                data_entry.data,
                DataEntryTypeEnum(data_entry.data_entry_type),
                year,
            )

        emission_types = resolve_emission_types(
            data_entry.data_entry_type,
            data_entry.data,
            factor=primary_factor,
        )
        if emission_types is None:
            # #2050 Track J: an unmapped type returned [], which is
            # indistinguishable downstream from "this entry emits nothing".
            raise ValueError(
                f"No emission types are mapped for "
                f"{data_entry.data_entry_type!r} (data_entry_id="
                f"{data_entry.id!r}); it cannot contribute a total"
            )
        # Genuinely empty is a real answer, unlike None above: the registry
        # resolved this entry's classification to no leaves.
        if not emission_types:
            return []

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
                except ValueError, TypeError:
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
        # Legacy rows may still carry a stored primary_factor_id — the
        # resolver result always wins; the stored value is dead weight.
        ctx["primary_factor_id"] = primary_factor.id if primary_factor else None
        # Forward the slice prefetch only when a caller (the recalc workflow)
        # actually preloaded one — keeps handlers whose pre_compute takes no
        # slice_cache (the base + non-plane modules) callable as-is.
        pre_compute_kwargs = {"slice_cache": slice_cache} if slice_cache else {}
        ctx.update(
            await handler.pre_compute(data_entry, self.session, **pre_compute_kwargs)
        )
        # Add factor year to context for year-specific formulas
        ctx["_year"] = year

        results: list[DataEntryEmissionRow] = []

        # Resolve every computation up front so the prefetch below sees all of
        # them, then prime the Strategy-B memo in one query (#2050 J4).
        # resolve_computations is pure, so hoisting it also stops it running
        # twice.
        computations_by_type = [
            (
                emission_type,
                handler.resolve_computations(data_entry, emission_type, ctx),
            )
            for emission_type in emission_types
        ]
        await self._prime_factor_query_cache(
            [comp for _, comps in computations_by_type for comp in comps],
            year=year,
            factor_query_cache=factor_query_cache,
        )
        for emission_type, computations in computations_by_type:
            for comp in computations:
                factors = await self._fetch_factors(
                    comp,
                    year,
                    data_entry_type=DataEntryTypeEnum(data_entry.data_entry_type),
                    factor_resolver=resolver,
                    factor_query_cache=factor_query_cache,
                )

                if report is not None:
                    override = await self._get_percentage_override_kg(
                        data_entry=data_entry,
                        emission_type=emission_type,
                        report=report,
                        override_cache=override_cache,
                    )
                    if override is not None:
                        override_kg, override_factor_id = override
                        results.append(
                            DataEntryEmissionRow(
                                data_entry_id=data_entry.id,
                                emission_type_id=emission_type.value,
                                # The source leaf's factor, so a copied
                                # planner row keeps its provenance and still
                                # renders its factor-derived columns
                                # (plan #2050 F3).
                                primary_factor_id=override_factor_id,
                                scope=emission_type_scope(emission_type),
                                kg_co2eq=float(override_kg),
                                meta={
                                    "factors_used": [],
                                    "percentage_of_reference_year": data_entry.data.get(
                                        "percentage_of_reference_year"
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
                        DataEntryEmissionRow(
                            data_entry_id=data_entry.id,
                            emission_type_id=comp.emission_type.value,
                            primary_factor_id=None,
                            kg_co2eq=float(effective_override),
                            scope=emission_type_scope(comp.emission_type),
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
                    # #2050 Track J: _apply_formula raises with the specific
                    # reason rather than returning None for the caller to
                    # drop. Dropping the leaf produced a total that looked
                    # complete but was missing a term; for rollup types the
                    # rollup row is only written when more than one leaf
                    # survives, so it rendered as a blank cell instead.
                    try:
                        per_factor_kg = self._apply_formula(
                            ctx, factor.values or {}, comp
                        )
                    except ValueError as exc:
                        raise ValueError(
                            f"data_entry_id={data_entry.id!r}, "
                            f"emission_type={emission_type.name!r}, "
                            f"factor_id={factor.id!r}: {exc}"
                        ) from exc
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
                        DataEntryEmissionRow(
                            data_entry_id=data_entry.id,
                            emission_type_id=_et_id,
                            primary_factor_id=factor.id,
                            kg_co2eq=per_factor_kg,
                            additional_value=additional_value,
                            scope=emission_type_scope(EmissionType(_et_id)),
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
                DataEntryEmissionRow(
                    data_entry_id=data_entry.id,
                    emission_type_id=rollup_type.value,
                    primary_factor_id=primary_factor_id,
                    kg_co2eq=total_kg,
                    scope=None,
                    meta={"is_rollup": True},
                )
            )

        return results

    @staticmethod
    def _factor_query_cache_key(q: FactorQuery, year: int | None) -> tuple:
        """The one place the Strategy-B memo key is built.

        Shared by ``_fetch_factors`` and ``_prime_factor_query_cache`` so the
        two cannot drift: a second spelling of this tuple would silently turn
        the prime into a no-op (#2050 J4).
        """
        return (
            q.data_entry_type,
            q.kind,
            q.subkind,
            q.emission_type,
            tuple(sorted(q.context.items())),
            tuple(sorted(q.fallbacks.items())),
            year,
        )

    async def _prime_factor_query_cache(
        self,
        computations: list[EmissionComputation],
        year: int | None,
        factor_query_cache: dict,
    ) -> None:
        """Resolve every Strategy-B3 criteria in these computations at once.

        #2050 J4: ``_fetch_factors`` queried one subtree per emission root —
        three for a headcount member. Every subtree is known before the first
        query, so one ``IN`` covers them all, and the per-criteria results are
        seeded into the memo ``_fetch_factors`` already consults.

        Only the pure-B3 shape is primed (an ``emission_type`` with no
        kind/subkind/context/fallbacks). Anything else falls through to
        ``_fetch_factors``' own resolution, so a shape this misses costs a
        statement, never a wrong factor.
        """
        b3 = [
            comp
            for comp in computations
            if comp.factor_id is None
            and comp.factor_query is not None
            and comp.factor_query.emission_type is not None
            and comp.factor_query.kind is None
            and comp.factor_query.subkind is None
            and not comp.factor_query.context
            and not comp.factor_query.fallbacks
        ]
        if not b3:
            return

        leaves_by_comp: dict[int, list[EmissionType]] = {}
        for comp in b3:
            query = comp.factor_query
            if query is None or query.emission_type is None:
                continue
            leaves_by_comp[id(comp)] = [
                EmissionType(node) for node in get_subtree_leaves(query.emission_type)
            ]
        wanted = sorted(
            {leaf for leaves in leaves_by_comp.values() for leaf in leaves},
            key=lambda leaf: leaf.value,
        )
        found = await FactorService(self.session).list_by_emission_types(
            wanted, year=year
        )
        by_emission_type: dict[int, list[Factor]] = {}
        for factor in found:
            by_emission_type.setdefault(factor.emission_type_id, []).append(factor)

        for comp in b3:
            query = comp.factor_query
            if query is None:
                continue
            factors: list[Factor] = []
            for leaf in leaves_by_comp.get(id(comp), []):
                factors.extend(by_emission_type.get(leaf.value, []))
            if query.data_entry_type is not None:
                factors = [
                    f for f in factors if f.data_entry_type_id == query.data_entry_type
                ]
            factor_query_cache[self._factor_query_cache_key(query, year)] = factors

    async def _fetch_factors(
        self,
        comp: EmissionComputation,
        year: int | None = None,
        *,
        data_entry_type: DataEntryTypeEnum | None = None,
        factor_resolver: FactorResolver | None = None,
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
            # The resolver's memoized (det, year) map is already primed by
            # the resolve() call that produced comp.factor_id, so this is a
            # dict hit, not a query. A miss still falls back to the DB so
            # semantics (including the year-mismatch warning) are unchanged.
            factor = None
            if (
                factor_resolver is not None
                and data_entry_type is not None
                and year is not None
            ):
                by_id = await factor_resolver.factors_by_id(data_entry_type, year)
                factor = by_id.get(comp.factor_id)
            if factor is None:
                factor = await factor_service.get(comp.factor_id)
            # #2050 Track J: both of these returned [] — the year mismatch
            # with a warning, the missing factor with nothing at all. An
            # empty factor list means the leaf loop in prepare_create never
            # runs, so the entry contributes zero and the missing-key raise
            # there never fires. Silent zeros are the failure mode this
            # whole track exists to remove.
            if factor is None:
                raise ValueError(
                    f"Factor {comp.factor_id!r} referenced by emission_type="
                    f"{comp.emission_type.name!r} does not exist"
                )
            if year is not None and factor.year != year:
                raise ValueError(
                    f"Factor {comp.factor_id!r} is for year {factor.year!r} "
                    f"but this entry is priced for year {year!r}; refusing "
                    f"to compute emissions from a mismatched factor"
                )
            result.append(factor)
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
                cache_key = self._factor_query_cache_key(q, year)
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
                # #2050 J4: one query for the whole subtree. This looped the
                # leaves and queried per node — 24 factor SELECTs for one
                # headcount member POST (3 roots whose subtrees hold 24
                # leaves), measured in
                # test_headcount_post_statement_budget_pg.py. The subtree is
                # known before the first query, so it belongs in one IN.
                emission_factors = await factor_service.list_by_emission_types(
                    [
                        EmissionType(node)
                        for node in get_subtree_leaves(q.emission_type)
                    ],
                    year=year,
                )
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
    ) -> float:
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

        Raises:
            ValueError: when the inputs cannot produce a value. #2050 Track
                I: this used to return None and the caller dropped the leaf.
                The reason lives here — the caller cannot tell a
                ``formula_func`` that declined from a missing key, and its
                old diagnostic printed two empty lists for the
                ``formula_func`` case, which is the common one.
        """
        if comp.formula_func is not None:
            computed = comp.formula_func(ctx, factor_values)
            if computed is None:
                null_inputs = sorted(k for k, v in ctx.items() if v is None)
                raise ValueError(
                    f"The formula for {comp.emission_type.name!r} could not "
                    f"produce a value. Null inputs on the entry: "
                    f"{null_inputs or 'none'}. Factor keys available: "
                    f"{sorted(factor_values)}. A reference-data lookup that "
                    f"found no match (an unknown building room, say) shows "
                    f"up here as a null input"
                )
            return computed

        if not comp.quantity_key or not comp.formula_key:
            raise ValueError(
                f"{comp.emission_type.name!r} has neither a formula_func nor "
                f"both of quantity_key/formula_key (quantity_key="
                f"{comp.quantity_key!r}, formula_key={comp.formula_key!r}); "
                f"it cannot be computed as configured"
            )

        quantity = ctx.get(comp.quantity_key)
        ef = factor_values.get(comp.formula_key)
        if quantity is None or ef is None:
            missing = [
                name
                for name, value in (
                    (f"entry.{comp.quantity_key}", quantity),
                    (f"factor.{comp.formula_key}", ef),
                )
                if value is None
            ]
            raise ValueError(
                f"Cannot compute {comp.emission_type.name!r}: {missing} is missing"
            )

        result = float(quantity) * float(ef)
        if comp.multiplier_key:
            mult = factor_values.get(comp.multiplier_key, comp.multiplier_default)
            if mult is None:
                mult = comp.multiplier_default
            result *= float(mult)
        return result

    async def create(
        self, data_entry: DataEntryResponse, *, scope: WriteScope | None = None
    ) -> list[DataEntryEmission]:
        """Create emissions for a data entry, if applicable.

        Returns a list of created emission records. Single-entry path — the
        one place besides ``upsert_by_data_entry`` that genuinely needs real
        ``session.add()``ed rows, so ``prepare_create``'s lightweight rows
        are materialized here, not left lightweight like the bulk paths.
        """
        emission_records = await self.prepare_create(data_entry, scope=scope)
        if not emission_records:
            return []

        created_emissions = await self.repo.bulk_create(
            [row.to_orm() for row in emission_records]
        )
        return created_emissions

    async def bulk_create(
        self, emission_records: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        """Create emissions for multiple data entries, if applicable."""
        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def bulk_copy(self, emissions: list[DataEntryEmissionRow]) -> int:
        """Bulk-insert freshly computed rows with nothing to replace first.

        For prefill-style callers writing brand-new entries — mirrors
        ``bulk_replace_for_entries`` minus the delete half.
        """
        return await self.repo.bulk_copy(emissions)

    async def bulk_replace_for_entries(
        self,
        data_entry_ids: list[int],
        emissions: list[DataEntryEmissionRow],
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

        # Create new emissions — single-entry path, materialize real rows
        # (see create()'s docstring for why the bulk paths don't).
        created_emissions = await self.repo.bulk_create(
            [row.to_orm() for row in prepared_emissions]
        )
        return created_emissions

    async def get_stats(
        self,
        carbon_report_module_id: int,
        aggregate_by: str = "emission_type_id",
        aggregate_field: str = "kg_co2eq",
        exclude_planner_snapshots: bool = False,
    ) -> dict[str, float | None]:
        """Get aggregated emission statistics for a carbon report module."""
        stats = await self.repo.get_stats(
            carbon_report_module_id,
            aggregate_by,
            aggregate_field,
            exclude_planner_snapshots=exclude_planner_snapshots,
        )
        return stats

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
        carbon_report_module_ids: list[int],
        data_entry_types: list[DataEntryTypeEnum],
        group_by_field: str,
        top_n: int = 3,
        label_field: str | None = None,
        report_year: int | None = None,
        emission_type_ids: list[int] | None = None,
    ) -> list[dict]:
        """Get emissions aggregated by subcategory and a grouping field.

        Generic method that returns top N items per subcategory plus a "rest" bucket.
        Several module ids are ranked together as one cross-unit aggregate.
        """
        return await self.repo.get_top_class_breakdown(
            carbon_report_module_ids=carbon_report_module_ids,
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
