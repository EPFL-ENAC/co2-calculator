"""Emission recalculation service.

Re-runs emission calculations for all DataEntries of a given
(data_entry_type_id, year) combination using the latest factors.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService

logger = get_logger(__name__)


class EmissionRecalculationWorkflow:
    """Recalculate emissions for a cross-module data_entry_type / year slice.

    Designed to be called from a background task; uses the caller's session
    so the task controls transaction boundaries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recalculate_for_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
    ) -> dict:
        """Recalculate emissions for every DataEntry of the given type and year.

        Iterates all matching DataEntry rows (across all CarbonReportModules /
        units), calls ``DataEntryEmissionService.upsert_by_data_entry`` for each,
        and recomputes module stats once per distinct CarbonReportModule at the end.

        Per-entry errors are caught and accumulated; a single failing entry never
        aborts the remaining ones.

        Args:
            data_entry_type_id: The data entry type whose emissions to recalculate.
            year: The report year to scope the query.

        Returns:
            Dict with keys: recalculated, modules_refreshed, errors, error_details.
        """
        repo = DataEntryRepository(self.session)
        entries = await repo.list_by_data_entry_type_and_year(data_entry_type_id, year)
        logger.info(
            f"Recalc {data_entry_type_id.name}/{year}: "
            f"{len(entries)} data entries to process"
        )

        # Early-exit: nothing to recalculate.  Keeps the recalc task off the
        # handler / factor lookup paths entirely when the slice is empty,
        # which is the dominant case right after a factor reupload for a
        # det that has no data entries yet.
        if not entries:
            return {
                "recalculated": 0,
                "modules_refreshed": 0,
                "errors": 0,
                "error_details": [],
            }

        emission_svc = DataEntryEmissionService(self.session)
        module_svc = CarbonReportModuleService(self.session)
        factor_repo = FactorRepository(self.session)
        handler = BaseModuleHandler.get_by_type(data_entry_type_id)

        # Plan 310D — batch the rematch.  Pre-load all factors for
        # (data_entry_type_id, year) once into a dict keyed by
        # (kind, subkind), turning what was N+1 SQL roundtrips into one
        # bulk SELECT plus Python lookups.  Skipped when the handler has
        # no ``kind_field`` because there is nothing to rematch on.
        #
        # Lookup-key matches ``ModuleHandlerService.resolve_primary_factor_id``:
        # both read ``classification[kind_field]`` and (when defined)
        # ``classification[subkind_field]``, normalising "" → None for
        # subkind.  Dict misses fall back to the per-entry resolver,
        # which itself does a kind-only fallback when the exact
        # (kind, subkind) row is absent.
        factor_lookup: dict[tuple[str, str | None], int] = {}
        # Skip the bulk SELECT entirely when the handler has no
        # ``kind_field`` OR when no entry actually carries that key in
        # ``entry.data``.  Strategy B handlers (e.g.
        # professional_travel/plane) declare ``kind_field`` but derive
        # the value in ``pre_compute`` — every entry would fail the
        # per-entry refresh gate below, so prefetching factors here
        # would be a wasted SELECT per recalc slice.
        if handler.kind_field is not None and any(
            handler.kind_field in e.data for e in entries
        ):
            kind_field = handler.kind_field
            subkind_field = handler.subkind_field
            factors = await factor_repo.list_by_data_entry_type(
                data_entry_type_id, year
            )
            for factor in factors:
                if factor.id is None:
                    continue
                classification = factor.classification or {}
                kind_value = classification.get(kind_field)
                if kind_value is None or kind_value == "":
                    continue
                subkind_value: str | None = None
                if subkind_field:
                    raw = classification.get(subkind_field)
                    subkind_value = raw if raw else None
                # First writer wins on duplicate keys; ``get_by_classification``
                # uses ``one_or_none`` which raises on duplicates anyway, so
                # callers don't depend on ordering when the index is consistent.
                factor_lookup.setdefault((kind_value, subkind_value), factor.id)

        recalculated = 0
        errors = 0
        error_details: list[dict] = []
        affected_module_ids: set[int] = set()

        for entry in entries:
            # Plan 310B Part 6 — refresh primary_factor_id against current
            # factors before computing.  Strategy A entries (equipment,
            # purchases, …) need this so a CSV reupload that changes a
            # factor's classification re-links the entry to the new
            # factor row instead of dereferencing a stale FK.
            #
            # Gate: only run the refresh when the handler exposes a
            # ``kind_field`` AND that field is actually present in
            # ``entry.data``.  Strategy B handlers like
            # professional_travel/plane have ``kind_field`` set but
            # derive the value in ``pre_compute``, so it's not in
            # ``entry.data`` — running the lookup with an empty kind
            # would either clear ``primary_factor_id`` or raise
            # ``MultipleResultsFound``, neither of which is right for
            # those handlers.
            #
            # Plan 310D — bulk-prefetched ``factor_lookup`` is the
            # single source of truth for the rematch.  ``_lookup_factor_id``
            # mirrors the full kind→subkind→kind-only fallback chain
            # in-memory, so a miss here means "factor truly dropped from
            # the current CSV" — no DB fallback.  Per the strict-drop
            # contract, we clear ``primary_factor_id`` and let the
            # downstream upsert recompute ``kg_co2eq`` as None, which the
            # dashboard surfaces as a missing-factor signal to operators.
            #
            # Bind ``kind_field`` to a local up-front so the
            # type-narrowing ``is not None`` check below proves it to
            # mypy at the ``_lookup_factor_id`` call site.  Avoids an
            # ``assert`` (bandit B101) because asserts are stripped under
            # ``python -O``.
            kind_field = handler.kind_field
            old_data = entry.data
            try:
                if kind_field is not None and kind_field in entry.data:
                    new_factor_id = self._lookup_factor_id(
                        entry_data=entry.data,
                        kind_field=kind_field,
                        subkind_field=handler.subkind_field,
                        factor_lookup=factor_lookup,
                    )
                    if new_factor_id != entry.data.get("primary_factor_id"):
                        # Tentative swap so DataEntryResponse + upsert
                        # see the refreshed factor (or ``None`` on a
                        # drop).  Rolled back below if the upsert fails,
                        # so partial-failure runs don't leave entry.data
                        # pointing at the new factor while
                        # data_entry_emissions is still computed against
                        # the old one.
                        entry.data = {
                            **entry.data,
                            "primary_factor_id": new_factor_id,
                        }

                entry_response = DataEntryResponse.model_validate(entry)
                await emission_svc.upsert_by_data_entry(entry_response)
                recalculated += 1
                if entry.carbon_report_module_id is not None:
                    affected_module_ids.add(entry.carbon_report_module_id)
            except Exception as exc:
                # Roll back the in-memory mutation so the outer
                # data_session.commit() does not persist a stale link
                # alongside an old emissions row.
                entry.data = old_data
                errors += 1
                error_details.append(
                    {
                        "data_entry_id": entry.id,
                        "error": str(exc),
                    }
                )
                logger.error(
                    f"Error recalculating emissions for data_entry_id={entry.id}: {exc}"
                )

        # Recompute module stats once per distinct module (batched at end)
        modules_refreshed = 0
        for module_id in affected_module_ids:
            try:
                await module_svc.recompute_stats(module_id)
                modules_refreshed += 1
            except Exception as exc:
                errors += 1
                error_details.append(
                    {
                        "carbon_report_module_id": module_id,
                        "error": str(exc),
                        "stage": "recompute_module_stats",
                    }
                )
                logger.error(
                    f"Error recomputing stats for carbon_report_module_id="
                    f"{module_id}: {exc}"
                )

        return {
            "recalculated": recalculated,
            "modules_refreshed": modules_refreshed,
            "errors": errors,
            "error_details": error_details,
        }

    @staticmethod
    def _lookup_factor_id(
        entry_data: dict,
        kind_field: str,
        subkind_field: str | None,
        factor_lookup: dict[tuple[str, str | None], int],
    ) -> int | None:
        """Resolve ``primary_factor_id`` from the bulk-prefetched lookup.

        Mirrors the kind→subkind→kind-only fallback chain that
        ``ModuleHandlerService.resolve_primary_factor_id`` runs in DB,
        but entirely in-memory:

        1. Exact ``(kind, subkind)`` match.
        2. Kind-only ``(kind, None)`` fallback — only succeeds if a
           factor with no subkind was prefetched (subkind=NULL row).

        Returns ``None`` on overall miss.  Per Plan 310-D's strict
        rematch contract, the caller treats a None as "factor dropped"
        and clears the entry's ``primary_factor_id`` so the recomputed
        emission is ``None`` (operator surfaces it as missing-factor
        rather than silently substituting via a per-entry DB roundtrip).

        Mirrors the key-derivation done in
        ``ModuleHandlerService.resolve_primary_factor_id``: subkind
        normalises empty string → None, kind reads as-is.
        """
        kind = entry_data.get(kind_field)
        if kind is None or kind == "":
            return None
        subkind: str | None = None
        if subkind_field:
            raw = entry_data.get(subkind_field)
            subkind = raw if raw else None
        # Exact match first.
        factor_id = factor_lookup.get((kind, subkind))
        if factor_id is not None:
            return factor_id
        # Kind-only fallback — only worth trying when subkind was set;
        # otherwise the lookup above already tried (kind, None).
        if subkind is not None:
            return factor_lookup.get((kind, None))
        return None
