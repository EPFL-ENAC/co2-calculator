from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.connector import ConnectorType
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.module_type import ModuleTypeEnum
from app.schemas.user import UserRead
from app.services.data_entry_emission_service import (
    KG_CO2EQ_OVERRIDE_KEY,
)
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
    StatsDict,
)

logger = get_logger(__name__)

# Sentinel ``user_institutional_id`` values for a traveler not tied to a
# resolvable Headcount identity (#1153, revised to the -1/null scheme —
# see docs/src/implementation-plans/1153-traveler-sentinel-resolution-prd.md).
# Must match the same-named constants in
# frontend/src/constant/module-config/traveler-options.ts.
# - INTERNAL: traveler has a SCIPER but it doesn't resolve against this
#   report's Headcount roster. Not assigned by ingestion (a Tableau row
#   either has a SCIPER or doesn't) — read-time resolution only, defined
#   here for centralized reuse (tests, future create-DTO validation).
# - EXTERNAL: traveler has no SCIPER at all. Ingestion assigns this on a
#   blank/None/whitespace SCIPER.
TRAVELER_OTHER_INTERNAL = "-1"
TRAVELER_OTHER_EXTERNAL = None


class ProfessionalTravelApiProvider(BaseTableauApiProvider):
    """Professional-travel (flights) provider backed by the EPFL Tableau
    connection. Credentials + datasource LUID come from the DB via the base
    class; this subclass owns only the travel-specific transform/load.
    """

    CONNECTOR = ConnectorType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.professional_travel
    DATA_ENTRY_TYPE = DataEntryTypeEnum.plane

    INGEST_NOUN = "travel"
    # SAP coverage gap: a blank Centre financier means no matching SAP expense
    # report exists for the Kuoni décompte number. Names the root cause so a
    # feed regression is diagnosable from job metadata.
    MISSING_UNIT_REASON = "Missing Centre financier (no matching SAP expense report)"

    # Stable contract with the Tableau datasource. Captions are validated
    # against read-metadata at fetch time so a rename/removal upstream fails
    # loud instead of silently dropping a column. Do NOT add "IN_Centre
    # financier" here — the Tableau service team requires the calculated
    # "Centre financier" field.
    REQUIRED_CAPTIONS: list[str] = [
        "OUT_CO2_CORRECTED",
        "OUT_DISTANCE_CORRECTED",
        "SCIPER",
        "Centre financier",
        "IN_Departure date",
        "IN_Segment class",
        "IN_Segment destination airport code",
        "IN_Segment origin airport code",
        "IN_Supplier",
        "IN_Ticket number",
        "PASSENGER_TYPE",
        "ROUND_TRIP",
        "TRANSPORT_TYPE",
        "Number of trips",
    ]

    # Feed-quality diagnostics only — OUT_* fields are Tableau-computed and
    # always present, so they're excluded from the missing-value count.
    MISSING_VALUE_FIELDS: list[str] = [
        c
        for c in REQUIRED_CAPTIONS
        if c not in ("OUT_CO2_CORRECTED", "OUT_DISTANCE_CORRECTED")
    ]

    def _log_missing_field_stats(self, raw_data: list[dict[str, Any]]) -> None:
        """Log how many raw rows are missing each tracked field.

        Counted against the full raw feed (not the year-filtered subset)
        so this reflects overall feed quality, not just what survives
        filtering. Diagnostic only — not surfaced in job stats/metadata.
        """
        counts = {field: 0 for field in self.MISSING_VALUE_FIELDS}
        for record in raw_data:
            for field in self.MISSING_VALUE_FIELDS:
                if not str(record.get(field) or "").strip():
                    counts[field] += 1

        if any(counts.values()):
            logger.info(
                f"Travel feed missing-value counts (of {len(raw_data)} rows): "
                f"{counts}"
            )

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        try:
            self._log_missing_field_stats(raw_data)
            transformed = []

            for record in raw_data:
                # Filter by target year
                # Filter by target year
                departure_date_str = record.get("IN_Departure date") or ""
                departure_date = self._parse_date(departure_date_str)
                if (not departure_date) or (departure_date.year != self.config["year"]):
                    continue

                # SCIPER is optional (#1153): a traveler with no EPFL SCIPER
                # still gets ingested, tagged with the external-traveler
                # sentinel instead of being dropped.
                sciper_raw = record.get("SCIPER")
                sciper = (
                    sciper_raw
                    if sciper_raw and str(sciper_raw).strip()
                    else TRAVELER_OTHER_EXTERNAL
                )

                # Validate IATA codes
                origin_iata: str = record.get("IN_Segment origin airport code") or ""
                destination_iata: str = (
                    record.get("IN_Segment destination airport code") or ""
                )
                if not origin_iata or not destination_iata:
                    continue

                # Parse number of trips
                raw_trips = record.get("Number of trips")
                try:
                    number_of_trips = int(raw_trips) if raw_trips is not None else 1
                except ValueError, TypeError:
                    number_of_trips = 1
                number_of_trips = max(1, number_of_trips)
                logger.info(record.get("ROUND_TRIP"))
                unit_institutional_id = record.get("Centre financier")

                entry = {
                    "unit_institutional_id": self._strip_unit_prefix(
                        unit_institutional_id
                    ),
                    "user_institutional_id": sciper,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "departure_date": (
                        departure_date.isoformat() if departure_date else None
                    ),
                    "number_of_trips": number_of_trips,
                    "cabin_class": self._normalize_class(
                        record.get("IN_Segment class") or ""
                    ),
                    "note": None,
                    # Preserve CO2 and distance from source
                    "kg_co2eq": record.get("OUT_CO2_CORRECTED"),
                    "distance_km": record.get("OUT_DISTANCE_CORRECTED"),
                    # Keep original values for reference
                    "supplier": record.get("IN_Supplier"),
                    "ticket_number": record.get("IN_Ticket number"),
                    "transport_type": record.get("TRANSPORT_TYPE"),
                    "round_trip": record.get("ROUND_TRIP") == "YES",
                    "passenger_type": record.get("PASSENGER_TYPE"),
                }
                transformed.append(entry)

            return transformed

        except Exception as e:
            error_message = f"Data transformation failed: {str(e)}"
            logger.error(error_message)
            await self._update_job(
                status_message="failed",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": error_message},
            )
            raise

    def _success_status_message(self, stats: StatsDict) -> str:
        return (
            f"Processed {stats['rows_processed']} records: "
            f"{stats['rows_with_factors']} with factors, "
            f"{stats['rows_without_factors']} without factors, "
            f"{stats['rows_skipped']} skipped"
        )

    async def _load_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """Load transformed travel data into database.

        Expects each record to have carbon_report_module_id already resolved.
        Uses self.data_session for consistency.
        Preserves CO2 values from source data (don't recalculate).
        """
        if not data:
            return {"inserted": 0}

        service = DataEntryService(self.data_session)

        # Create data entries with preserved CO2 values.
        # The raw ``kg_co2eq`` key is stripped from the persisted payload —
        # under the reserved ``__kg_co2eq_override__`` carrier instead — so
        # the formula short-circuit in ``prepare_create`` can still tell the
        # raw input apart from the override channel, and so a future user
        # edit clearing the override can trigger a clean recompute (B-H1).
        # The parallel ``kg_co2eq_overrides`` list is kept index-aligned with
        # ``entries`` for the legacy inline-write path below.
        entries = []
        kg_co2eq_overrides: list[float | None] = []
        for item in data:
            carbon_report_module_id = item.get("carbon_report_module_id")
            if not carbon_report_module_id:
                continue

            # Use ``is not None`` rather than ``or`` so a valid 0/0.0 isn't
            # silently replaced by the OUT_*-corrected fallback.  Walking
            # legs and fully-electric trips on green grids land here.
            kg_raw = item.get("kg_co2eq")
            kg_co2eq = kg_raw if kg_raw is not None else item.get("OUT_CO2_CORRECTED")
            dist_raw = item.get("distance_km")
            distance_km = (
                dist_raw if dist_raw is not None else item.get("OUT_DISTANCE_CORRECTED")
            )

            data_payload = dict(item)
            data_payload.pop("kg_co2eq", None)
            if distance_km is not None:
                data_payload["distance_km"] = distance_km

            # Coerce the override value to float; log + skip on garbage values
            # rather than crashing the whole batch (mirrors base_csv_provider).
            override: float | None = None
            if kg_co2eq is not None:
                try:
                    override = float(kg_co2eq)
                except ValueError, TypeError:
                    # Surface unparseable overrides at WARNING so operators see
                    # the silent fallback to formula-based emissions in the log.
                    logger.warning(
                        f"Invalid kg_co2eq value {kg_co2eq!r} from API source, "
                        f"ignoring override"
                    )
            # Persist the override under the reserved carrier key so the
            # async recalc path (``upsert_by_data_entry`` →
            # ``prepare_create``) still honors Tableau's ``OUT_CO2_CORRECTED``
            # under ``BULK_PATH_PURE_ASYNC``.
            if override is not None:
                data_payload[KG_CO2EQ_OVERRIDE_KEY] = override

            # year/unit_id are stamped centrally by
            # DataEntryService.fill_denormalized_scope in bulk_create.
            entry = DataEntry(
                carbon_report_module_id=carbon_report_module_id,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                data=data_payload,
            )
            entries.append(entry)
            kg_co2eq_overrides.append(override)

        if not entries:
            return {"inserted": 0}

        # Bulk create entries
        data_entries_response = await service.bulk_create(
            entries,
            UserRead.model_validate(self.user) if self.user else None,
            job_id=self.job_id,
            source=DataEntrySourceEnum.EXTERNAL_INTEGRATION.value,
            created_by_id=self.job_id,
        )

        # Plan 310-D — the
        # runner-driven ``emission_recalc`` chain (fired by
        # ``api_ingest_handler`` post-success) owns ``data_entry_emissions``
        # writes for the bulk path.  Skip the inline path here — the
        # chain reads the freshly-committed ``data_entries`` and writes
        # emissions against the latest factors.  Inline writes would
        # race the chain's writes for the same primary key.
        #
        # Travel data carries a per-row ``kg_co2eq`` override (Tableau's
        # ``OUT_CO2_CORRECTED``) that the legacy path threaded through
        # ``prepare_create(kg_co2eq_override=...)``.  The async path
        # persists the same value under ``KG_CO2EQ_OVERRIDE_KEY`` above,
        # which ``prepare_create`` reads as a fallback when no function-arg
        # override is passed — so the recalc workflow's
        # ``upsert_by_data_entry`` preserves it across the async hop.
        await self.data_session.flush()
        return {"inserted": len(data_entries_response)}

    def _parse_date(self, date_str: str) -> datetime | None:
        if not date_str or len(date_str) != 8:
            return None
        return datetime.strptime(date_str, "%Y%m%d")

    def _normalize_class(self, class_str: str) -> str:
        # Canonical cabin_class vocabulary ("economy"/"business") —
        # the value resolve_emission_types and factor classification key on.
        # Must NOT emit "eco": the resolver rejects it (the old wrong value),
        # so economy flights would resolve to no emission type.
        mapping = {
            "AIR ECONOMY CLASS": "economy",
            "AIR BUSINESS CLASS": "business",
        }
        return mapping.get(class_str, "economy")
