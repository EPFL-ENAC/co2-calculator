"""CarbonReportModule repository for database operations."""

from math import ceil
from typing import Any, List, Optional

from sqlmodel import and_, case, col, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import User
from app.schemas.carbon_report import CarbonReportModuleCreate
from app.utils.emission_category import build_chart_breakdown

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
        carbon_report_modules_to_create: list[CarbonReportModuleCreate],
    ) -> List[CarbonReportModule]:
        """Create multiple carbon report module records in one transaction."""
        carbon_report_modules = [
            CarbonReportModule(**carbon_report_module.model_dump())
            for carbon_report_module in carbon_report_modules_to_create
        ]
        self.session.add_all(carbon_report_modules)
        await self.session.flush()
        for obj in carbon_report_modules:
            await self.session.refresh(obj)
        return carbon_report_modules

    async def bulk_create_carbon_report_modules_of_carbon_report(
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

    @staticmethod
    def _split_filter_values(
        values: Optional[List[str]],
    ) -> tuple[List[int], List[str]]:
        """Split mixed query values into integer IDs and string names."""
        ids: List[int] = []
        names: List[str] = []
        for raw in values or []:
            value = str(raw).strip()
            if not value:
                continue
            if value.isdigit():
                ids.append(int(value))
            else:
                names.append(value)
        return ids, names

    async def _get_selected_units(
        self, values: Optional[List[str]]
    ) -> List[tuple[int, Optional[str]]]:
        """Resolve selected units from mixed ID/name values to id/code tuples."""
        ids, names = self._split_filter_values(values)
        if not ids and not names:
            return []

        filters = []
        if ids:
            filters.append(col(Unit.id).in_(ids))
        if names:
            filters.append(col(Unit.name).in_(names))

        statement = select(Unit.id, Unit.institutional_code).where(or_(*filters))
        rows = (await self.session.exec(statement)).all()
        # Unit.id is expected to be present, but SQL typing can expose Optional.
        return [(unit_id, code) for unit_id, code in rows if unit_id is not None]

    async def _get_descendant_unit_ids(self, values: Optional[List[str]]) -> set[int]:
        """Resolve hierarchy nodes to descendant unit IDs, including self."""
        selected_units = await self._get_selected_units(values)
        if not selected_units:
            return set()

        selected_ids = {unit_id for unit_id, _ in selected_units}
        selected_codes = {code for _, code in selected_units if code}

        # No institutional codes — descendants can only be looked up by path,
        # so return the directly resolved IDs to avoid a full-table scan.
        if not selected_codes:
            return selected_ids

        path_conditions = []
        for code in selected_codes:
            # Token-boundary matching for ancestor code in path string.
            path_conditions.extend(
                [
                    col(Unit.path_institutional_code) == code,
                    col(Unit.path_institutional_code).like(f"{code} %"),
                    col(Unit.path_institutional_code).like(f"% {code}"),
                    col(Unit.path_institutional_code).like(f"% {code} %"),
                ]
            )

        descendants_stmt = select(Unit.id).where(or_(*path_conditions))
        descendant_ids = {
            unit_id
            for unit_id in (await self.session.exec(descendants_stmt)).all()
            if unit_id is not None
        }

        # Ensure selected units are included even if path is null or non-standard.
        return selected_ids.union(descendant_ids)

    async def _get_direct_unit_ids(self, values: Optional[List[str]]) -> set[int]:
        """Resolve direct unit filter values (ID/name) to unit IDs."""
        selected_units = await self._get_selected_units(values)
        return {unit_id for unit_id, _ in selected_units}

    async def _resolve_hierarchy_unit_ids(
        self,
        path_lvl2: Optional[List[str]] = None,
        path_lvl3: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
    ) -> Optional[set[int]]:
        """
        Build the effective unit ID filter with intersection semantics across levels.

        Returns:
            - None when no hierarchy filters were provided (no-op)
            - set of unit IDs when at least one hierarchy filter is provided
        """
        filter_sets: List[set[int]] = []

        if path_lvl2:
            filter_sets.append(await self._get_descendant_unit_ids(path_lvl2))
        if path_lvl3:
            filter_sets.append(await self._get_descendant_unit_ids(path_lvl3))
        if path_lvl4:
            filter_sets.append(await self._get_direct_unit_ids(path_lvl4))

        if not filter_sets:
            return None

        effective_ids = filter_sets[0]
        for ids in filter_sets[1:]:
            effective_ids = effective_ids.intersection(ids)
        return effective_ids

    @staticmethod
    def _apply_report_filters(
        stmt: Any,
        hierarchy_unit_ids: Optional[set[int]],
        completion_status: Optional["ModuleStatus"],
    ) -> Any:
        """Apply hierarchy and completion-status filters to a statement."""
        if hierarchy_unit_ids is not None:
            stmt = stmt.where(col(Unit.id).in_(hierarchy_unit_ids))
        if completion_status is not None:
            stmt = stmt.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )
        return stmt

    @staticmethod
    def _get_completion_status_from_progress(
        completion_progress: Optional[str],
    ) -> ModuleStatus:
        """Map completion progress string (e.g. '5/7') to ModuleStatus."""
        if not completion_progress:
            return ModuleStatus.NOT_STARTED

        completed_raw, _, total_raw = completion_progress.partition("/")
        if not completed_raw.isdigit() or not total_raw.isdigit():
            return ModuleStatus.NOT_STARTED

        completed = int(completed_raw)
        total = int(total_raw)
        if total <= 0 or completed <= 0:
            return ModuleStatus.NOT_STARTED
        if completed >= total:
            return ModuleStatus.VALIDATED
        return ModuleStatus.IN_PROGRESS

    async def get_reporting_overview(
        self,
        path_lvl2: Optional[List[str]] = None,
        path_lvl3: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
        completion_status: Optional[ModuleStatus] = None,
        search: Optional[str] = None,
        modules: Optional[List[str]] = None,  # complex TBD
        years: Optional[List[int]] = None,  # Default to first year for overview for now
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        Retrieves the aggregated reporting data using a Deferred Join strategy.
        First paginates the Units, then calculates footprints ONLY for those 50 units.
        """
        if years is None:
            raise ValueError(
                "At least one year must be specified for the reporting overview."
            )

        hierarchy_unit_ids = await self._resolve_hierarchy_unit_ids(
            path_lvl2=path_lvl2,
            path_lvl3=path_lvl3,
            path_lvl4=path_lvl4,
        )

        # If filters were provided but resolve to no units, short-circuit early.
        if hierarchy_unit_ids is not None and len(hierarchy_unit_ids) == 0:
            return {
                "data": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "validated_units_count": 0,
                "in_progress_units_count": 0,
                "not_started_units_count": 0,
                "total_units_count": 0,
            }

        # --- STEP 1: The Cheap Count ---
        # Count units per status in a single GROUP BY query.
        status_count_stmt = (
            select(
                col(CarbonReport.overall_status),
                func.count(col(Unit.id)),
            )
            .join(CarbonReport, col(CarbonReport.unit_id) == Unit.id)
            .where(col(CarbonReport.year).in_(years))
            .group_by(col(CarbonReport.overall_status))
        )
        if hierarchy_unit_ids is not None:
            status_count_stmt = status_count_stmt.where(
                col(Unit.id).in_(hierarchy_unit_ids)
            )

        status_count_rows = (await self.session.exec(status_count_stmt)).all()
        status_counts = {int(status): count for status, count in status_count_rows}
        total_units_count = sum(status_counts.values())
        validated_units_count = status_counts.get(int(ModuleStatus.VALIDATED), 0)
        in_progress_units_count = status_counts.get(int(ModuleStatus.IN_PROGRESS), 0)
        not_started_units_count = status_counts.get(int(ModuleStatus.NOT_STARTED), 0)

        # Base count stmt still needed for the filtered table count below.
        base_count_stmt = (
            select(func.count(col(Unit.id)))
            .join(CarbonReport, col(CarbonReport.unit_id) == Unit.id)
            .where(col(CarbonReport.year).in_(years))
        )
        if hierarchy_unit_ids is not None:
            base_count_stmt = base_count_stmt.where(
                col(Unit.id).in_(hierarchy_unit_ids)
            )

        # Filtered count (adds optional completion_status filter for the table).
        count_statement = base_count_stmt
        if completion_status is not None:
            count_statement = count_statement.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )

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
            col(Unit.path_name).label("path_name"),
            col(User.display_name).label("principal_user_name"),
            col(CarbonReport.id).label("carbon_report_id"),
            col(CarbonReport.completion_progress).label("completion_progress"),
        ]

        # 2. Unpack them into the select statement
        units_stmt = (
            select(*units_stmt_columns)
            .join(CarbonReport, CarbonReport.unit_id == Unit.id)
            .outerjoin(
                User, User.institutional_id == Unit.principal_user_institutional_id
            )
            .where(col(CarbonReport.year).in_(years))
        )
        units_stmt = self._apply_report_filters(
            units_stmt, hierarchy_unit_ids, completion_status
        )

        filtered_report_ids_stmt = self._apply_report_filters(
            select(col(CarbonReport.id))
            .join(Unit, col(CarbonReport.unit_id) == col(Unit.id))
            .where(col(CarbonReport.year).in_(years)),
            hierarchy_unit_ids,
            completion_status,
        )

        # Use a subquery instead of materializing the full list of report IDs
        # to avoid large IN (...) parameter lists for big datasets.
        filtered_report_ids_subq = filtered_report_ids_stmt.subquery()
        filtered_report_ids_in = select(filtered_report_ids_subq.c.id)

        # if unit_ids:
        #     units_stmt = units_stmt.where(col(Unit.id).in_(unit_ids))

        # Apply limits here!
        units_stmt = (
            units_stmt.order_by(col(Unit.name))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        paginated_units = (await self.session.exec(units_stmt)).all()
        page_report_ids = [u.carbon_report_id for u in paginated_units]

        # Build an aggregated emission breakdown from module stats by_emission_type
        # so frontend can reuse result-page charts with reporting filters.
        module_stats_stmt = select(
            CarbonReportModule.module_type_id,
            CarbonReportModule.status,
            CarbonReportModule.stats,
        ).where(col(CarbonReportModule.carbon_report_id).in_(filtered_report_ids_in))
        raw_module_stats_rows = (await self.session.exec(module_stats_stmt)).all()
        module_stats_rows: list[tuple[int, int, Optional[dict[str, Any]]]] = [
            (
                int(module_type_id),
                int(status),
                stats if isinstance(stats, dict) else None,
            )
            for module_type_id, status, stats in raw_module_stats_rows
        ]

        global_fte_stmt = (
            select(func.sum(func.coalesce(DataEntry.data["fte"].as_float(), 0.0)))
            .join(
                CarbonReportModule,
                col(CarbonReportModule.id) == col(DataEntry.carbon_report_module_id),
            )
            .where(
                col(CarbonReportModule.carbon_report_id).in_(filtered_report_ids_in),
                col(CarbonReportModule.module_type_id) == ModuleTypeEnum.headcount,
            )
        )
        global_fte_result = (await self.session.exec(global_fte_stmt)).one()
        global_fte = float(global_fte_result or 0.0)

        chart_rows: list[tuple[int, int, float]] = []
        validated_module_type_ids: set[int] = set()
        headcount_validated = False

        for module_type_id, status, stats in module_stats_rows:
            if status == ModuleStatus.VALIDATED:
                validated_module_type_ids.add(int(module_type_id))
                if int(module_type_id) == int(ModuleTypeEnum.headcount):
                    headcount_validated = True

            if not isinstance(stats, dict):
                continue

            by_emission_type = stats.get("by_emission_type", {})
            if not isinstance(by_emission_type, dict):
                continue

            for emission_type_id_raw, kg_value in by_emission_type.items():
                try:
                    emission_type_id = int(emission_type_id_raw)
                except (TypeError, ValueError):
                    continue

                if not isinstance(kg_value, (int, float)):
                    continue

                chart_rows.append(
                    (int(module_type_id), emission_type_id, float(kg_value))
                )

        emission_breakdown = build_chart_breakdown(
            rows=chart_rows,
            total_fte=global_fte,
            headcount_validated=headcount_validated,
            validated_module_type_ids=validated_module_type_ids,
        )

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
            aff = u.path_name if u.path_name and len(u.path_name) > 0 else "N/A"

            # Get the aggregations for this specific unit's report,
            # or default empty values
            aggs = agg_map.get(u.carbon_report_id)

            completion_progress = u.completion_progress or "0/7"
            completion_status_value = self._get_completion_status_from_progress(
                completion_progress
            )
            reporting_data.append(
                {
                    "id": u.unit_id,
                    "unit_name": u.unit_name,
                    "affiliation": aff,
                    "validation_status": completion_progress,
                    "principal_user": u.principal_user_name or "Unknown",
                    "last_update": aggs.last_update if aggs else None,
                    "highest_result_category": self._map_module_id_to_name(
                        aggs.highest_cat_id if aggs else None
                    ),
                    "total_carbon_footprint": round(float(aggs.total_footprint or 0), 2)
                    if aggs
                    else 0.0,
                    "view_url": f"/backoffice/unit/{u.unit_id}",
                    "completion": completion_status_value,
                    "completion_progress": completion_progress,
                }
            )

        # --- Single-unit case: per-module status breakdown ---
        module_status_counts = None
        if total == 1 and paginated_units:
            single_report_id = paginated_units[0].carbon_report_id
            if single_report_id is not None:
                module_status_stmt = (
                    select(
                        col(CarbonReportModule.status),
                        func.count(col(CarbonReportModule.id)),
                    )
                    .where(col(CarbonReportModule.carbon_report_id) == single_report_id)
                    .group_by(col(CarbonReportModule.status))
                )
                module_status_rows = (await self.session.exec(module_status_stmt)).all()
                module_status_counts = {
                    int(status): count for status, count in module_status_rows
                }

        return {
            "data": reporting_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size),
            "emission_breakdown": emission_breakdown,
            "validated_units_count": validated_units_count,
            "in_progress_units_count": in_progress_units_count,
            "not_started_units_count": not_started_units_count,
            "total_units_count": total_units_count,
            "module_status_counts": module_status_counts,
        }

    async def get_usage_report(
        self,
        path_lvl2: Optional[List[str]] = None,
        path_lvl3: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
        completion_status: Optional[ModuleStatus] = None,
        search: Optional[str] = None,
        modules: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
    ) -> list[dict]:
        """
        Get a report of all carbon reports and their modules with status and
        last updated timestamp.

        Args:
            path_lvl2: Optional list of hierarchy level 2 filters (unit names or IDs)
            path_lvl3: Optional list of hierarchy level 3 filters (unit names or IDs)
            path_lvl4: Optional list of hierarchy level 4 filters (unit names or IDs)
            completion_status: Optional filter for report-level completion status.
            search: Optional search term to filter results.
            modules: Optional filter for specific module types and statuses
              (e.g., ["energy:2", "transport:1"])
            years: Optional filter for specific years (e.g., [2024, 2025])
        Returns:
            A list of dictionaries containing year, unit_id, module_name,
              module_status, and last_updated.
        """
        hierarchy_unit_ids = await self._resolve_hierarchy_unit_ids(
            path_lvl2=path_lvl2,
            path_lvl3=path_lvl3,
            path_lvl4=path_lvl4,
        )
        # If hierarchy filters were provided but matched no units, return no results.
        if hierarchy_unit_ids is not None and not hierarchy_unit_ids:
            return []

        report: list[dict] = []

        columns: List[Any] = [
            col(CarbonReport.year),
            col(CarbonReport.unit_id),
            col(CarbonReportModule.module_type_id),
            col(CarbonReportModule.status),
            col(CarbonReportModule.last_updated),
        ]
        statement = (
            select(*columns)
            .join(
                CarbonReportModule,
                CarbonReportModule.carbon_report_id == CarbonReport.id,
            )
            .order_by(CarbonReport.id, CarbonReportModule.module_type_id)
        )
        if years:
            statement = statement.where(col(CarbonReport.year).in_(years))
        if completion_status:
            statement = statement.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )
        if search:
            search_term = f"%{search.strip().lower()}%"
            statement = statement.join(Unit, Unit.id == CarbonReport.unit_id).where(
                or_(
                    func.lower(Unit.name).like(search_term),
                    func.lower(Unit.institutional_code).like(search_term),
                )
            )
        if modules:
            # Filter by module types and statuses
            for mod in modules:
                if ":" in mod:
                    module_type_name, status_str = mod.split(":", 1)
                    if module_type_name not in ModuleTypeEnum.__members__:
                        raise ValueError(
                            f"Invalid module type in modules filter: {module_type_name}"
                        )
                    try:
                        status_int = int(status_str)
                    except ValueError as exc:
                        raise ValueError(
                            f"Invalid status in modules filter (must be integer): "
                            f"{status_str}"
                        ) from exc
                    module_type = ModuleTypeEnum[module_type_name].value
                    statement = statement.where(
                        (col(CarbonReportModule.module_type_id) == module_type)
                        & (col(CarbonReportModule.status) == status_int)
                    )
                else:
                    module_type_name = mod
                    if module_type_name not in ModuleTypeEnum.__members__:
                        raise ValueError(
                            f"Invalid module type in modules filter: {module_type_name}"
                        )
                    module_type = ModuleTypeEnum[module_type_name].value

        if hierarchy_unit_ids is not None:
            statement = statement.where(
                col(CarbonReport.unit_id).in_(hierarchy_unit_ids)
            )
        cursor = await self.session.stream(statement)
        async for partition in cursor.partitions(500):
            for row in partition:
                report.append(
                    {
                        "year": row.year,
                        "unit_id": row.unit_id,
                        "module_name": ModuleTypeEnum(row.module_type_id).name,
                        "module_status": row.status,
                        "last_updated": row.last_updated,
                    }
                )

        return report

    def _map_module_id_to_name(self, module_type_id: Optional[int]) -> str:
        """Helper to map internal IDs to the display names used in UI."""
        if not module_type_id:
            return "—"
        # Map based on your ModuleTypeEnum/metadata
        return f"{ModuleTypeEnum(module_type_id).name}"
