from collections import Counter

from fastapi import BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.data_entry import DataEntryResponse
from app.schemas.user import UserRead
from app.services.data_entry_service import DataEntryService
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

logger = get_logger(__name__)


class EmbodiedEnergyWorkflow:
    """Keeps ``building_embodied_energy`` companion entries in sync with the
    module's ``building`` entries — one companion per parent ``room_name``.
    """

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
        if (
            DataEntryTypeEnum(data_entry.data_entry_type_id)
            == DataEntryTypeEnum.building
        ):
            await self._reconcile(
                carbon_report_module, current_user, request_context, background_tasks
            )

    async def post_update(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry: DataEntryResponse,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        if (
            DataEntryTypeEnum(data_entry.data_entry_type_id)
            == DataEntryTypeEnum.building
        ):
            await self._reconcile(
                carbon_report_module, current_user, request_context, background_tasks
            )

    async def post_delete(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_type_id: int,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        if DataEntryTypeEnum(data_entry_type_id) == DataEntryTypeEnum.building:
            await self._reconcile(
                carbon_report_module, current_user, request_context, background_tasks
            )

    async def _reconcile(
        self,
        carbon_report_module: CarbonReportModuleRead,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Converge the companion multiset onto the parents' ``room_name``s.

        Reads fresh post-commit state, so no knowledge of the mutated
        entry's previous shape is needed: surplus companions (falsy or
        over-represented names, highest ids first) are deleted, missing
        ones created. The companion set is a pure function of the parents.
        """
        entries = await DataEntryRepository(self.session).list_by_module(
            carbon_report_module.id
        )
        want: Counter[str] = Counter(
            name
            for e in entries
            if e.data_entry_type_id == DataEntryTypeEnum.building.value
            and (name := (e.data or {}).get("room_name"))
        )

        surplus_ids: list[int] = []
        companions_by_name: dict[str, list[int]] = {}
        for e in entries:
            if (
                e.data_entry_type_id != DataEntryTypeEnum.building_embodied_energy.value
                or e.id is None
            ):
                continue
            name = (e.data or {}).get("room_name")
            if not name:
                surplus_ids.append(e.id)
            else:
                companions_by_name.setdefault(name, []).append(e.id)
        for name, ids in companions_by_name.items():
            extra = len(ids) - want.get(name, 0)
            if extra > 0:
                surplus_ids.extend(sorted(ids, reverse=True)[:extra])

        workflow = CarbonReportModuleWorkflow(self.session)
        for entry_id in surplus_ids:
            await workflow.delete(
                carbon_report_module=carbon_report_module,
                data_entry_id=entry_id,
                current_user=current_user,
                request_context=request_context,
                background_tasks=background_tasks,
            )
        for name, wanted in want.items():
            kept = min(len(companions_by_name.get(name, [])), wanted)
            for _ in range(wanted - kept):
                await workflow.create(
                    carbon_report_module=carbon_report_module,
                    data_entry_type_id=(
                        DataEntryTypeEnum.building_embodied_energy.value
                    ),
                    item_data={"room_name": name},
                    current_user=current_user,
                    request_context=request_context,
                    background_tasks=background_tasks,
                )

    async def create_derived_entries_for(self, entries: list[DataEntry]) -> int:
        """Bulk-create ``building_embodied_energy`` rows for the freshly
        ingested ``building`` entries among ``entries``. Returns the number
        of rows inserted.

        Callers pass a whole ingest batch — this workflow owns the
        knowledge of which rows it derives from, so non-``building`` rows
        are ignored here. Pure map: the persisted payload is just
        ``{"room_name"}``; building data resolves from ``BuildingRoom`` at
        compute/read time. The bulk ingest's delete-then-recreate has
        already removed stale derived entries, so no reconcile is needed.
        """
        derived_entries = [
            DataEntry(
                data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
                carbon_report_module_id=parent.carbon_report_module_id,
                data={"room_name": room_name},
                status=parent.status,
                source=parent.source,
                created_by_id=parent.created_by_id,
                year=parent.year,
                unit_id=parent.unit_id,
            )
            for parent in entries
            if parent.data_entry_type_id == DataEntryTypeEnum.building.value
            and (room_name := (parent.data or {}).get("room_name"))
        ]
        if not derived_entries:
            logger.info(
                "create_derived_entries_for: no building entry with a "
                f"room_name among {len(entries)} rows — nothing inserted"
            )
            return 0
        return await DataEntryService(self.session).bulk_copy(
            derived_entries, job_id=derived_entries[0].created_by_id
        )
