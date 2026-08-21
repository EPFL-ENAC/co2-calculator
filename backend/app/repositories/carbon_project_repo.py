"""Carbon project repository for simulator plan database operations."""

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.user import User

logger = get_logger(__name__)


class CarbonProjectRepository:
    """Repository for CarbonProject database operations (Simulator Plan)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _plan_with_creator_stmt(self):
        """Base SELECT of plan projects joined with the creator display name."""
        return (
            select(CarbonProject, col(User.display_name))
            .outerjoin(User, col(CarbonProject.created_by) == col(User.id))
            .where(CarbonProject.carbon_report_type == CarbonReportType.SIMULATOR_PLAN)
        )

    async def list_plans_by_unit(
        self, unit_id: int
    ) -> list[tuple[CarbonProject, str | None]]:
        """List plan projects for a unit with creator names, newest first.

        Ordered by id (creation order); created_at is nullable so ordering
        on it would need NULL handling.
        """
        statement = (
            self._plan_with_creator_stmt()
            .where(CarbonProject.unit_id == unit_id)
            .order_by(col(CarbonProject.id).desc())
        )
        result = await self.session.execute(statement)
        return [(project, display_name) for project, display_name in result.all()]

    async def get_plan(self, plan_id: int) -> CarbonProject | None:
        """Get a plan project by ID (non-plan projects are not returned)."""
        statement = select(CarbonProject).where(
            CarbonProject.id == plan_id,
            CarbonProject.carbon_report_type == CarbonReportType.SIMULATOR_PLAN,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_plan_with_creator(
        self, plan_id: int
    ) -> tuple[CarbonProject, str | None] | None:
        """Get a plan project by ID, with the creator name."""
        statement = self._plan_with_creator_stmt().where(CarbonProject.id == plan_id)
        result = await self.session.execute(statement)
        row = result.first()
        if row is None:
            return None
        project, display_name = row
        return project, display_name

    async def list_plan_names(self, unit_id: int) -> set[str]:
        """Return the names of all plan projects for a unit."""
        statement = select(col(CarbonProject.name)).where(
            CarbonProject.unit_id == unit_id,
            CarbonProject.carbon_report_type == CarbonReportType.SIMULATOR_PLAN,
        )
        result = await self.session.execute(statement)
        return {name for name in result.scalars().all() if name is not None}

    async def list_report_ids_for_project(self, project_id: int) -> list[int]:
        """Return the IDs of carbon reports belonging to a project."""
        statement = select(col(CarbonReport.id)).where(
            CarbonReport.carbon_project_id == project_id
        )
        result = await self.session.execute(statement)
        return [report_id for report_id in result.scalars().all()]

    async def get_calculator_report(
        self, unit_id: int, year: int
    ) -> CarbonReport | None:
        """Return the unit's Calculator report for a year, or None."""
        statement = (
            select(CarbonReport)
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                col(CarbonReport.unit_id) == unit_id,
                col(CarbonReport.year) == year,
                col(CarbonProject.carbon_report_type) == CarbonReportType.CALCULATOR,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_calculator_year(self, unit_id: int) -> int | None:
        """Year of the unit's most recent Calculator report, or None.

        The default factor year of plan years without a reference year.
        """
        statement = (
            select(func.max(col(CarbonReport.year)))
            .join(
                CarbonProject,
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
            )
            .where(
                col(CarbonReport.unit_id) == unit_id,
                col(CarbonProject.carbon_report_type) == CarbonReportType.CALCULATOR,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_report_stats_by_project(
        self, project_ids: list[int]
    ) -> list[tuple[int, dict | None]]:
        """Return ``(project_id, report.stats)`` for many projects in one query.

        Backs the plan totals shown in the home-page planner table: one query
        for the whole unit instead of one per plan.

        Project Grant reports are excluded: how grant results combine with the
        per-year results is still open (#1977), and summing both would count
        the same project twice.
        """
        if not project_ids:
            return []
        statement = select(
            col(CarbonReport.carbon_project_id), col(CarbonReport.stats)
        ).where(
            col(CarbonReport.carbon_project_id).in_(project_ids),
            col(CarbonReport.is_grant).is_(False),
        )
        result = await self.session.execute(statement)
        return [(project_id, stats) for project_id, stats in result.all()]

    async def list_reports_for_project(self, project_id: int) -> list[CarbonReport]:
        """Return the carbon reports of a project, ordered by year."""
        statement = (
            select(CarbonReport)
            .where(col(CarbonReport.carbon_project_id) == project_id)
            .order_by(col(CarbonReport.year))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_reports_by_ids(self, report_ids: list[int]) -> list[CarbonReport]:
        """Return the given carbon reports, ordered by year."""
        if not report_ids:
            return []
        statement = (
            select(CarbonReport)
            .where(col(CarbonReport.id).in_(report_ids))
            .order_by(col(CarbonReport.year))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, project: CarbonProject) -> CarbonProject:
        """Persist and flush a new carbon project."""
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def delete(self, project: CarbonProject) -> None:
        """Delete a carbon project."""
        await self.session.delete(project)
        await self.session.flush()
