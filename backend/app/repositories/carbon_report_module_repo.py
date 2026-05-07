"""CarbonReportModule repository for database operations."""

from datetime import datetime, timezone
from math import ceil
from typing import Any, List, Optional

from sqlalchemy import Integer, case, cast
from sqlmodel import col, delete, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import DEFAULT_COMPLETION_PROGRESS, ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
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
        self,
        year: int,
        unit_id: int,
        module_type_id: ModuleTypeEnum,
        *,
        report_type: CarbonReportType = CarbonReportType.CALCULATOR,
    ) -> Optional[CarbonReportModule]:
        statement = (
            select(CarbonReportModule)
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                col(CarbonProject.carbon_report_type) == report_type,
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

    async def list_by_module_type_and_year(
        self, module_type_id: int, year: int
    ) -> List[CarbonReportModule]:
        """List all modules for a given (module_type_id, year) slice.

        ``module_type_id`` lives on ``CarbonReportModule``; ``year`` lives on
        the parent ``CarbonReport``, so the filter joins through it.  Mirrors
        ``get_by_year_and_unit`` minus the unit filter.
        """
        statement = (
            select(CarbonReportModule)
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                CarbonReportModule.module_type_id == module_type_id,
                CarbonReport.year == year,
            )
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
        id_result = await self.session.execute(
            select(CarbonReportModule.id).where(
                CarbonReportModule.carbon_report_id == carbon_report_id
            )
        )
        module_ids = [row[0] for row in id_result.all()]
        if not module_ids:
            return 0

        # Delete data_entries first (no DB-level cascade on this FK).
        await self.session.execute(
            delete(DataEntry).where(
                col(DataEntry.carbon_report_module_id).in_(module_ids)
            )
        )

        await self.session.execute(
            delete(CarbonReportModule).where(col(CarbonReportModule.id).in_(module_ids))
        )
        await self.session.flush()
        return len(module_ids)

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
        path_affiliation: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
    ) -> Optional[set[int]]:
        """
        Build the effective unit ID filter with OR semantics.

        - Affiliation filter: Gets all descendants (Lvl2+3)
        - Units filter: Gets direct units (Lvl4)
        - Result: Union of both sets (OR logic)

        Returns:
            - None when no hierarchy filters provided
            - set of unit IDs (possibly empty) when at least one
              filter was provided
        """
        all_ids: set[int] = set()
        any_filter = False

        if path_affiliation is not None:
            any_filter = True
            all_ids.update(await self._get_descendant_unit_ids(path_affiliation))
        if path_lvl4 is not None:
            any_filter = True
            all_ids.update(await self._get_direct_unit_ids(path_lvl4))

        if not any_filter:
            return None

        return all_ids

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
        path_affiliation: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
        completion_status: Optional[ModuleStatus] = None,
        search: Optional[str] = None,
        modules: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
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
            path_affiliation=path_affiliation,
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

        is_multi_year = len(years) > 1

        # --- STEP 2: Paginate just the basic Unit/Report info ---
        if is_multi_year:
            # Multi-year: aggregate across years — one row per unit.
            # validated_years_count = number of selected years with VALIDATED status.
            validated_years_col = func.sum(
                case(
                    (
                        col(CarbonReport.overall_status) == int(ModuleStatus.VALIDATED),
                        1,
                    ),
                    else_=0,
                )
            ).label("validated_years_count")

            # Correlated subquery: stats from the most recent selected year.
            latest_stats_subq = (
                select(CarbonReport.stats)
                .where(CarbonReport.unit_id == Unit.id)
                .where(col(CarbonReport.year).in_(years))
                .order_by(desc(CarbonReport.year))
                .limit(1)
                .correlate(Unit)
                .scalar_subquery()
            )

            units_stmt_columns: List[Any] = [
                col(Unit.id).label("unit_id"),
                col(Unit.name).label("unit_name"),
                col(Unit.path_name).label("path_name"),
                col(User.display_name).label("principal_user_name"),
                func.max(col(CarbonReport.id)).label("carbon_report_id"),
                validated_years_col,
                func.max(col(CarbonReport.last_updated)).label("last_updated"),
                latest_stats_subq.label("report_stats"),
            ]

            units_stmt = (
                select(*units_stmt_columns)
                .join(CarbonReport, CarbonReport.unit_id == Unit.id)
                .outerjoin(
                    User,
                    User.institutional_id == Unit.principal_user_institutional_id,
                )
                .where(col(CarbonReport.year).in_(years))
                .group_by(Unit.id, Unit.name, Unit.path_name, User.display_name)
            )
        else:
            # Single year: one row per unit, module-level completion progress.
            units_stmt_columns = [
                col(Unit.id).label("unit_id"),
                col(Unit.name).label("unit_name"),
                col(Unit.path_name).label("path_name"),
                col(User.display_name).label("principal_user_name"),
                col(CarbonReport.id).label("carbon_report_id"),
                col(CarbonReport.completion_progress).label("completion_progress"),
                col(CarbonReport.last_updated).label("last_updated"),
                col(CarbonReport.stats).label("report_stats"),
            ]

            units_stmt = (
                select(*units_stmt_columns)
                .join(CarbonReport, CarbonReport.unit_id == Unit.id)
                .outerjoin(
                    User,
                    User.institutional_id == Unit.principal_user_institutional_id,
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

        # Build order by clause
        order_col: Any = Unit.name
        use_case_for_nulls = False
        null_value_for_sort = 0

        if sort_by == "unit_name":
            order_col = Unit.name
        elif sort_by == "affiliation":
            order_col = Unit.path_name
        elif sort_by == "validation_status":
            if is_multi_year:
                order_col = func.sum(
                    case(
                        (
                            col(CarbonReport.overall_status)
                            == int(ModuleStatus.VALIDATED),
                            1,
                        ),
                        else_=0,
                    )
                )
            else:
                completed_part = func.split_part(
                    CarbonReport.completion_progress, "/", 1
                )
                order_col = cast(completed_part, Integer)
            use_case_for_nulls = True
            null_value_for_sort = 0
        elif sort_by == "principal_user":
            order_col = User.display_name
        elif sort_by == "last_update":
            order_col = CarbonReport.last_updated
            use_case_for_nulls = True
            null_value_for_sort = 0
        elif sort_by == "total_carbon_footprint":
            # Extract 'total' from JSON stats, treat NULL/missing as 0
            order_col = col(CarbonReport.stats)["total"].as_float()
            use_case_for_nulls = True
            null_value_for_sort = 0
        elif sort_by == "highest_result_category":
            # Sort by module_id from stats JSON
            order_col = col(CarbonReport.stats)[
                "highest_category_module_id"
            ].as_integer()
            use_case_for_nulls = True
            null_value_for_sort = 0

        # Apply sort order with NULL handling
        if use_case_for_nulls:
            order_col_for_sort = case(
                (order_col.is_(None), null_value_for_sort), else_=order_col
            )
            if sort_order == "desc":
                units_stmt = units_stmt.order_by(desc(order_col_for_sort))
            else:
                units_stmt = units_stmt.order_by(order_col_for_sort)
        else:
            if sort_order == "desc":
                units_stmt = units_stmt.order_by(desc(order_col))
            else:
                units_stmt = units_stmt.order_by(order_col)

        # Apply pagination - if page_size is 0, no limit (show all)
        if page_size > 0:
            units_stmt = units_stmt.limit(page_size).offset((page - 1) * page_size)

        paginated_units = (await self.session.exec(units_stmt)).all()

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

        chart_rows: list[tuple[int, int, float, float | None]] = []
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
            by_additional_value = stats.get("by_additional_value", {})
            if not isinstance(by_additional_value, dict):
                by_additional_value = {}

            for emission_type_id_raw, kg_value in by_emission_type.items():
                try:
                    emission_type_id = int(emission_type_id_raw)
                except (TypeError, ValueError):
                    continue

                if not isinstance(kg_value, (int, float)):
                    continue

                add_raw = by_additional_value.get(emission_type_id_raw)
                add_value = (
                    float(add_raw) if isinstance(add_raw, (int, float)) else None
                )
                chart_rows.append(
                    (int(module_type_id), emission_type_id, float(kg_value), add_value)
                )

        emission_breakdown = build_chart_breakdown(
            rows=chart_rows,
            total_fte=global_fte,
            headcount_validated=headcount_validated,
            validated_module_type_ids=validated_module_type_ids,
        )

        # --- STEP 3: Use cached stats from CarbonReport ---
        # Build reporting data using pre-computed stats
        reporting_data = []
        for u in paginated_units:
            aff = u.path_name if u.path_name and len(u.path_name) > 0 else "N/A"

            report_stats = u.report_stats if isinstance(u.report_stats, dict) else {}
            total_footprint_kg = report_stats.get("total", 0) or 0
            total_footprint_tonnes = total_footprint_kg / 1000.0
            highest_category_module_id = report_stats.get("highest_category_module_id")

            last_update_dt = None
            if u.last_updated is not None:
                last_update_dt = datetime.fromtimestamp(u.last_updated, tz=timezone.utc)

            if is_multi_year:
                validated_count = getattr(u, "validated_years_count", 0) or 0
                completion_progress = f"{validated_count}/{len(years)}"
            else:
                completion_progress = (
                    u.completion_progress or DEFAULT_COMPLETION_PROGRESS
                )
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
                    "last_update": last_update_dt,
                    "highest_result_category": self._map_module_id_to_name(
                        highest_category_module_id
                    ),
                    "total_carbon_footprint": round(total_footprint_tonnes, 2),
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
            "total_pages": ceil(total / page_size) if page_size > 0 else 1,
            "emission_breakdown": emission_breakdown,
            "validated_units_count": validated_units_count,
            "in_progress_units_count": in_progress_units_count,
            "not_started_units_count": not_started_units_count,
            "total_units_count": total_units_count,
            "module_status_counts": module_status_counts,
        }

    async def get_usage_report(
        self,
        path_affiliation: Optional[List[str]] = None,
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
            path_affiliation: Optional list of affiliation filters (unit names or IDs)
            path_lvl4: Optional list of hierarchy level 4 filters (unit names or IDs)
            completion_status: Optional filter for report-level completion status.
            search: Optional search term to filter results.
            modules: Optional filter for specific module types (ModuleTypeEnum names)
              and statuses (e.g., ["headcount:2", "professional_travel:1"])
            years: Optional filter for specific years (e.g., [2024, 2025])
        Returns:
            A list of dictionaries containing year, unit information, module type,
            module status, and last updated timestamp for each module matching
            the filters.
        """
        hierarchy_unit_ids = await self._resolve_hierarchy_unit_ids(
            path_affiliation=path_affiliation,
            path_lvl4=path_lvl4,
        )
        # If hierarchy filters were provided but matched no units, return no results.
        if hierarchy_unit_ids is not None and not hierarchy_unit_ids:
            return []

        report: list[dict] = []

        columns: List[Any] = [
            col(CarbonReport.year),
            col(Unit.institutional_id).label("unit_institutional_id"),
            col(Unit.path_name).label("unit_path_name"),
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
            .join(Unit, Unit.id == CarbonReport.unit_id)
            .order_by(CarbonReport.id, CarbonReportModule.module_type_id)
        )
        if years:
            statement = statement.where(col(CarbonReport.year).in_(years))
        if completion_status is not None:
            statement = statement.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )
        if search:
            search_term = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Unit.name).like(search_term),
                    func.lower(Unit.institutional_code).like(search_term),
                )
            )
        if modules:
            module_conditions: List[Any] = []
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
                    module_conditions.append(
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
                    module_conditions.append(
                        col(CarbonReportModule.module_type_id) == module_type
                    )
            statement = statement.where(or_(*module_conditions))
        if hierarchy_unit_ids is not None:
            statement = statement.where(col(Unit.id).in_(hierarchy_unit_ids))

        cursor = await self.session.stream(statement)
        async for partition in cursor.partitions(500):
            for row in partition:
                last_updated_iso = None
                if row.last_updated is not None:
                    last_updated_iso = datetime.fromtimestamp(
                        row.last_updated, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")

                module_status_str = ModuleStatus(row.status).name

                report.append(
                    {
                        "year": row.year,
                        "unit_institutional_id": row.unit_institutional_id,
                        "unit_path_name": row.unit_path_name,
                        "module_name": ModuleTypeEnum(row.module_type_id).name,
                        "module_status": module_status_str,
                        "last_updated": last_updated_iso,
                    }
                )

        return report

    async def get_detailed_report(
        self,
        data_entry_type: DataEntryTypeEnum,
        path_affiliation: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
        completion_status: Optional[ModuleStatus] = None,
        search: Optional[str] = None,
        modules: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
    ) -> list[dict]:
        """
        Get a detailed report of carbon report data entries for a given data entry
        type, including associated units, years, raw data payloads, and emissions.

        Args:
            data_entry_type: The type of data entry to filter by
            path_affiliation: Optional list of affiliation filters (unit names or IDs)
            path_lvl4: Optional list of hierarchy level 4 filters (unit names or IDs)
            completion_status: Optional filter for report-level completion status.
            search: Optional search term to filter results.
            modules: Optional filter for specific module types (ModuleTypeEnum names)
              and statuses (e.g., ["headcount:2", "professional_travel:1"])
            years: Optional filter for specific years (e.g., [2024, 2025])
        Returns:
            A list of dictionaries where each item represents a data entry and
            contains:
            - ``data_entry_type``: The name of the data entry type.
            - ``year``: The reporting year.
            - ``unit_institutional_id``: The institutional identifier of the unit.
            - ``unit_path_name``: The full hierarchy path of the unit.
            - ``data_entry_id``: The ID of the data entry record.
            - ``kg_co2eq``: The summed emissions in kilograms of CO2 equivalent
              associated with the data entry.
            - All fields from the underlying data-entry payload, flattened into
              the top-level dictionary.
        """
        hierarchy_unit_ids = await self._resolve_hierarchy_unit_ids(
            path_affiliation=path_affiliation,
            path_lvl4=path_lvl4,
        )
        # If hierarchy filters were provided but matched no units, return no results.
        if hierarchy_unit_ids is not None and not hierarchy_unit_ids:
            return []

        report: list[dict] = []

        columns: List[Any] = [
            col(DataEntry.data_entry_type_id),
            col(CarbonReport.year),
            col(Unit.institutional_id).label("unit_institutional_id"),
            col(Unit.path_name).label("unit_path_name"),
            col(DataEntry.id).label("data_entry_id"),
            col(DataEntry.data),
            func.coalesce(
                func.sum(col(DataEntryEmission.kg_co2eq)),
                0,
            ).label("kg_co2eq"),
        ]
        statement = (
            select(*columns)
            .select_from(DataEntry)
            .join(
                CarbonReportModule,
                CarbonReportModule.id == DataEntry.carbon_report_module_id,
            )
            .join(
                CarbonReport,
                CarbonReport.id == CarbonReportModule.carbon_report_id,
            )
            .join(Unit, Unit.id == CarbonReport.unit_id)
            .outerjoin(
                DataEntryEmission,
                DataEntryEmission.data_entry_id == DataEntry.id,
            )
            .where(DataEntry.data_entry_type_id == data_entry_type.value)
            .group_by(
                col(CarbonReport.year),
                col(Unit.institutional_id),
                col(Unit.path_name),
                col(DataEntry.id),
            )
        )

        # Additional filters based on provided parameters
        if years:
            statement = statement.where(col(CarbonReport.year).in_(years))
        if completion_status is not None:
            statement = statement.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )
        if search:
            search_term = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Unit.name).like(search_term),
                    func.lower(Unit.institutional_code).like(search_term),
                )
            )
        if modules:
            module_conditions: List[Any] = []
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
                    module_conditions.append(
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
                    module_conditions.append(
                        col(CarbonReportModule.module_type_id) == module_type
                    )
            statement = statement.where(or_(*module_conditions))
        if hierarchy_unit_ids is not None:
            statement = statement.where(col(Unit.id).in_(hierarchy_unit_ids))

        cursor = await self.session.stream(statement)
        async for partition in cursor.partitions(500):
            for row in partition:
                # Remove primary_factor_id from data
                data = row.data.copy() if row.data else {}
                data.pop("primary_factor_id", None)
                report.append(
                    {
                        "data_entry_type": DataEntryTypeEnum(
                            row.data_entry_type_id
                        ).name,
                        "year": row.year,
                        "unit_institutional_id": row.unit_institutional_id,
                        "unit_path_name": row.unit_path_name,
                        "data_entry_id": row.data_entry_id,
                        **data,
                        "kg_co2eq": row.kg_co2eq,
                    }
                )

        return report

    async def get_results_report(
        self,
        path_affiliation: Optional[List[str]] = None,
        path_lvl4: Optional[List[str]] = None,
        completion_status: Optional[ModuleStatus] = None,
        search: Optional[str] = None,
        years: Optional[List[int]] = None,
    ) -> list[dict]:
        """
        Get a report of carbon report results aggregated at the unit-year level,
        including scope totals and breakdowns by emission type.

        Args:
            path_affiliation: Optional list of affiliation filters (unit names or IDs)
            path_lvl4: Optional list of hierarchy level 4 filters (unit names or IDs)
            completion_status: Optional filter for report-level completion status.
            search: Optional search term to filter results.
            years: Optional filter for specific years (e.g., [2024, 2025])
        Returns:
            A list of dictionaries containing year, unit info, scope1/2/3 totals,
            and breakdown by emission type.
        """
        hierarchy_unit_ids = await self._resolve_hierarchy_unit_ids(
            path_affiliation=path_affiliation,
            path_lvl4=path_lvl4,
        )
        # If hierarchy filters were provided but matched no units, return no results.
        if hierarchy_unit_ids is not None and not hierarchy_unit_ids:
            return []

        report: list[dict] = []

        columns: List[Any] = [
            col(CarbonReport.year),
            col(Unit.institutional_id).label("unit_institutional_id"),
            col(Unit.path_name).label("unit_path_name"),
            col(CarbonReport.stats),
        ]
        statement = (
            select(*columns)
            .join(Unit, Unit.id == CarbonReport.unit_id)
            .order_by(CarbonReport.id)
        )
        if years:
            statement = statement.where(col(CarbonReport.year).in_(years))
        if completion_status is not None:
            statement = statement.where(
                col(CarbonReport.overall_status) == int(completion_status)
            )
        if search:
            search_term = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Unit.name).like(search_term),
                    func.lower(Unit.institutional_code).like(search_term),
                )
            )
        if hierarchy_unit_ids is not None:
            statement = statement.where(col(Unit.id).in_(hierarchy_unit_ids))

        cursor = await self.session.stream(statement)
        async for partition in cursor.partitions(500):
            for row in partition:
                stats = row.stats if isinstance(row.stats, dict) else {}
                by_emission_type = stats.get("by_emission_type") or {}
                # Convert emission type keys to names if possible
                converted_by_emission_type: dict[str, Any] = {}
                for k, v in by_emission_type.items():
                    k_str = str(k)
                    try:
                        emission_type = EmissionType(int(k_str))
                        key = emission_type.name.replace("__", "_")
                    except (ValueError, TypeError):
                        key = k_str
                    converted_by_emission_type[key] = v
                by_emission_type = converted_by_emission_type
                report.append(
                    {
                        "year": row.year,
                        "unit_institutional_id": row.unit_institutional_id,
                        "unit_path_name": row.unit_path_name,
                        "scope1": stats.get("scope1"),
                        "scope2": stats.get("scope2"),
                        "scope3": stats.get("scope3"),
                        "total": stats.get("total"),
                        # Flatten by_emission_type into top-level keys
                        **by_emission_type,
                    }
                )

        return report

    def _map_module_id_to_name(self, module_type_id: Optional[int]) -> str:
        """Helper to map internal IDs to the display names used in UI."""
        if not module_type_id:
            return "—"
        # Map based on your ModuleTypeEnum/metadata
        return f"{ModuleTypeEnum(module_type_id).name}"
