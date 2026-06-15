"""Emission recalculation service.

Re-runs emission calculations for all DataEntries of a given
(data_entry_type_id, year) combination using the latest factors.
"""

import asyncio
import time
from typing import Awaitable, Callable, Optional

from sqlalchemy.exc import DBAPIError, InvalidRequestError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.repositories.data_entry_repo import DataEntryRepository
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

logger = get_logger(__name__)

# Emit a progress log line (and invoke the caller's progress callback)
# every N computed entries.
PROGRESS_INTERVAL = 5000


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
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
        carbon_report_module_ids: Optional[list[int]] = None,
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
        entries = await repo.list_by_data_entry_type_and_year(
            data_entry_type_id, year, carbon_report_module_ids
        )
        scope_label = (
            f" (scoped to {len(carbon_report_module_ids)} module(s))"
            if carbon_report_module_ids
            else ""
        )
        logger.info(
            f"Recalc {data_entry_type_id.name}/{year}: "
            f"{len(entries)} data entries to process{scope_label}"
        )

        # Early-exit: nothing to recalculate.  Keeps the recalc task off the
        # handler / factor lookup paths entirely when the slice is empty,
        # which is the dominant case right after a factor reupload for a
        # det that has no data entries yet.
        if not entries:
            return {
                "recalculated": 0,
                "modules_refreshed": 0,
                "affected_module_ids": [],
                "errors": 0,
                "error_details": [],
            }

        emission_svc = DataEntryEmissionService(self.session)
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
        # One bulk SELECT for the slice's factors.  Feeds two caches:
        # ``factor_cache`` (id → Factor) short-circuits Strategy A
        # lookups inside ``prepare_create`` for every entry, and
        # ``factor_lookup`` ((kind, subkind) → id) backs the rematch
        # below (only built when the handler actually rematches).
        factors = await factor_repo.list_by_data_entry_type(data_entry_type_id, year)
        factor_cache: dict[int, Factor] = {f.id: f for f in factors if f.id is not None}
        if handler.kind_field is not None and any(
            handler.kind_field in e.data for e in entries
        ):
            kind_field = handler.kind_field
            subkind_field = handler.subkind_field
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
        # Batched write buffers: per-entry work below is compute-only
        # (reads); all emission writes happen in ONE set-based replace
        # after the loop.  Entries that computed to zero emissions stay
        # in ``processed_entry_ids`` so their stale rows get deleted.
        processed_entry_ids: list[int] = []
        prepared_emissions: list = []
        total_written = 0
        total_replaced = 0
        slice_started = time.perf_counter()

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
            # Bind to a local with an explicit ``Optional[str]`` annotation
            # so the ``is not None`` check below narrows it to ``str`` at
            # the ``_lookup_factor_id`` call site.  The name differs from
            # ``kind_field`` used in the prefetch block above to avoid a
            # mypy scope-collision (the prefetch binding lives inside an
            # ``if handler.kind_field is not None`` block, so mypy infers
            # the narrower ``str`` and then refuses the wider re-bind here).
            # Also avoids an ``assert`` (bandit B101 — asserts are stripped
            # under ``python -O``).
            entry_kind_field: str | None = handler.kind_field
            old_data = entry.data
            try:
                # Compute-only: ``prepare_create`` does reads (handler
                # pre_compute, Strategy-B factor queries) but never
                # writes, so a per-entry failure needs no SAVEPOINT —
                # there is nothing to roll back; the ``except`` just
                # reverts the in-memory factor swap and moves on.
                if entry_kind_field is not None and entry_kind_field in entry.data:
                    new_factor_id = self._lookup_factor_id(
                        entry_data=entry.data,
                        kind_field=entry_kind_field,
                        subkind_field=handler.subkind_field,
                        factor_lookup=factor_lookup,
                    )
                    if new_factor_id != entry.data.get("primary_factor_id"):
                        # Tentative swap so DataEntryResponse +
                        # prepare_create see the refreshed factor (or
                        # ``None`` on a drop); the outer commit persists
                        # the relink alongside the new emissions.
                        entry.data = {
                            **entry.data,
                            "primary_factor_id": new_factor_id,
                        }

                entry_response = DataEntryResponse.model_validate(entry)
                emissions = await emission_svc.prepare_create(
                    entry_response, year=year, factor_cache=factor_cache
                )
                if entry.id is not None:
                    processed_entry_ids.append(entry.id)
                prepared_emissions.extend(emissions)
                recalculated += 1
                if entry.carbon_report_module_id is not None:
                    affected_module_ids.add(entry.carbon_report_module_id)
            except Exception as exc:
                # Revert the in-memory factor swap (no DB writes happened
                # during compute) so the outer commit doesn't persist a
                # stale link next to an old emissions row.
                entry.data = old_data
                # Session/connection-fatal errors can't be contained by
                # a SAVEPOINT — the session is unusable for every
                # remaining entry.  Two shapes seen on stage:
                #   * ``DBAPIError`` with ``connection_invalidated`` —
                #     the raw connection dropped (server restart / LB
                #     reset).
                #   * ``InvalidRequestError`` (incl.
                #     ``PendingRollbackError`` and "Can't reconnect
                #     until invalid transaction is rolled back") — the
                #     session needs a full rollback before any
                #     statement, so even ``begin_nested()``'s SAVEPOINT
                #     enter fails on the next entry.
                # Continuing logs one identical fatal error per
                # remaining entry (masking the first cause) and the job
                # fails anyway.  Stop now and re-raise so the runner
                # records FINISHED+ERROR with the real error.
                connection_dead = (
                    isinstance(exc, DBAPIError) and exc.connection_invalidated
                )
                if connection_dead or isinstance(exc, InvalidRequestError):
                    logger.error(
                        f"emission recalc: session/connection unusable at "
                        f"data_entry_id={entry.id} ({type(exc).__name__}); "
                        f"aborting batch ({recalculated} recalculated, "
                        f"{errors} errored, {len(entries)} total)"
                    )
                    raise
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

            processed = recalculated + errors
            # With cached factors/year, per-entry compute can be pure
            # CPU — yield regularly so the event loop (API, SSE,
            # heartbeats) never starves during a 50k-entry slice.
            if processed % 1000 == 0:
                await asyncio.sleep(0)
            if processed % PROGRESS_INTERVAL == 0:
                # Flush this chunk's writes (one DELETE + one COPY) so
                # neither the emission buffer nor a single statement
                # ever spans more than ~PROGRESS_INTERVAL entries.
                # Statements only — COMMIT stays with the runner, so a
                # preempted or failed job persists nothing.
                total_written += await emission_svc.bulk_replace_for_entries(
                    processed_entry_ids, prepared_emissions
                )
                total_replaced += len(processed_entry_ids)
                processed_entry_ids = []
                prepared_emissions = []
                logger.info(
                    f"Recalc {data_entry_type_id.name}/{year}: "
                    f"{processed}/{len(entries)} entries computed "
                    f"({total_written} emissions written, {errors} errors)"
                )
                if progress_callback is not None:
                    await progress_callback(processed, len(entries))

        # Final chunk (remaining entries below the interval).
        total_written += await emission_svc.bulk_replace_for_entries(
            processed_entry_ids, prepared_emissions
        )
        total_replaced += len(processed_entry_ids)
        logger.info(
            f"Recalc {data_entry_type_id.name}/{year}: replaced emissions for "
            f"{total_replaced} entries ({total_written} emission rows, "
            f"{time.perf_counter() - slice_started:.1f}s compute+write)"
        )

        # Plan 310-D — stats recompute moves out of this workflow and
        # into the runner-driven ``aggregation`` handler that the
        # ``emission_recalc`` task chains on success.  Keeping the
        # ``modules_refreshed`` and ``affected_module_ids`` keys in the
        # return shape so callers (and the runner-persisted meta) keep
        # the same field set; ``modules_refreshed`` is now always 0
        # from this layer because the writer is the aggregation
        # handler, not us.
        return {
            "recalculated": recalculated,
            "modules_refreshed": 0,
            "affected_module_ids": sorted(affected_module_ids),
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
