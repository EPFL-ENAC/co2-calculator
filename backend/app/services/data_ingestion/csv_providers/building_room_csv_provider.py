"""CSV provider for Buildings/Rooms ingestion with building_rooms lookup enrichment."""

from typing import Any, Dict, List, Optional

from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.models.factor import Factor
from app.models.user import User
from app.repositories.building_room_repo import BuildingRoomRepository
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
    _get_expected_columns_from_handlers,
    _get_required_columns_from_handler,
)

logger = get_logger(__name__)


class BuildingRoomCSVProvider(BaseCSVProvider):
    """Ingest building-room rows and enrich from `building_rooms`."""

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        *,
        data_session: Any,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self._room_repo = BuildingRoomRepository(self.data_session)
        self._kwh_cache: Dict[tuple[str, str, str], Optional[float]] = {}

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """Setup handlers/header rules while reusing BaseCSVProvider setup flow."""
        configured_data_entry_type_id = self.config.get("data_entry_type_id")
        if configured_data_entry_type_id is None:
            raise ValueError(
                "data_entry_type_id is required for building CSV ingestion"
            )

        configured_data_entry_type = DataEntryTypeEnum(configured_data_entry_type_id)
        handler = BaseModuleHandler.get_by_type(configured_data_entry_type)
        handlers = [handler]

        await self._load_kwh_cache()

        return {
            "handlers": handlers,
            "factors_map": {},
            "expected_columns": _get_expected_columns_from_handlers(handlers),
            "required_columns": _get_required_columns_from_handler(handler),
        }

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

    async def _load_kwh_cache(self) -> None:
        """Load building energy factors.

        Cache key is (building_name, room_type, category).
        """
        stmt = select(Factor).where(
            col(Factor.data_entry_type_id) == DataEntryTypeEnum.building.value,
            col(Factor.is_conversion) == False,  # noqa: E712
        )
        result = await self.data_session.exec(stmt)
        factors = result.all()
        for factor in factors:
            classification = factor.classification or {}
            building_name = classification.get("kind", "")
            room_type = classification.get("room_type", "")
            category = classification.get("subkind", "")
            kwh = (factor.values or {}).get("category_kwh_per_square_meter")
            if building_name and room_type and category:
                key = (building_name, room_type, category)
                self._kwh_cache[key] = kwh

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: StatsDict,
        max_row_errors: int,
        unit_to_module_map: Dict[str, int] | None = None,
    ) -> tuple[DataEntry | None, str | None, Any | None]:
        """Resolve room from building_rooms.

        Then transform the row into a building-room payload.
        """
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

        room, room_error = await self._retrieve_building_room(
            building_name=building_name,
            room_name=room_name,
            building_location=building_location,
        )
        if room_error:
            self._record_row_error(stats, row_idx, room_error, max_row_errors)
            return None, room_error, None

        if room is None:
            error_msg = "No building room could be resolved"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

        room_type = room.room_type or ""
        transformed_row = {**row, **room.model_dump(exclude_none=True)}

        # Inject per-category kwh values from factor cache
        for category in ("heating", "cooling", "ventilation", "lighting"):
            kwh = self._kwh_cache.get((building_name, room_type, category))
            transformed_row[f"{category}_kwh_per_square_meter"] = kwh

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

    async def _retrieve_building_room(
        self,
        building_name: str,
        room_name: str,
        building_location: str,
    ) -> tuple[Any | None, str | None]:
        """Retrieve and disambiguate room data from building_rooms."""
        if building_location:
            rooms = await self._room_repo.list_rooms(
                building_location=building_location,
            )
            rooms = [
                r
                for r in rooms
                if r.building_name == building_name and r.room_name == room_name
            ]
        else:
            rooms = await self._room_repo.list_rooms(
                building_name=building_name,
            )
            rooms = [r for r in rooms if r.room_name == room_name]

        if not rooms:
            where = (
                f"building_location='{building_location}', "
                if building_location
                else ""
            )
            return None, (
                f"No building room found for {where}"
                f"building_name='{building_name}', room_name='{room_name}'"
            )

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
                return rooms[0], None
            return None, (
                "Ambiguous building room match; provide building_location "
                f"for building_name='{building_name}', room_name='{room_name}'"
            )

        return rooms[0], None
