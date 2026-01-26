"""Data entry emission repository for database operations."""

from sqlmodel import col, delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry_emission import DataEntryEmission

logger = get_logger(__name__)


class DataEntryEmissionRepository:
    """Repository for data entry emission database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_data_entry_emissions_by_data_entry_id(
        self, data_entry_id: int
    ) -> None:
        """Delete all emissions associated with a specific data entry."""

        # This is the standard SQLModel / SQLAlchemy 2.0 way
        delete_stmt = delete(DataEntryEmission).where(
            col(DataEntryEmission.data_entry_id) == col(data_entry_id)
        )

        await self.session.execute(delete_stmt)
        # Note: Usually, you commit in the Service, not the Repo,
        # but if this is a standalone operation, commit is fine.
        await self.session.commit()

        logger.info(f"Deleted emissions for data_entry_id: {data_entry_id}")
