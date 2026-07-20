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
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.factor_resolver import FactorResolver

logger = get_logger(__name__)

# Flush the batched emission writes every N computed entries (write-batching
# concern only — progress reporting is time-based, below).
PROGRESS_INTERVAL = 5000

# Yield the event loop whenever this much wall time passed in pure-CPU
# per-entry compute. Stage incident 2026-07-17: the previous every-1000-entries
# yield left multi-second stretches where /healthz couldn't get a slot, k8s
# liveness (2s timeout, 3×20s) killed the pod exactly 60s into the recalc.
YIELD_INTERVAL_S = 0.05

# Emit a progress log line + job status update this often (mirrors
# ingestion's PROGRESS_REPORT_INTERVAL_S).
PROGRESS_REPORT_INTERVAL_S = 2.0


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
        handler = BaseModuleHandler.get_by_type(data_entry_type_id)

        # Plan 1661 — one shared FactorResolver per slice.  It memoizes
        # the bulk factor SELECT for (data_entry_type_id, year), so
        # resolving the primary factor for every entry below costs one
        # query total, not one per entry.  ``prepare_create`` (Task 2)
        # is the sole caller of ``resolver.resolve``; the recalc loop no
        # longer rematches or writes ``primary_factor_id`` itself.
        resolver = FactorResolver(self.session)
        # Prime the (det, year) map once so every per-entry resolve below
        # is a dict hit; prepare_create reads the same memoized map for
        # its Strategy-A factor fetches.
        await resolver.factors_by_id(data_entry_type_id, year)
        # Strategy-B (classification-query) factor lookups hit the DB once per
        # emission per entry — an N+1 that dominated headcount recalc (member:
        # ~25 queries/entry × thousands of entries). The factor table is held
        # stable for the slice by the recalc advisory lock, and the same
        # (kind, subkind, context, year) criteria recur across entries, so a
        # slice-scoped memo collapses it to one query per distinct criteria.
        factor_query_cache: dict = {}

        # Plan 310D — per-slice prefetch: handlers that otherwise re-query
        # slice-constant data per entry (plane reloads airports + the full
        # plane-factor set on every entry) bulk-load it once here; pre_compute
        # then reads it from slice_cache in-memory. Empty for handlers that
        # don't override the hook, so their per-entry path is unchanged.
        slice_cache = await handler.prefetch_slice(entries, self.session, year=year)

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
        last_yield = slice_started
        last_report = slice_started
        # Per-segment wall time for a recalc profile line (diagnostic, the
        # analog of ingestion's row-loop profile): localises where per-entry
        # time goes so a slow slice is measured, not guessed.
        seg = {"validate": 0.0, "prepare": 0.0}

        for entry in entries:
            try:
                # Compute-only: ``prepare_create`` does reads (handler
                # pre_compute, ``FactorResolver`` lookups, Strategy-B
                # factor queries) but never writes ``entry.data`` — a
                # per-entry failure needs no SAVEPOINT, there is nothing
                # to roll back.
                _t = time.perf_counter()
                entry_response = DataEntryResponse.model_validate(entry)
                seg["validate"] += time.perf_counter() - _t

                _t = time.perf_counter()
                emissions = await emission_svc.prepare_create(
                    entry_response,
                    year=year,
                    factor_query_cache=factor_query_cache,
                    slice_cache=slice_cache,
                    factor_resolver=resolver,
                )
                seg["prepare"] += time.perf_counter() - _t
                if entry.id is not None:
                    processed_entry_ids.append(entry.id)
                prepared_emissions.extend(emissions)
                recalculated += 1
                if entry.carbon_report_module_id is not None:
                    affected_module_ids.add(entry.carbon_report_module_id)
            except Exception as exc:
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
            # CPU — yield on wall time, not entry count, so the event
            # loop (API, /healthz probes, SSE, heartbeats) never starves
            # regardless of per-entry cost.
            now = time.perf_counter()
            if now - last_yield > YIELD_INTERVAL_S:
                await asyncio.sleep(0)
                last_yield = time.perf_counter()
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
            if now - last_report > PROGRESS_REPORT_INTERVAL_S:
                last_report = time.perf_counter()
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
        # Terminal progress update — with time-based reporting a short
        # slice may never cross the report interval, and the operator
        # should always see N/N before the runner's own finish message.
        if progress_callback is not None:
            await progress_callback(recalculated + errors, len(entries))
        slice_elapsed = time.perf_counter() - slice_started
        logger.info(
            f"Recalc {data_entry_type_id.name}/{year}: replaced emissions for "
            f"{total_replaced} entries ({total_written} emission rows, "
            f"{slice_elapsed:.1f}s compute+write)"
        )
        # Recalc profile: where the per-entry time went (validate = Pydantic,
        # prepare = prepare_create incl. FactorResolver + any handler DB
        # reads). remainder = bulk writes + loop overhead.
        accounted = seg["validate"] + seg["prepare"]
        logger.info(
            "Recalc profile %s/%s: %d entries in %.1fs (%.2f ms/entry) | "
            "validate=%.1f prepare=%.1f remainder=%.1f",
            data_entry_type_id.name,
            year,
            len(entries),
            slice_elapsed,
            slice_elapsed / len(entries) * 1000,
            seg["validate"],
            seg["prepare"],
            slice_elapsed - accounted,
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
