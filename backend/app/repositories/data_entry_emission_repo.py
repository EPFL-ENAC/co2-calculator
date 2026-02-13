"""Data entry emission repository for database operations."""

from typing import Any, Dict, List

from sqlalchemy import Select
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum

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

    async def delete_by_data_entry_id(self, data_entry_id: int) -> None:
        query = select(DataEntryEmission).where(
            DataEntryEmission.data_entry_id == data_entry_id
        )
        result = await self.session.execute(query)
        obj = result.scalar_one_or_none()
        if obj:
            await self.session.delete(obj)
            await self.session.flush()

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

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
    ) -> Dict[str, float]:
        """Aggregate validated emission totals per module for a carbon report.

        Joins DataEntryEmission → DataEntry → CarbonReportModule and returns
        SUM(kg_co2eq) grouped by module_type_id, filtered to validated modules
        only.

        Returns:
            Dict keyed by module_type_id (as string), e.g.:
            {"2": 15000.0, "4": 41700.0, "7": 5000.0}
        """
        query = (
            select(
                col(CarbonReportModule.module_type_id),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                CarbonReportModule.carbon_report_id == carbon_report_id,
                CarbonReportModule.status == ModuleStatus.VALIDATED,
                col(DataEntryEmission.kg_co2eq).isnot(None),
            )
            .group_by(col(CarbonReportModule.module_type_id))
        )

        result = await self.session.execute(query)
        rows = result.all()

        aggregation: Dict[str, float] = {}
        for module_type_id, total in rows:
            label = str(module_type_id) if module_type_id is not None else "unknown"
            aggregation[label] = float(total or 0.0)

        return aggregation

    async def get_travel_stats_by_class(
        self,
        carbon_report_module_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate trip emissions by transport_mode and cabin_class.
        """
        # Define expressions once so SELECT and GROUP BY use the same objects
        category_expr = DataEntry.data["transport_mode"].as_string()
        class_expr = DataEntry.data["cabin_class"].as_string()

        query = (
            select(
                category_expr.label("category"),
                class_expr.label("class_key"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
                DataEntry.data_entry_type_id == DataEntryTypeEnum.trips.value,
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
            .group_by(category_expr, class_expr)
        )

        result = await self.session.execute(query)
        rows = result.all()

        # Group by category (transport_mode), aggregate by class
        data_dict: Dict[str, Dict[str, float]] = {}
        for row in rows:
            category = row.category or "unknown"
            class_key = row.class_key
            kg_co2eq = float(row.kg_co2eq or 0.0)

            if kg_co2eq <= 0:
                continue

            if category not in data_dict:
                data_dict[category] = {}

            # Default class when null
            if class_key is None:
                if category == "plane":
                    class_key = "eco"
                elif category == "train":
                    class_key = "class_2"
                else:
                    class_key = "unknown"

            data_dict[category][class_key] = (
                data_dict[category].get(class_key, 0.0) + kg_co2eq
            )

        # Build treemap format
        total_kg_co2eq = sum(sum(classes.values()) for classes in data_dict.values())

        result_list: List[Dict[str, Any]] = []
        for category, classes in data_dict.items():
            category_total = sum(classes.values())
            children = []
            for class_key, kg_co2eq in classes.items():
                percentage = (
                    (kg_co2eq / total_kg_co2eq * 100) if total_kg_co2eq > 0 else 0.0
                )
                children.append(
                    {
                        "name": class_key,
                        "value": kg_co2eq,
                        "percentage": percentage,
                    }
                )
            if children and category_total > 0:
                result_list.append(
                    {
                        "name": category,
                        "value": category_total,
                        "children": children,
                    }
                )

        return result_list

    async def get_travel_evolution_over_time(
        self,
        unit_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate trip emissions by year and transport_mode across all years
        for a given unit.

        Returns:
        [
            {"year": 2023, "transport_mode": "plane", "kg_co2eq": 15000.0},
            {"year": 2023, "transport_mode": "train", "kg_co2eq": 8000.0},
            ...
        ]
        """
        year_expr = col(CarbonReport.year)
        transport_mode_expr = DataEntry.data["transport_mode"].as_string()

        query: Select[Any] = (
            select(
                year_expr.label("year"),
                transport_mode_expr.label("transport_mode"),
                func.sum(col(DataEntryEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                DataEntry,
                col(DataEntryEmission.data_entry_id) == col(DataEntry.id),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonReportModule.module_type_id
                == ModuleTypeEnum.professional_travel.value,
                DataEntry.data_entry_type_id == DataEntryTypeEnum.trips.value,
                col(DataEntryEmission.kg_co2eq).isnot(None),
                col(DataEntryEmission.kg_co2eq) > 0,
            )
            .group_by(year_expr, transport_mode_expr)
            .order_by(year_expr.asc(), transport_mode_expr.asc())
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "year": int(row.year),
                "transport_mode": row.transport_mode or "unknown",
                "kg_co2eq": float(row.kg_co2eq or 0.0),
            }
            for row in rows
        ]
