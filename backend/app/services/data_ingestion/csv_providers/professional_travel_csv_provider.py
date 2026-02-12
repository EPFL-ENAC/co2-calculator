"""Travel CSV provider for professional travel data ingestion (planes and trains).

Extends the generic BaseCSVProvider with:
- IATA code → location ID resolution (planes)
- Exact name → location ID resolution (trains)
- Column mapping: from/to → origin_location_id/destination_location_id
- Column mapping: sciper → traveler_id

"""

from typing import Any, Dict, List

from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionStatus
from app.models.location import Location, TransportModeEnum
from app.models.user import User
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
)

logger = get_logger(__name__)

# Columns the user provides in the travel CSV
TRAVEL_CSV_REQUIRED_COLUMNS = {"transport_mode", "from", "to", "traveler_name"}
TRAVEL_CSV_OPTIONAL_COLUMNS = {
    "departure_date",
    "sciper",
    "number_of_trips",
}
TRAVEL_CSV_ALL_COLUMNS = TRAVEL_CSV_REQUIRED_COLUMNS | TRAVEL_CSV_OPTIONAL_COLUMNS


class ProfessionalTravelCSVProvider(BaseCSVProvider):
    """Provider to ingest professional travel data from CSV files (planes and trains).

    Overrides the generic CSV provider to:
    1. Accept user-friendly columns (from/to as IATA codes for planes,
       exact station names for trains, sciper)
    2. Resolve IATA codes (planes) or exact names (trains) to location IDs
       via in-memory caches
    3. Transform rows into the format expected by ProfessionalTravelHandlerCreate
    """

    SUPPORTED_TRANSPORT_MODES = {mode.value for mode in TransportModeEnum}

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        *,
        data_session: Any,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self._iata_cache: Dict[str, int] = {}
        self._train_name_cache: Dict[str, int] = {}

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """Not used — _setup_and_validate is fully overridden."""
        raise NotImplementedError(
            "ProfessionalTravelCSVProvider overrides _setup_and_validate directly"
        )

    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """Travel has a single handler — kind/subkind extraction is not needed."""
        return "", None

    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, ModuleHandler | None, str | None]:
        """Resolve handler for travel rows (single handler, no factor validation)."""
        handlers = setup_result["handlers"]
        configured_data_entry_type_id = int(self.config["data_entry_type_id"])
        data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = handlers[0] if handlers else None
        if not handler:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg
        return data_entry_type, handler, None

    async def _build_iata_cache(self) -> Dict[str, int]:
        """Build in-memory IATA code → location ID lookup for planes."""
        stmt = select(col(Location.iata_code), col(Location.id)).where(
            Location.transport_mode == TransportModeEnum.plane,
            col(Location.iata_code).isnot(None),
        )
        result = await self.data_session.execute(stmt)
        cache = {row.iata_code.upper(): row.id for row in result.all()}
        logger.info("Built IATA cache with %d entries", len(cache))
        return cache

    async def _build_train_name_cache(self) -> Dict[str, int]:
        """Build in-memory exact name → location ID lookup for train stations."""
        stmt = select(col(Location.name), col(Location.id)).where(
            Location.transport_mode == TransportModeEnum.train,
        )
        result = await self.data_session.execute(stmt)
        cache = {row.name: row.id for row in result.all()}
        logger.info("Built train name cache with %d entries", len(cache))
        return cache

    async def _setup_and_validate(self) -> Dict[str, Any]:
        """Setup phase: file handling, IATA cache, travel-specific header validation.

        Overrides parent to:
        - Validate against travel CSV columns (from/to) instead of schema columns
        - Build IATA location cache

        """

        await self.repo.update_ingestion_job(
            job_id=self.job_id,
            status_message="Starting CSV processing",
            status_code=IngestionStatus.IN_PROGRESS,
            metadata={},
        )
        await self.data_session.commit()

        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing source_file_path in config")
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
            await self.data_session.commit()
            raise

        # --- Build location caches ---
        self._iata_cache = await self._build_iata_cache()
        self._train_name_cache = await self._build_train_name_cache()

        return {
            "csv_text": csv_text,
            "entity_type": EntityType.MODULE_UNIT_SPECIFIC,
            "configured_data_entry_type_id": configured_data_entry_type_id,
            "handlers": [handler],
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
        unit_to_module_map: Dict[str, int] | None = None,
    ) -> tuple[DataEntry | None, str | None, Any | None]:
        """Transform a travel CSV row then delegate to parent.

        Resolves IATA codes to location IDs and maps CSV columns to schema fields.
        """
        origin_raw = (row.get("from") or "").strip()
        destination_raw = (row.get("to") or "").strip()
        transport_mode = (row.get("transport_mode") or "").strip().lower()

        # Validate transport_mode
        if transport_mode not in self.SUPPORTED_TRANSPORT_MODES:
            error_msg = (
                f"Unsupported transport_mode '{transport_mode}': "
                f"only {sorted(self.SUPPORTED_TRANSPORT_MODES)} are supported"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        # Resolve origin and destination based on transport mode
        if transport_mode == TransportModeEnum.plane:
            origin_location_id = self._iata_cache.get(origin_raw.upper())
            destination_location_id = self._iata_cache.get(destination_raw.upper())
            origin_label, destination_label = (
                origin_raw.upper(),
                destination_raw.upper(),
            )
        elif transport_mode == TransportModeEnum.train:
            origin_location_id = self._train_name_cache.get(origin_raw)
            destination_location_id = self._train_name_cache.get(destination_raw)
            origin_label, destination_label = origin_raw, destination_raw

        if not origin_location_id:
            error_msg = f"Origin '{origin_label}' not found in locations"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        if not destination_location_id:
            error_msg = f"Destination '{destination_label}' not found in locations"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        # Build transformed row with schema field names
        transformed_row: Dict[str, str] = {
            "transport_mode": transport_mode,
            "origin_location_id": str(origin_location_id),
            "destination_location_id": str(destination_location_id),
        }

        # Map traveler_name (required)
        traveler_name = (row.get("traveler_name") or "").strip()
        if not traveler_name:
            error_msg = "Missing required value for 'traveler_name'"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None
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
            transformed_row,
            row_idx,
            setup_result,
            stats,
            max_row_errors,
            unit_to_module_map,
        )

        if data_entry and data_entry.data:
            for key in (
                "origin_location_id",
                "destination_location_id",
                "traveler_id",
                "number_of_trips",
            ):
                val = data_entry.data.get(key)
                if isinstance(val, float) and val.is_integer():
                    data_entry.data[key] = int(val)

        return data_entry, err, factor
