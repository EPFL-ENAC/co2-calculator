"""Data entry emission repository for database operations."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry_emission import DataEntryEmission
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository

logger = get_logger(__name__)


class DataEntryEmissionRepository:
    """Repository for data entry emission database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.carbon_report_module_repo = CarbonReportModuleRepository(session)

    async def delete_data_entry_emissions_by_data_entry_id(
        self, data_entry_id: int
    ) -> None:
        """Delete data entry emissions by data entry ID."""
        delete_stmt = DataEntryEmission.__table__.delete().where(
            DataEntryEmission.data_entry_id == data_entry_id
        )
        await self.session.execute(delete_stmt)
        await self.session.commit()
