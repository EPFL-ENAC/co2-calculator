"""Carbon report repository for database operations."""

from sqlalchemy import JSON, String, column, true
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate

logger = get_logger(__name__)


class CarbonReportRepository:
    """Repository for CarbonReport database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CarbonReportCreate) -> CarbonReport:
        """Create a new carbon report."""
        db_obj = CarbonReport.model_validate(data.model_dump())
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def bulk_upsert(self, data: list[CarbonReportCreate]) -> list[CarbonReport]:
        """Bulk upsert carbon reports using INSERT ... ON CONFLICT DO NOTHING.

        Uses the uq_carbon_reports_project_year constraint (carbon_project_id,
        year, is_grant) as the conflict target. Callers must resolve
        carbon_project_id before
        calling this method (it must be non-null for conflict detection to work).
        """
        stmt = (
            insert(CarbonReport)
            .values([d.model_dump() for d in data])
            .on_conflict_do_nothing(constraint="uq_carbon_reports_project_year")
            .returning(CarbonReport)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, carbon_report_id: int) -> CarbonReport | None:
        """Get a carbon report by ID."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_unit(self, unit_id: int) -> list[CarbonReport]:
        """List Calculator carbon reports for a unit (excludes Simulator types)."""
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonProject.carbon_report_type == CarbonReportType.CALCULATOR,
            )
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def _calculator_reports_of(self, unit_ids: list[int], year: int | None):
        """Base select of several units' Calculator reports, optionally one year."""
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                col(CarbonReport.unit_id).in_(unit_ids),
                CarbonProject.carbon_report_type == CarbonReportType.CALCULATOR,
            )
        )
        if year is not None:
            statement = statement.where(CarbonReport.year == year)
        return statement

    async def list_by_units(
        self, unit_ids: list[int], year: int | None = None
    ) -> list[CarbonReport]:
        """Calculator reports of several units in one query, oldest year first.

        A unit can own more than one Calculator project, so a (unit, year) pair
        may yield several reports; callers fold them.
        """
        statement = self._calculator_reports_of(unit_ids, year).order_by(
            col(CarbonReport.year), col(CarbonReport.id)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def sum_stat_buckets_by_year(
        self, unit_ids: list[int]
    ) -> list[tuple[int, str, int, float]]:
        """Sum persisted ``stats.buckets`` kg per (year, bucket key) across units.

        One grouped query over ``json_each(stats->'buckets')`` instead of a
        Python fold over every report. Rows are ``(year, key, scope, total_kg)``
        ordered by year then key.
        """
        bucket = func.json_each(col(CarbonReport.stats)["buckets"]).table_valued(
            column("key", String), column("value", JSON)
        )
        scope = func.max(bucket.c.value["scope"].as_integer())
        total_kg = func.sum(bucket.c.value["total_kg"].as_float())
        statement = (
            self._calculator_reports_of(unit_ids, None)
            .with_only_columns(col(CarbonReport.year), bucket.c.key, scope, total_kg)
            .join(bucket, true())
            .where(bucket.c.key.is_not(None))
            .group_by(col(CarbonReport.year), bucket.c.key)
            .order_by(col(CarbonReport.year), bucket.c.key)
        )
        result = await self.session.execute(statement)
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def list_validated_buckets_by_year(
        self, unit_ids: list[int]
    ) -> dict[int, set[str]]:
        """Union of ``stats.validated_buckets`` per year across the units."""
        statement = self._calculator_reports_of(unit_ids, None).with_only_columns(
            col(CarbonReport.year), col(CarbonReport.stats)["validated_buckets"]
        )
        result = await self.session.execute(statement)
        validated: dict[int, set[str]] = {}
        for year, keys in result.all():
            validated.setdefault(year, set()).update(keys or [])
        return validated

    async def get_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> CarbonReport | None:
        """Get a Calculator carbon report by unit and year."""
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonReport.year == year,
                CarbonProject.carbon_report_type == CarbonReportType.CALCULATOR,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_explore_by_unit_and_reference_year(
        self,
        *,
        unit_id: int,
        reference_year: int,
        created_by: int,
    ) -> CarbonReport | None:
        """Get the Simulator Explore report for a unit + reference year.

        Explore sandboxes are private per user (#2293): only the report whose
        project was created by ``created_by`` is returned. Explore reports
        store the reference year in the ``year`` field (year is always
        non-null), and ``uq_carbon_reports_project_year`` guarantees at most
        one report per project + year.
        """
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                CarbonReport.unit_id == unit_id,
                CarbonReport.year == reference_year,
                CarbonProject.carbon_report_type == CarbonReportType.SIMULATOR_EXPLORE,
                CarbonProject.created_by == created_by,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(
        self, carbon_report_id: int, data: CarbonReportUpdate
    ) -> CarbonReport | None:
        """Update a carbon report."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, carbon_report_id: int) -> bool:
        """Delete a carbon report."""
        statement = select(CarbonReport).where(CarbonReport.id == carbon_report_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.flush()
        return True

    async def get_reporting_overview(
        self,
        path_lvl2: list[str] | None = None,
        path_lvl3: list[str] | None = None,
        path_lvl4: list[str] | None = None,
        overall_status: ModuleStatus | None = None,
        search: str | None = None,
        modules: list[str] | None = None,
        years: list[int] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[CarbonReport]:
        """Retrieves the aggregated reporting data using a Deferred Join strategy.
        First paginates the Units, then calculates footprints ONLY for those 50 units.
        """
        # Reporting is Calculator-only: never surface Simulator Explore/Plan
        # reports (they are carbon_reports rows too, under non-Calculator
        # projects) in the backoffice reporting overview.
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(col(CarbonProject.carbon_report_type) == CarbonReportType.CALCULATOR)
        )
        if years:
            statement = statement.where(col(CarbonReport.year).in_(years))

        statement = statement.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(statement)
        return list(result.scalars().all())
