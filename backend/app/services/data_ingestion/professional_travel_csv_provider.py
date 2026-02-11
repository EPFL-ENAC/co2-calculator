"""Travel CSV provider for professional travel data ingestion (planes only).

Extends the generic DataEntriesCSVProvider with:
- IATA code → location ID resolution
- Column mapping: from/to → origin_location_id/destination_location_id
- Column mapping: sciper → traveler_id
- Injection of unit_id from config
"""

from typing import Any, Dict

from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionStatus
from app.models.location import Location, TransportModeEnum
from app.models.user import User
from app.schemas.data_entry import BaseModuleHandler
from app.services.data_ingestion.data_entries_csv_provider import (
    DataEntriesCSVProvider,
    StatsDict,
)

logger = get_logger(__name__)

# Columns the user provides in the travel CSV
TRAVEL_CSV_REQUIRED_COLUMNS = {"transport_mode", "from", "to", "traveler_name"}
TRAVEL_CSV_OPTIONAL_COLUMNS = {"departure_date", "sciper", "number_of_trips"}
TRAVEL_CSV_ALL_COLUMNS = TRAVEL_CSV_REQUIRED_COLUMNS | TRAVEL_CSV_OPTIONAL_COLUMNS


class ProfessionalTravelCSVProvider(DataEntriesCSVProvider):
    """Provider to ingest professional travel data from CSV files (planes only).

    Overrides the generic CSV provider to:
    1. Accept user-friendly columns (from/to as IATA codes, sciper)
    2. Resolve IATA codes to location IDs via an in-memory cache
    3. Transform rows into the format expected by ProfessionalTravelHandlerCreate
    """

    def __init__(self, config: Dict[str, Any], user: User | None = None):
        super().__init__(config, user)
        self.unit_id: int | None = config.get("unit_id")
        self._iata_cache: Dict[str, int] = {}

    async def _build_iata_cache(self) -> Dict[str, int]:
        """Build in-memory IATA code → location ID lookup for planes."""
        stmt = select(col(Location.iata_code), col(Location.id)).where(
            Location.transport_mode == TransportModeEnum.plane,
            col(Location.iata_code).isnot(None),
        )
        result = await self.session.execute(stmt)
        cache = {row.iata_code.upper(): row.id for row in result.all()}
        logger.info(f"Built IATA cache with {len(cache)} entries")
        return cache

    async def _setup_and_validate(self) -> Dict[str, Any]:
        """Setup phase: file handling, IATA cache, travel-specific header validation.

        Overrides parent to:
        - Validate against travel CSV columns (from/to) instead of schema columns
        - Build IATA location cache
        - Carry unit_id through to row processing
        """

        if not self.unit_id and self.carbon_report_module_id:
            stmt = (
                select(col(CarbonReport.unit_id))
                .join(
                    CarbonReportModule,
                    col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
                )
                .where(CarbonReportModule.id == self.carbon_report_module_id)
            )
            result = await self.session.execute(stmt)
            row = result.first()
            if row:
                self.unit_id = row[0]
                logger.info(
                    f"Resolved unit_id={self.unit_id} from "
                    f"carbon_report_module_id={self.carbon_report_module_id}"
                )
        if not self.unit_id:
            raise ValueError(
                "unit_id could not be resolved. Provide it in the sync config "
                "or ensure carbon_report_module_id is valid."
            )

        await self.repo.update_ingestion_job(
            job_id=self.job_id,
            status_message="Starting CSV processing",
            status_code=IngestionStatus.IN_PROGRESS,
            metadata={},
        )
        await self.session.commit()

        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        filename = tmp_path.split("/")[-1]
        processing_path = f"processing/{self.job_id}/{filename}"

        logger.info(f"Moving file from {tmp_path} to {processing_path}")
        move_result = await self.files_store.move_file(tmp_path, processing_path)
        if not move_result:
            raise Exception(f"Failed to move file from {tmp_path} to {processing_path}")

        file_content, _ = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8")

        configured_data_entry_type_id = self.config.get("data_entry_type_id")
        if configured_data_entry_type_id is None:
            raise ValueError("data_entry_type_id is required for travel CSV ingestion")
        configured_data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = BaseModuleHandler.get_by_type(configured_data_entry_type)
        expected_columns = set(handler.create_dto.model_fields.keys())

        # --- Validate CSV headers against travel-specific columns ---
        logger.info("Validating travel CSV headers")
        try:
            await self._validate_csv_headers(
                csv_text,
                expected_columns=TRAVEL_CSV_ALL_COLUMNS,
                required_columns=TRAVEL_CSV_REQUIRED_COLUMNS,
            )
            logger.info("Travel CSV header validation passed")
        except ValueError as validation_error:
            error_message = str(validation_error)
            logger.error(f"Travel CSV validation failed: {error_message}")
            await self.repo.update_ingestion_job(
                job_id=self.job_id,
                status_message=f"Column validation failed: {error_message}",
                status_code=IngestionStatus.FAILED,
                metadata={"validation_error": error_message},
            )
            await self.session.commit()
            raise

        # --- Build IATA cache ---
        self._iata_cache = await self._build_iata_cache()

        return {
            "csv_text": csv_text,
            "entity_type": EntityType.MODULE_UNIT_SPECIFIC,
            "configured_data_entry_type_id": configured_data_entry_type_id,
            "handlers": [handler],
            # Travel handler has kind_field=None and require_factor_to_match=False,
            # so factors_map is never queried — skip the DB call entirely.
            "factors_map": {},
            "expected_columns": expected_columns,
            "required_columns": set(),
            "processing_path": processing_path,
            "filename": filename,
        }

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: StatsDict,
        max_row_errors: int,
    ) -> tuple[DataEntry | None, str | None, Any | None]:
        """Transform a travel CSV row then delegate to parent.

        Resolves IATA codes to location IDs and maps CSV columns to schema fields.
        """
        origin_iata = (row.get("from") or "").strip().upper()
        destination_iata = (row.get("to") or "").strip().upper()
        transport_mode = (row.get("transport_mode") or "").strip().lower()

        # Validate transport_mode is plane
        if transport_mode != "plane":
            error_msg = (
                f"Unsupported transport_mode '{transport_mode}': "
                "only 'plane' is supported"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        # Resolve origin IATA code
        origin_location_id = self._iata_cache.get(origin_iata)
        if not origin_location_id:
            error_msg = f"Origin '{origin_iata}' not found in locations"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        # Resolve destination IATA code
        destination_location_id = self._iata_cache.get(destination_iata)
        if not destination_location_id:
            error_msg = f"Destination '{destination_iata}' not found in locations"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        # Build transformed row with schema field names
        transformed_row: Dict[str, str] = {
            "transport_mode": "plane",
            "origin_location_id": str(origin_location_id),
            "destination_location_id": str(destination_location_id),
            "unit_id": str(self.unit_id),
        }

        # Map traveler_name (optional)
        traveler_name = (row.get("traveler_name") or "").strip()
        if traveler_name:
            transformed_row["traveler_name"] = traveler_name

        # Map sciper (optional → traveler_id)
        sciper = (row.get("sciper") or "").strip()
        if sciper:
            transformed_row["traveler_id"] = sciper

        # Pass through optional columns
        if row.get("departure_date", "").strip():
            transformed_row["departure_date"] = row["departure_date"].strip()
        if row.get("number_of_trips", "").strip():
            transformed_row["number_of_trips"] = row["number_of_trips"].strip()

        # Delegate to parent with the transformed row
        data_entry, err, factor = await super()._process_row(
            transformed_row, row_idx, setup_result, stats, max_row_errors
        )

        if data_entry and data_entry.data:
            for key in (
                "origin_location_id",
                "destination_location_id",
                "unit_id",
                "traveler_id",
                "number_of_trips",
            ):
                val = data_entry.data.get(key)
                if isinstance(val, float):
                    data_entry.data[key] = int(val)

        return data_entry, err, factor
