"""Emission recalculation service.

Re-runs emission calculations for all DataEntries of a given
(data_entry_type_id, year) combination using the latest factors.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.module_handler_service import ModuleHandlerService

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
        handler_svc = ModuleHandlerService(self.session)
        handler = BaseModuleHandler.get_by_type(data_entry_type_id)

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
            # N+1 query per entry — acceptable for now; batched matching
            # is on the Plan D follow-up list.
            should_refresh = (
                handler.kind_field is not None and handler.kind_field in entry.data
            )
            old_data = entry.data
            try:
                if should_refresh:
                    refreshed = await handler_svc.resolve_primary_factor_id(
                        handler=handler,
                        payload=dict(entry.data),
                        data_entry_type_id=data_entry_type_id,
                        year=year,
                        existing_data=None,
                    )
                    new_factor_id = refreshed.get("primary_factor_id")
                    if new_factor_id != entry.data.get("primary_factor_id"):
                        # Tentative swap so DataEntryResponse + upsert
                        # see the refreshed factor.  Rolled back below
                        # if the upsert fails, so partial-failure runs
                        # don't leave entry.data pointing at the new
                        # factor while data_entry_emissions is still
                        # computed against the old one.
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
