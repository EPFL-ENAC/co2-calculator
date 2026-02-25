"""CSV provider for Buildings/Rooms ingestion with Archibus lookup enrichment."""

from typing import Any, Dict, List, Optional

from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionStatus
from app.models.user import User
from app.repositories.archibus_room_repo import ArchibusRoomRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.services.data_ingestion.base_csv_provider import BaseCSVProvider, StatsDict

logger = get_logger(__name__)

BUILDING_ROOM_CSV_REQUIRED_COLUMNS = {"building_name", "room_name"}
BUILDING_ROOM_CSV_OPTIONAL_COLUMNS = {
    "building_location",
    "room_type",
    "room_surface_square_meter",
    "note",
}
BUILDING_ROOM_CSV_ALL_COLUMNS = (
    BUILDING_ROOM_CSV_REQUIRED_COLUMNS | BUILDING_ROOM_CSV_OPTIONAL_COLUMNS
)


class BuildingRoomCSVProvider(BaseCSVProvider):
    """Ingest building-room rows and enrich from `archibus_rooms`."""

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        *,
        data_session: Any,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self._room_repo = ArchibusRoomRepository(self.data_session)
        self._unit_institutional_ids: Optional[list[str]] = None

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """Not used - this provider overrides setup directly."""
        raise NotImplementedError(
            "BuildingRoomCSVProvider overrides _setup_and_validate directly"
        )

    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """Building-room CSV uses a single handler; factor lookup not needed."""
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
        """Resolve building-room handler (single handler, no factor requirement)."""
        handlers = setup_result["handlers"]
        configured_data_entry_type_id = int(self.config["data_entry_type_id"])
        data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = handlers[0] if handlers else None
        if not handler:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg
        return data_entry_type, handler, None

    async def _setup_and_validate(self) -> Dict[str, Any]:
        """Setup phase: move file, load CSV, validate building-room headers."""
        self._unit_institutional_ids = await self._load_unit_institutional_ids()
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
            raise ValueError(
                "data_entry_type_id is required for building CSV ingestion"
            )
        configured_data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = BaseModuleHandler.get_by_type(configured_data_entry_type)
        expected_columns = set(handler.create_dto.model_fields.keys())

        logger.info("Validating building room CSV headers")
        try:
            await self._validate_csv_headers(
                csv_text,
                expected_columns=BUILDING_ROOM_CSV_ALL_COLUMNS,
                required_columns=BUILDING_ROOM_CSV_REQUIRED_COLUMNS,
            )
            logger.info("Building room CSV header validation passed")
        except ValueError as validation_error:
            error_message = str(validation_error)
            logger.error(f"Building room CSV validation failed: {error_message}")
            await self.repo.update_ingestion_job(
                job_id=self.job_id,
                status_message=f"Column validation failed: {error_message}",
                status_code=IngestionStatus.FAILED,
                metadata={"validation_error": error_message},
            )
            await self.data_session.commit()
            raise

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

    @staticmethod
    def _normalize_unit_institutional_ids(
        cost_centers: list, provider_code: Optional[str]
    ) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in cost_centers:
            value = str(item).strip()
            if value and value not in seen:
                seen.add(value)
                normalized.append(value)
        if provider_code:
            provider = str(provider_code).strip()
            if provider and provider not in seen:
                seen.add(provider)
                normalized.append(provider)
        return normalized

    async def _load_unit_institutional_ids(self) -> Optional[list[str]]:
        """Resolve allowed Archibus unit IDs from the ingestion's module context."""
        if not self.carbon_report_module_id:
            return None

        stmt = (
            select(CarbonReport.unit_id)
            .select_from(CarbonReportModule)
            .join(
                CarbonReport,
                col(CarbonReport.id) == col(CarbonReportModule.carbon_report_id),
            )
            .where(CarbonReportModule.id == self.carbon_report_module_id)
        )
        result = await self.data_session.exec(stmt)
        unit_id = result.one_or_none()
        if unit_id is None:
            return None

        unit = await UnitRepository(self.data_session).get_by_id(unit_id)
        if unit is None:
            return None

        return self._normalize_unit_institutional_ids(
            unit.cost_centers or [],
            unit.provider_code,
        )

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: StatsDict,
        max_row_errors: int,
        unit_to_module_map: Dict[str, int] | None = None,
    ) -> tuple[DataEntry | None, str | None, Any | None]:
        """Resolve room from Archibus and transform row to building-room payload."""
        building_name = (row.get("building_name") or "").strip()
        room_name = (row.get("room_name") or "").strip()
        building_location = (row.get("building_location") or "").strip()
        note = (row.get("note") or "").strip()

        if not building_name:
            error_msg = "Missing required value for 'building_name'"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None
        if not room_name:
            error_msg = "Missing required value for 'room_name'"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        if building_location:
            rooms = await self._room_repo.list_rooms(
                unit_institutional_ids=self._unit_institutional_ids,
                building_location=building_location,
            )
            rooms = [
                r
                for r in rooms
                if r.building_name == building_name and r.room_name == room_name
            ]
        else:
            rooms = await self._room_repo.list_rooms(
                unit_institutional_ids=self._unit_institutional_ids,
                building_name=building_name,
            )
            rooms = [r for r in rooms if r.room_name == room_name]

        if not rooms:
            where = (
                f"building_location='{building_location}', "
                if building_location
                else ""
            )
            error_msg = (
                f"No Archibus room found for {where}"
                f"building_name='{building_name}', room_name='{room_name}'"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        if len(rooms) > 1:
            unique_values = {
                (
                    r.building_location,
                    r.building_name,
                    r.room_name,
                    r.room_type,
                    r.room_surface_square_meter,
                )
                for r in rooms
            }
            if len(unique_values) == 1:
                room = rooms[0]
            else:
                error_msg = (
                    "Ambiguous Archibus match; provide building_location "
                    f"for building_name='{building_name}', room_name='{room_name}'"
                )
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None
        else:
            room = rooms[0]
        transformed_row: Dict[str, str] = {
            "building_name": room.building_name,
            "room_name": room.room_name,
        }
        csv_room_type = (row.get("room_type") or "").strip()
        if room.room_type:
            transformed_row["room_type"] = room.room_type
        elif csv_room_type:
            transformed_row["room_type"] = csv_room_type

        if room.room_surface_square_meter is not None:
            transformed_row["room_surface_square_meter"] = str(
                room.room_surface_square_meter
            )
        elif (row.get("room_surface_square_meter") or "").strip():
            transformed_row["room_surface_square_meter"] = row[
                "room_surface_square_meter"
            ].strip()

        if room.heating_kwh_per_square_meter is not None:
            transformed_row["heating_kwh_per_square_meter"] = str(
                room.heating_kwh_per_square_meter
            )
        if room.cooling_kwh_per_square_meter is not None:
            transformed_row["cooling_kwh_per_square_meter"] = str(
                room.cooling_kwh_per_square_meter
            )
        if room.ventilation_kwh_per_square_meter is not None:
            transformed_row["ventilation_kwh_per_square_meter"] = str(
                room.ventilation_kwh_per_square_meter
            )
        if room.lighting_kwh_per_square_meter is not None:
            transformed_row["lighting_kwh_per_square_meter"] = str(
                room.lighting_kwh_per_square_meter
            )

        if note:
            transformed_row["note"] = note

        return await super()._process_row(
            transformed_row,
            row_idx,
            setup_result,
            stats,
            max_row_errors,
            unit_to_module_map,
        )
