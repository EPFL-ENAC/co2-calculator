from fastapi import BackgroundTasks
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.building_room import BuildingRoom
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.data_entry import DataEntryResponse
from app.schemas.user import UserRead
from app.services.building_room_service import BuildingRoomService
from app.services.data_entry_service import DataEntryService
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

logger = get_logger(__name__)


class EmbodiedEnergyWorkflow:
    """Workflow to calculate embodied energy emissions for a data entry."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def post_create(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry: DataEntryResponse,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Post-process the created data entry to calculate embodied energy."""
        data_entry_type = DataEntryTypeEnum(data_entry.data_entry_type_id)

        if data_entry_type == DataEntryTypeEnum.building:
            await self._post_create_building(
                carbon_report_module,
                data_entry,
                current_user,
                request_context,
                background_tasks,
            )

    async def post_update(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry: DataEntryResponse,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Post-process the updated data entry to recalculate
        embodied energy emissions.
        """
        data_entry_type = DataEntryTypeEnum(data_entry.data_entry_type_id)
        embodied_energy_entry_id = await self._get_embodied_energy_entry_id(
            carbon_report_module.id, data_entry.id
        )

        if data_entry_type == DataEntryTypeEnum.building:
            if embodied_energy_entry_id is None:
                await self._post_create_building(
                    carbon_report_module,
                    data_entry,
                    current_user,
                    request_context,
                    background_tasks,
                )
            else:
                await self._post_update_building(
                    embodied_energy_entry_id,
                    carbon_report_module,
                    data_entry,
                    current_user,
                    request_context,
                    background_tasks,
                )

    async def post_delete(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_id: int,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Post-process the deleted data entry to remove embodied energy emissions."""
        embodied_energy_entry_id = await self._get_embodied_energy_entry_id(
            carbon_report_module.id, data_entry_id
        )
        if embodied_energy_entry_id is not None:
            # Use the CarbonReportModuleWorkflow to delete
            # the embodied energy data entry
            carbon_report_module_workflow = CarbonReportModuleWorkflow(self.session)
            await carbon_report_module_workflow.delete(
                carbon_report_module=carbon_report_module,
                data_entry_id=embodied_energy_entry_id,
                current_user=current_user,
                request_context=request_context,
                background_tasks=background_tasks,
            )

    async def _post_create_building(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry: DataEntryResponse,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Calculate embodied energy emissions for a new building data entry."""
        embodied_energy_data = await self._resolve_embodied_energy_data(
            room_cache=None,
            data_entry_id=data_entry.id,
            data=data_entry.data,
        )
        if embodied_energy_data is None:
            return
        # Use the CarbonReportModuleWorkflow to create the embodied energy data entry
        carbon_report_module_workflow = CarbonReportModuleWorkflow(self.session)
        await carbon_report_module_workflow.create(
            carbon_report_module=carbon_report_module,
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy,
            item_data=embodied_energy_data,
            current_user=current_user,
            request_context=request_context,
            background_tasks=background_tasks,
        )

    async def _post_update_building(
        self,
        embodied_energy_entry_id: int,
        carbon_report_module: CarbonReportModuleRead,
        data_entry: DataEntryResponse,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        embodied_energy_data = await self._resolve_embodied_energy_data(
            room_cache=None,
            data_entry_id=data_entry.id,
            data=data_entry.data,
        )
        if embodied_energy_data is None:
            # Clean up, if needed
            await self.post_delete(
                carbon_report_module=carbon_report_module,
                data_entry_id=data_entry.id,
                current_user=current_user,
                request_context=request_context,
                background_tasks=background_tasks,
            )
        else:
            # Use the CarbonReportModuleWorkflow to update the
            # embodied energy data entry
            carbon_report_module_workflow = CarbonReportModuleWorkflow(self.session)
            await carbon_report_module_workflow.update(
                carbon_report_module=carbon_report_module,
                data_entry_type_id=DataEntryTypeEnum.building_embodied_energy,
                item_id=embodied_energy_entry_id,
                item_data=embodied_energy_data,
                current_user=current_user,
                request_context=request_context,
                background_tasks=background_tasks,
            )

    async def create_derived_entries_for(self, parent_entries: list[DataEntry]) -> int:
        """Bulk-create ``building_embodied_energy`` entries for freshly
        ingested ``building`` entries. Returns the number of rows inserted.

        Straight map-and-insert: the bulk ingest's delete-then-recreate has
        already removed stale derived entries, so no reconcile is needed. The
        whole ``BuildingRoom`` table is prefetched once so resolution never
        queries per row. Parents without resolvable reference data are
        skipped, same as the interactive path.
        """
        if not parent_entries:
            return 0
        rooms = await BuildingRoomService(self.session).list_rooms()
        room_cache = {room.room_name: room for room in rooms}
        derived_entries: list[DataEntry] = []
        for parent in parent_entries:
            if parent.id is None:
                continue
            embodied_energy_data = await self._resolve_embodied_energy_data(
                room_cache=room_cache,
                data_entry_id=parent.id,
                data=parent.data or {},
            )
            if embodied_energy_data is None:
                continue
            derived_entries.append(
                DataEntry(
                    data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
                    carbon_report_module_id=parent.carbon_report_module_id,
                    data=embodied_energy_data,
                    status=parent.status,
                    source=parent.source,
                    created_by_id=parent.created_by_id,
                    year=parent.year,
                    unit_id=parent.unit_id,
                )
            )
        if not derived_entries:
            logger.info(
                "create_derived_entries_for: no resolvable rooms among "
                f"{len(parent_entries)} building entries — nothing inserted"
            )
            return 0
        return await DataEntryService(self.session).bulk_copy(
            derived_entries, job_id=derived_entries[0].created_by_id
        )

    async def _resolve_embodied_energy_data(
        self,
        room_cache: dict[str, BuildingRoom] | None,
        data_entry_id: int,
        data: dict,
    ) -> dict | None:
        """Build a ``building_embodied_energy`` payload from a ``building`` entry.

        The room surface is resolved from the ``BuildingRoom`` reference table —
        never read off the source entry's ``.data``, which does not persist it.
        ``room_cache`` (a ``{room_name: BuildingRoom}`` map) replaces the
        per-room query for bulk callers; ``None`` falls back to a direct
        ``get_room`` call. Returns ``None`` when the entry or reference data is
        incomplete (skip, don't default).
        """
        building_name = data.get("building_name")
        room_name = data.get("room_name")
        if not building_name or not room_name:
            return None
        if room_cache is not None:
            room = room_cache.get(room_name)
        else:
            room = await BuildingRoomService(self.session).get_room(room_name=room_name)
        if room is None or room.room_surface_square_meter is None:
            return None
        return {
            "data_entry_id": data_entry_id,
            "building_name": building_name,
            "room_surface_square_meter": room.room_surface_square_meter,
        }

    async def _get_embodied_energy_entry_id(
        self, carbon_report_module_id: int, data_entry_id: int
    ) -> int | None:
        """Get the embodied energy data entry id corresponding
        to a data entry in a carbon report.
        """
        statement = select(DataEntry.id).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            DataEntry.data["data_entry_id"].as_integer() == data_entry_id,
        )
        result = await self.session.exec(statement)
        return result.one_or_none()
