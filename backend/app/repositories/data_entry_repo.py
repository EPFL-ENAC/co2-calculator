"""Data entry repository for database operations."""

from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import Select, asc, desc, func, or_
from sqlalchemy import select as sa_select
from sqlalchemy.orm import aliased
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.location import Location
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report_response import SubmoduleResponse, SubmoduleSummary
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryUpdate,
    ModuleHandler,
)
from app.utils.headcount_role_category import get_function_role

logger = get_logger(__name__)

# Default filter map when handler doesn't provide one
DEFAULT_FILTER_MAP = {"name": DataEntry.data["name"].as_string()}


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
        await self.session.flush()
        return db_obj

    async def bulk_create(self, data_entries: list[DataEntry]) -> list[DataEntry]:
        """Bulk create data entries."""
        db_objs = [DataEntry.model_validate(entry) for entry in data_entries]
        self.session.add_all(db_objs)
        await self.session.flush()
        return db_objs

    async def bulk_delete(
        self, carbon_report_module_id: int, data_entry_type_id: DataEntryTypeEnum
    ) -> None:
        """Bulk delete data entries by module and type."""
        statement = delete(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            col(DataEntry.data_entry_type_id) == data_entry_type_id,
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def update(
        self, id: int, data: DataEntryUpdate, user_id: int
    ) -> Optional[DataEntry]:
        # POTENTIAL OPTIMIZATION: Use SQLAlchemy's update() for direct updates
        # 1. Fetch the existing record

        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.exec(statement)
        db_obj = result.one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "data" and value is not None:
                # Merge dicts instead of replacing
                db_obj.data = {**db_obj.data, **value}
            else:
                setattr(db_obj, field, value)

        # 4. Save
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def delete(self, id: int) -> bool:
        statement = delete(DataEntry).where(col(DataEntry.id) == id)
        result = await self.session.execute(statement)

        # rowcount tells you if a row actually matched the ID
        deleted = result.rowcount if hasattr(result, "rowcount") else None

        await self.session.flush()
        return bool(deleted)

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

        all_type_ids = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(
            ModuleTypeEnum(module_type_id), []
        )

        # Get actual counts from DB
        query: Select = (
            select(
                DataEntry.data_entry_type_id,
                func.count().label("total_count"),
            )
            .where(DataEntry.carbon_report_module_id == carbon_report_module_id)
            .group_by(col(DataEntry.data_entry_type_id))
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

    def _apply_name_filter(
        self, statement, filter: Optional[str], handler: ModuleHandler
    ):
        """
        Applies a filter to the given SQLAlchemy statement based on
        the handler's filter_map if a valid filter is provided.
        """
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
            # Get filter map from handler, default to filtering by name
            filter_map = getattr(handler, "filter_map", {}) or DEFAULT_FILTER_MAP

            # Build OR conditions for all filter fields
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            statement = statement.where(or_(*conditions))
        return statement, filter_pattern

    def _apply_sort(self, statement, sort_by: str, sort_order: str, sort_map: dict):
        sort_expr = sort_map.get(sort_by)
        if sort_expr is None:
            raise ValueError(f"Cannot sort by unknown field: {sort_by}")
        if sort_order.lower() == "asc":
            return statement.order_by(asc(sort_expr))
        else:
            return statement.order_by(desc(sort_expr))

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
        is_trips = data_entry_type_id == DataEntryTypeEnum.trips.value

        # Build query based on entry type
        statement: Select[Any]
        if is_trips:
            OriginLocation = aliased(Location)
            DestLocation = aliased(Location)
            statement = (
                sa_select(
                    DataEntry, DataEntryEmission, Factor, OriginLocation, DestLocation
                )
                .join(
                    DataEntryEmission,
                    col(DataEntry.id) == col(DataEntryEmission.data_entry_id),
                    isouter=True,
                )
                .join(
                    Factor,
                    col(DataEntryEmission.primary_factor_id) == col(Factor.id),
                    isouter=True,
                )
                .join(
                    OriginLocation,
                    DataEntry.data["origin_location_id"].as_integer()
                    == OriginLocation.id,
                    isouter=True,
                )
                .join(
                    DestLocation,
                    DataEntry.data["destination_location_id"].as_integer()
                    == DestLocation.id,
                    isouter=True,
                )
                .where(
                    col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                    col(DataEntry.data_entry_type_id) == data_entry_type_id,
                )
            )
        else:
            statement = (
                sa_select(DataEntry, DataEntryEmission, Factor)
                .join(
                    DataEntryEmission,
                    col(DataEntry.id) == col(DataEntryEmission.data_entry_id),
                    isouter=True,
                )
                .join(
                    Factor,
                    col(DataEntryEmission.primary_factor_id) == col(Factor.id),
                    isouter=True,
                )
                .where(
                    col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                    col(DataEntry.data_entry_type_id) == data_entry_type_id,
                )
            )

        handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum(data_entry_type_id))
        statement, filter_pattern = self._apply_name_filter(statement, filter, handler)

        sort_map = handler.sort_map
        statement = self._apply_sort(statement, sort_by, sort_order, sort_map)

        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)

        # Query for total count (for pagination)
        count_stmt = select(func.count()).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == data_entry_type_id,
        )
        if filter_pattern != "":
            # Get filter map from handler, default to filtering by name
            filter_map = getattr(handler, "filter_map", {}) or DEFAULT_FILTER_MAP

            # Build OR conditions for all filter fields
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            count_stmt = count_stmt.where(or_(*conditions))
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        rows = result.all()
        count = len(rows)

        items: list[BaseModel] = []

        for row in rows:
            # Unpack based on query shape
            if is_trips:
                (
                    data_entry,
                    data_entry_emission,
                    primary_factor,
                    origin_loc,
                    dest_loc,
                ) = row
            else:
                data_entry, data_entry_emission, primary_factor = row
                origin_loc, dest_loc = None, None

            handler = BaseModuleHandler.get_by_type(
                DataEntryTypeEnum(data_entry.data_entry_type_id)
            )
            kg_co2eq = None
            emission_meta = {}
            if data_entry_emission is not None:
                kg_co2eq = data_entry_emission.kg_co2eq
                # Extract meta fields (e.g., distance_km for travel)
                if data_entry_emission.meta:
                    emission_meta = data_entry_emission.meta
            # If primary_factor is None, try to fetch it
            # from DataEntry.data["primary_factor_id"]
            if primary_factor is None:
                primary_factor_id = data_entry.data.get("primary_factor_id")
                if primary_factor_id:
                    factor_stmt = select(Factor).where(Factor.id == primary_factor_id)
                    factor_result = await self.session.execute(factor_stmt)
                    primary_factor = factor_result.scalar_one_or_none()

            data_entry.data = {
                **data_entry.data,
                **emission_meta,
                **({"origin": origin_loc.name} if origin_loc else {}),
                **({"destination": dest_loc.name} if dest_loc else {}),
                "kg_co2eq": kg_co2eq,
                "primary_factor": {
                    **primary_factor.values,
                    **primary_factor.classification,
                }
                if primary_factor
                else {},
            }

            items.append(handler.to_response(data_entry))

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

    async def get_total_per_field(
        self,
        field_name: str,
        carbon_report_module_id: int,
        data_entry_type_id: Optional[int] = None,
    ) -> float:
        """Get total sum for a specific field across data entries.

        :param field_name: The field to sum (e.g., 'fte', 'kg_co2eq').
        :param carbon_report_module_id: The carbon report module ID to filter by.
        :param data_entry_type_id: Optional data entry type ID to filter by.
        :return: The total sum as a float.
        """
        if hasattr(DataEntry, field_name):
            sum_field = getattr(DataEntry, field_name)
        else:
            sum_field = DataEntry.data[field_name].as_float()

        statement = select(func.sum(sum_field).label("total")).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id
        )
        if data_entry_type_id is not None:
            statement = statement.where(
                DataEntry.data_entry_type_id == data_entry_type_id
            )

        result = await self.session.execute(statement)
        total = result.scalar_one()
        return float(total or 0.0)

    async def get_stats(
        self,
        carbon_report_module_id,
        aggregate_by: str = "data_entry_type_id",
        aggregate_field: str = "fte",
    ) -> Dict[str, float]:
        """Aggregate DataEntry data by submodule or function.
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
        if hasattr(DataEntry, aggregate_by):
            group_field = getattr(DataEntry, aggregate_by)
        else:
            group_field = DataEntry.data[aggregate_by].as_string()
        if hasattr(DataEntry, aggregate_field):
            sum_field = getattr(DataEntry, aggregate_field)
        else:
            sum_field = DataEntry.data[aggregate_field].as_float()

        # 2. Build the query with the JOIN
        query = (
            select(
                group_field,
                func.sum(sum_field).label("total"),
            )
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
            # special edge case for headcount : TO BE FIX by PM
            if aggregate_by == "function":
                label = get_function_role(label)
            if label not in aggregation:
                aggregation[label] = 0.0
            aggregation[label] += float(total_count or 0.0)

        return aggregation
