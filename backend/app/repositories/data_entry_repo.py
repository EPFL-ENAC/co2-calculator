"""Headcount repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Float, cast, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger

# from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
# from app.schemas.equipment import SubmoduleResponse, SubmoduleSummary
from app.models.data_entry import DataEntry
from app.schemas.data_entry import DataEntryCreate, DataEntryUpdate
from app.schemas.equipment import SubmoduleResponse, SubmoduleSummary

logger = get_logger(__name__)


# # TODO: get role should be done in the frontend, hidden from the user!
#         function_role = get_function_role(data.function or "")
#         if data.submodule == "student" and function_role != "student":
#             function_role = "student"
#         db_obj = HeadCount.model_validate(
#             {**data.dict(), "function_role": function_role}
#         )


class DataEntryRepository:
    """Repository for data entry database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def create(self, data: DataEntry) -> DataEntry:
        """Create a new headcount record."""
        # 1. Convert Input Model to Table Model

        # function_role = get_function_role(data.function or "")
        # if data.submodule == "student" and function_role != "student":
        #     function_role = "student"
        db_obj = DataEntry.model_validate({**data.dict()})

        # 3. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self, id: int, data: DataEntryUpdate, user_id: str
    ) -> Optional[DataEntry]:
        """Update an existing headcount record."""
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

        # add function_role update
        # if "function" in update_data:
        #     function_role = get_function_role(update_data["function"])
        #     if db_obj.submodule == "student" and function_role != "student":
        #         function_role = "student"
        #     db_obj.function_role = function_role

        # 3. Add System-Determined Fields
        db_obj.updated_by = user_id
        db_obj.updated_at = datetime.now(timezone.utc)

        # 4. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        """Delete a headcount record."""
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
        unit_id,
        year,
        limit,
        offset,
        sort_by,
        sort_order,
        filter: Optional[str] = None,
    ) -> list[DataEntry]:
        """Get headcount record by unit_id and year."""
        statement = select(DataEntry).where(
            DataEntry.unit_id == unit_id,
            # DataEntry.year == year,
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(DataEntry, sort_by).asc())
        else:
            statement = statement.order_by(getattr(DataEntry, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_summary_by_submodule(
        self, carbon_report_module_id: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregated summary statistics grouped by submodule.

        Args:
            session: Database session
            unit_id: Filter by unit ID
            status: Filter by equipment status

        Returns:
            Dict mapping submodule to summary stats:
            {
                "scientific": {
                    "total_items": 10,
                    "annual_consumption_kwh": 1500.0,
                    "total_kg_co2eq": 187.5
                },
                ...
            }
        """
        # Build query with aggregation
        query = select(
            DataEntry.data_entry_type_id.label("submodule"),
            func.count(col(DataEntry.id)).label("total_items"),
            func.sum(DataEntry.data["fte"]).label("annual_fte"),
        ).group_by(DataEntry.data_entry_type_id)

        # Apply filters
        if carbon_report_module_id:
            query = query.where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id
            )

        # Execute query
        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dict
        summary: Dict[str, Dict[str, Any]] = {}
        for submodule, total_items, annual_fte in rows:
            summary[submodule] = {
                "total_items": int(total_items),
                "annual_fte": float(annual_fte or 0),
                "annual_consumption_kwh": None,
                "total_kg_co2eq": None,
            }

        logger.debug(f"Retrieved summary for {len(summary)} submodules")

        return summary

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
        """Get headcount record by unit_id, year, and submodule."""
        statement = select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == data_entry_type_id,
        )

        if filter:
            filter.strip()
            # max filter for security
            if len(filter) > 100:
                filter = filter[:100]
            # check for empty or only-wildcard filters and handle accordingly.
            if filter == "" or filter == "%" or filter == "*":
                filter = None

        if filter:
            filter_pattern = f"%{filter}%"
            statement = statement.where(
                (col(DataEntry.display_name).ilike(filter_pattern))
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
            # DataEntry.year == year,
        )
        if filter:
            count_stmt = count_stmt.where(
                (col(DataEntry.data["display_name"]).ilike(filter_pattern))
            )
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        items = list(result.scalars().all())
        count = len(items)
        response = SubmoduleResponse(
            id=data_entry_type_id,
            name=str(data_entry_type_id),
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

    async def get_by_id(self, id: int) -> Optional[DataEntry]:
        """Get headcount record by ID."""
        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    # async def get_by_workspace(self, unit_id: int, date: str) -> Optional[DataEntry]:
    #     """Get headcount record by unit_id and date."""
    #     statement = select(DataEntry).where(
    #         DataEntry.unit_id == unit_id,
    #         DataEntry.date == date,
    #     )
    #     result = await self.session.execute(statement)
    #     return result.scalar_one_or_none()
