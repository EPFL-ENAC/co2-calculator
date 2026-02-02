"""Data entry emission repository for database operations."""

from typing import Dict

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import DataEntryEmission

logger = get_logger(__name__)


class DataEntryEmissionRepository:
    """Repository for data entry emission database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, obj: DataEntryEmission) -> DataEntryEmission:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: DataEntryEmission) -> DataEntryEmission:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_data_entry_id(
        self, data_entry_id: int
    ) -> DataEntryEmission | None:
        query = select(DataEntryEmission).where(
            DataEntryEmission.data_entry_id == data_entry_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def bulk_create(
        self, objs: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def get_stats(
        self,
        carbon_report_module_id,
        aggregate_by: str = "emission_type_id",
        aggregate_field: str = "kg_co2eq",
    ) -> Dict[str, float]:
        """Aggregate DataEntryEmission data by emission_type_id
                SELECT
            dee.*
        FROM
            data_entry_emission dee
        JOIN
            data_entry de ON dee.data_entry_id = de.id
        WHERE
            de.carbon_report_module_id = 'YOUR_REPORT_ID_HERE';
        """
        # 1. Get the model attributes dynamically
        group_field = getattr(DataEntryEmission, aggregate_by)
        sum_field = getattr(DataEntryEmission, aggregate_field)

        # 2. Build the query with the JOIN
        query = (
            select(
                group_field,
                func.sum(sum_field).label("total"),
            )
            .join(DataEntry, col(DataEntryEmission.data_entry_id) == col(DataEntry.id))
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
            )
            .group_by(group_field)
        )

        result = await self.session.execute(
            query
        )  # Changed .exec to .execute (Standard SQLAlchemy/SQLModel)
        rows = result.all()

        # 3. Format the results
        aggregation: Dict[str, float] = {}
        for key, total_count in rows:
            label = str(key) if key is not None else "unknown"
            aggregation[label] = float(total_count or 0.0)

        return aggregation
