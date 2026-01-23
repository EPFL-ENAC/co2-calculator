"""Headcount repository for database operations."""

from typing import Dict, Optional

from pydantic import BaseModel
from sqlalchemy import Float, Select, cast, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import DataEntryEmission
from app.models.data_entry_type import DataEntryType, DataEntryTypeEnum
from app.models.factor import Factor
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report_response import SubmoduleResponse, SubmoduleSummary
from app.schemas.data_entry import FLATTENERS, DataEntryUpdate

logger = get_logger(__name__)


class DataEntryRepository:
    """Repository for data entry database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.carbon_report_module_repo = CarbonReportModuleRepository(session)

    async def get(self, id: int) -> Optional[DataEntry]:
        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def create(self, data: DataEntry) -> DataEntry:
        # 1. Convert Input Model to Table Model

        db_obj = DataEntry.model_validate({**data.dict()})

        # 3. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self, id: int, data: DataEntryUpdate, user_id: int
    ) -> Optional[DataEntry]:
        # 1. Fetch the existing record

        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.exec(statement)
        db_obj = result.one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # 4. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        # 1. Fetch the existing record
        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return False

        # 2. Delete
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def get_list(
        self,
        carbon_report_module_id: int,
        # unit_id,
        # year,
        limit,
        offset,
        sort_by,
        sort_order,
        filter: Optional[str] = None,
    ) -> list[DataEntry]:
        statement = select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(DataEntry, sort_by).asc())
        else:
            statement = statement.order_by(getattr(DataEntry, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_data_entry_type_ids_for_module_type(
        self, module_type_id: int
    ) -> list[int]:
        # Example: adjust according to your actual model/table
        from app.models.data_entry_type import DataEntryType

        stmt = select(DataEntryType.id).where(
            DataEntryType.module_type_id == module_type_id
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_module_type_id_for_carbon_report_module(
        self, carbon_report_module_id: int
    ) -> Optional[int]:
        return await self.carbon_report_module_repo.get_module_type(
            carbon_report_module_id
        )

    async def get_total_count_by_submodule(
        self, carbon_report_module_id: int
    ) -> Dict[int, int]:
        """
        Docstring for get_total_count_by_submodule

        :param self: Description
        :param carbon_report_module_id: Description
        :type carbon_report_module_id: int
        :return: Description
        :rtype: Dict[int, int]

        Dict mapping submodule (data_entry_type_id) to total item count:
            {
                1: 10,
                2: 5,
                ...
            }
        """
        # Determine module_type_id from carbon_report_module_id

        module_type_id = await self.get_module_type_id_for_carbon_report_module(
            carbon_report_module_id
        )
        if module_type_id is None:
            return {}
        all_type_ids = await self.get_data_entry_type_ids_for_module_type(
            module_type_id
        )

        # Get actual counts from DB
        query: Select = (
            select(
                DataEntry.data_entry_type_id,
                func.count().label("total_count"),
            )
            .where(DataEntry.carbon_report_module_id == carbon_report_module_id)
            .group_by(DataEntry.data_entry_type_id)
        )
        result = await self.session.execute(query)
        rows = list(result.all())
        aggregation: Dict[int, int] = {
            data_entry_type_id: int(total_count)
            for data_entry_type_id, total_count in rows
        }

        # Fill in zeros for missing types
        for type_id in all_type_ids:
            if type_id not in aggregation:
                aggregation[type_id] = 0

        return aggregation

    async def get_submodule_data(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
        filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        statement = (
            select(DataEntry, DataEntryEmission, Factor)
            .join(DataEntryEmission, DataEntry.id == DataEntryEmission.data_entry_id)
            .outerjoin(Factor, DataEntryEmission.primary_factor_id == Factor.id)
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
                DataEntry.data_entry_type_id == data_entry_type_id,
            )
        )

        filter_pattern = ""
        if filter:
            filter = filter.strip()
            # max filter for security
            if len(filter) > 100:
                filter = filter[:100]
            # check for empty or only-wildcard filters and handle accordingly.
            if filter == "" or filter == "%" or filter == "*":
                filter = None

        if filter:
            filter_pattern = f"%{filter}%"
            statement = statement.where(
                (col(DataEntry.data["name"]).ilike(filter_pattern))
            )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(DataEntry, sort_by).asc())
        else:
            statement = statement.order_by(getattr(DataEntry, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)

        # Query for total count (for pagination)
        count_stmt = select(func.count()).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == data_entry_type_id,
        )
        if filter and filter_pattern != "":
            count_stmt = count_stmt.where(
                (col(DataEntry.data["name"]).ilike(filter_pattern))
            )
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        rows = result.all()
        count = len(rows)

        items: list[BaseModel] = []

        for data_entry, data_entry_emission, primary_factor in rows:
            flattener = FLATTENERS[DataEntryTypeEnum(data_entry.data_entry_type_id)]
            data_entry.data = {
                **data_entry.data,
                "emission": data_entry_emission.kg_co2eq,
                "primary_factor": primary_factor.values if primary_factor else None,
            }
            items.append(flattener(data_entry))

        response = SubmoduleResponse(
            id=data_entry_type_id,
            count=count,
            items=items,
            summary=SubmoduleSummary(
                total_items=total_items,
                annual_consumption_kwh=0.0,
                total_kg_co2eq=0.0,
                annual_fte=0.0,
            ),
            has_more=total_items > offset + count,
        )
        return response

    async def get_module_stats(
        self, carbon_report_module_id: int, aggregate_by: str = "submodule"
    ) -> Dict[str, float]:
        """Aggregate headcount data by submodule or function."""
        group_field = DataEntry.data[aggregate_by].astext

        # TODO MAKE module_type agnostic!
        query = (
            select(
                group_field.label(aggregate_by),
                func.sum(cast(DataEntry.data["fte"].astext, Float)).label("annual_fte"),
            )
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
            )
            .group_by(group_field)
        )

        result = await self.session.exec(query)
        rows = list(result.all())

        aggregation: Dict[str, float] = {}
        for key, total_count in rows:
            if key is None:
                aggregation["unknown"] = float(total_count)
            else:
                aggregation[key] = float(total_count)

        logger.debug(f"Aggregated headcount by {aggregate_by}: {aggregation}")

        return aggregation
