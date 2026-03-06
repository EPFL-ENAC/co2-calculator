"""CarbonReportModule repository for database operations."""

from math import ceil
from typing import Any, List, Optional

from sqlmodel import and_, case, col, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule, ModuleStatus
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import User

logger = get_logger(__name__)


class CarbonReportModuleRepository:
    """Repository for CarbonReportModule database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        carbon_report_id: int,
        module_type_id: int,
        status: int = ModuleStatus.NOT_STARTED,
    ) -> CarbonReportModule:
        """Create a new carbon report module record."""
        db_obj = CarbonReportModule(
            carbon_report_id=carbon_report_id,
            module_type_id=module_type_id,
            status=status,
        )
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def bulk_create(
        self,
        carbon_report_id: int,
        module_type_ids: List[int],
        status: int = ModuleStatus.NOT_STARTED,
    ) -> List[CarbonReportModule]:
        """Create multiple carbon report module records in one transaction."""
        db_objects = [
            CarbonReportModule(
                carbon_report_id=carbon_report_id,
                module_type_id=module_type_id,
                status=status,
            )
            for module_type_id in module_type_ids
        ]
        self.session.add_all(db_objects)
        await self.session.flush()
        for obj in db_objects:
            await self.session.refresh(obj)
        return db_objects

    async def get_by_year_and_unit(
        self, year: int, unit_id: int, module_type_id: ModuleTypeEnum
    ) -> Optional[CarbonReportModule]:
        statement = (
            select(CarbonReportModule)
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReport.year == year,
                CarbonReport.unit_id == unit_id,
                CarbonReportModule.module_type_id == module_type_id,
            )
        )
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def get(self, id: int) -> Optional[CarbonReportModule]:
        """Get a carbon report module by ID."""
        statement = select(CarbonReportModule).where(CarbonReportModule.id == id)
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def get_module_type(self, carbon_report_module_id: int) -> Optional[int]:
        """Get the module type ID for a given carbon report module ID."""
        statement = select(CarbonReportModule.module_type_id).where(
            CarbonReportModule.id == carbon_report_module_id
        )
        result = await self.session.exec(statement)
        row = result.one_or_none()
        if row is not None:
            return row
        return None

    async def get_by_report_and_module_type(
        self, carbon_report_id: int, module_type_id: int
    ) -> Optional[CarbonReportModule]:
        """Get a carbon report module by report ID and module type ID."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id,
            CarbonReportModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_report(self, carbon_report_id: int) -> List[CarbonReportModule]:
        """List all modules for a given carbon report."""
        statement = (
            select(CarbonReportModule)
            .where(CarbonReportModule.carbon_report_id == carbon_report_id)
            .order_by("module_type_id")
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self, carbon_report_id: int, module_type_id: int, status: int
    ) -> Optional[CarbonReportModule]:
        """Update the status of a carbon report module."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id,
            CarbonReportModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        db_obj.status = status
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, carbon_report_module_id: int) -> bool:
        """Delete a carbon report module by ID."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.id == carbon_report_module_id
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.flush()
        return True

    async def update_stats(self, carbon_report_module_id: int, stats: dict) -> None:
        """Persist pre-computed stats JSON on a carbon report module."""
        module = await self.get(carbon_report_module_id)
        if module is None:
            logger.warning(
                f"Cannot update stats: module {carbon_report_module_id} not found"
            )
            return
        module.stats = stats
        self.session.add(module)
        await self.session.flush()

    async def delete_by_report(self, carbon_report_id: int) -> int:
        """Delete all modules for a given carbon report. Returns count deleted."""
        statement = select(CarbonReportModule).where(
            CarbonReportModule.carbon_report_id == carbon_report_id
        )
        result = await self.session.execute(statement)
        db_objects = list(result.scalars().all())
        count = len(db_objects)
        for obj in db_objects:
            await self.session.delete(obj)
        await self.session.flush()
        return count

    async def get_reporting_overview(
        self,
        years: list[int],
        unit_ids: Optional[List[int]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        Retrieves the aggregated reporting data using a Deferred Join strategy.
        First paginates the Units, then calculates footprints ONLY for those 50 units.
        """

        # --- STEP 1: The Cheap Count ---
        count_statement = (
            select(func.count(col(Unit.id)))
            .join(CarbonReport, col(CarbonReport.unit_id) == Unit.id)
            .where(col(CarbonReport.year).in_(years))
        )
        if unit_ids:
            count_statement = count_statement.where(col(Unit.id).in_(unit_ids))

        total = (await self.session.exec(count_statement)).one()

        # Short-circuit if no results
        if total == 0:
            return {
                "data": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
            }

        # --- STEP 2: Paginate just the basic Unit/Report info ---
        # 1. Group columns into a list to bypass the 4-arg overload limit
        units_stmt_columns: List[Any] = [
            col(Unit.id).label("unit_id"),
            col(Unit.name).label("unit_name"),
            col(Unit.path_name).label("affiliations"),
            col(User.display_name).label("principal_user_name"),
            col(CarbonReport.id).label("carbon_report_id"),
        ]

        # 2. Unpack them into the select statement
        units_stmt = (
            select(*units_stmt_columns)
            .join(CarbonReport, CarbonReport.unit_id == Unit.id)
            .outerjoin(User, User.provider_code == Unit.principal_user_institutional_id)
            .where(col(CarbonReport.year).in_(years))
        )

        if unit_ids:
            units_stmt = units_stmt.where(col(Unit.id).in_(unit_ids))

        # Apply limits here!
        units_stmt = (
            units_stmt.order_by(col(Unit.name))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        paginated_units = (await self.session.exec(units_stmt)).all()
        page_report_ids = [u.carbon_report_id for u in paginated_units]

        # --- STEP 3: The Heavy Math (Restricted to max 50 reports) ---
        # We no longer need to join CarbonReport here,
        # because we already have the specific IDs
        # 1. Define the columns in a list to bypass overload limits
        module_totals_cte_columns: List[Any] = [
            col(CarbonReportModule.id).label("module_id"),
            CarbonReportModule.carbon_report_id,
            CarbonReportModule.module_type_id,
            CarbonReportModule.status,
            func.max(DataEntry.updated_at).label("updated_at"),
            func.sum(func.coalesce(DataEntryEmission.kg_co2eq, 0) / 1000.0).label(
                "tco2_total"
            ),
        ]

        # 2. Build the query using unpacking (*)
        module_totals_cte = (
            select(*module_totals_cte_columns)
            .join(
                DataEntry,
                DataEntry.carbon_report_module_id == CarbonReportModule.id,
                isouter=True,
            )
            .join(
                DataEntryEmission,
                DataEntryEmission.data_entry_id == DataEntry.id,
                isouter=True,
            )
            .where(col(CarbonReportModule.carbon_report_id).in_(page_report_ids))
            # Combine into a single group_by
            .group_by(
                CarbonReportModule.id,
                CarbonReportModule.carbon_report_id,
                CarbonReportModule.module_type_id,
                CarbonReportModule.status,
            )
            .cte("module_totals")
        )

        highest_rank_sub = (
            select(
                module_totals_cte.c.carbon_report_id,
                module_totals_cte.c.module_type_id,
                func.row_number()
                .over(
                    partition_by=module_totals_cte.c.carbon_report_id,
                    order_by=desc(module_totals_cte.c.tco2_total),
                )
                .label("rn"),
            )
            .where(module_totals_cte.c.status == ModuleStatus.VALIDATED)
            .subquery()
        )

        # 1. Group your columns into a list
        columns = [
            module_totals_cte.c.carbon_report_id,
            func.count(
                case((module_totals_cte.c.status == ModuleStatus.VALIDATED, 1))
            ).label("val_count"),
            func.count(module_totals_cte.c.module_id).label("total_count"),
            func.max(module_totals_cte.c.updated_at).label("last_update"),
            func.sum(module_totals_cte.c.tco2_total).label("total_footprint"),
            highest_rank_sub.c.module_type_id.label("highest_cat_id"),
        ]

        # 2. Unpack them into select()
        agg_stmt = (
            select(*columns)
            .outerjoin(
                highest_rank_sub,
                and_(
                    highest_rank_sub.c.carbon_report_id
                    == module_totals_cte.c.carbon_report_id,
                    highest_rank_sub.c.rn == 1,
                ),
            )
            .group_by(
                module_totals_cte.c.carbon_report_id,
                highest_rank_sub.c.module_type_id,
            )
        )

        agg_results = (await self.session.exec(agg_stmt)).all()

        # --- STEP 4: Merge in Python ---
        # Create a dictionary mapping report_id to its aggregations for O(1) lookup
        agg_map = {row.carbon_report_id: row for row in agg_results}

        reporting_data = []
        for u in paginated_units:
            aff = (
                u.affiliations[0]
                if u.affiliations and len(u.affiliations) > 0
                else "N/A"
            )

            # Get the aggregations for this specific unit's report,
            # or default empty values
            aggs = agg_map.get(u.carbon_report_id)

            agg_value = (
                f"{aggs.val_count if aggs else 0}/{aggs.total_count if aggs else 0}"
            )
            reporting_data.append(
                {
                    "id": u.unit_id,
                    "unit_name": u.unit_name,
                    "affiliation": aff,
                    "validation_status": agg_value,
                    "principal_user": u.principal_user_name or "Unknown",
                    "last_update": aggs.last_update if aggs else None,
                    "highest_result_category": self._map_module_id_to_name(
                        aggs.highest_cat_id if aggs else None
                    ),
                    "total_carbon_footprint": round(float(aggs.total_footprint or 0), 2)
                    if aggs
                    else 0.0,
                    "view_url": f"/backoffice/unit/{u.unit_id}",
                }
            )

        return {
            "data": reporting_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size),
        }

    def _map_module_id_to_name(self, module_type_id: Optional[int]) -> str:
        """Helper to map internal IDs to the display names used in UI."""
        if not module_type_id:
            return "—"
        # Map based on your ModuleTypeEnum/metadata
        mapping = {1: "Headcount", 4: "Equipment", 7: "Travel"}  # Example IDs
        return mapping.get(
            module_type_id, f"Module {ModuleTypeEnum(module_type_id).name}"
        )
