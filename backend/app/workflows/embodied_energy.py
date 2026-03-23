from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.schemas.data_entry import DataEntryResponse


class EmbodiedEnergyWorkflow:
    """
    Workflow to calculate embodied energy emissions for a data entry.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def post_process(self, data_entry: DataEntryResponse) -> float | None:
        """
        Post-process the data entry to calculate embodied energy emissions.
        """
        data_entry_type = DataEntryTypeEnum(data_entry.data_entry_type_id)

        if data_entry_type == DataEntryTypeEnum.building:
            return await self._post_process_building(data_entry)

        return None

    async def _post_process_building(
        self, data_entry: DataEntryResponse
    ) -> float | None:
        """Calculate embodied energy emissions for a building data entry."""
        building_name = data_entry.data.get("building_name")
        if not building_name:
            return None
        room_surface_square_meter = data_entry.data.get("room_surface_square_meter")
        if room_surface_square_meter is None:
            return None

        # For demonstration purposes, we'll return a fixed value.
        return 10000.0  # kg CO2e as a placeholder value
