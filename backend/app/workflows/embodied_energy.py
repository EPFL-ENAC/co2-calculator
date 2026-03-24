from fastapi import BackgroundTasks
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.data_entry import DataEntryResponse
from app.schemas.user import UserRead
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow


class EmbodiedEnergyWorkflow:
    """
    Workflow to calculate embodied energy emissions for a data entry.
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
        """
        Post-process the created data entry to calculate embodied energy emissions.
        """
        data_entry_type = DataEntryTypeEnum(data_entry.data_entry_type_id)

        if data_entry_type == DataEntryTypeEnum.building:
            return await self._post_create_building(
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
        # Delete the existing embodied energy data entry
        # corresponding to this data entry, if it exists
        await self.post_delete(
            carbon_report_module,
            data_entry.id,
            current_user,
            request_context,
            background_tasks,
        )
        # Create a new embodied energy data entry based on the updated data entry
        await self.post_create(
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
        building_name = data_entry.data.get("building_name")
        if not building_name:
            return
        room_surface_square_meter = data_entry.data.get("room_surface_square_meter")
        if room_surface_square_meter is None:
            return
        # Create a data entry for the embodied energy emissions
        # based on the building data entry
        embodied_energy_data = {
            "data_entry_id": data_entry.id,
            "building_name": building_name,
            "room_surface_square_meter": room_surface_square_meter,
        }
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
