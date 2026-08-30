"""Carbon project repository for simulator plan database operations."""

from sqlalchemy.orm import aliased
from sqlmodel import and_, col, exists, func, select
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
        """Base SELECT of plan projects with the creator name and grant flag.

        A plan is a grant proposal iff it owns an ``is_grant`` report; the
        flag is derived here rather than stored on the project.
        """
        has_grant = (
            exists()
            .where(
                col(CarbonReport.carbon_project_id) == col(CarbonProject.id),
                col(CarbonReport.is_grant).is_(True),
            )
            .label("is_grant_proposal")
        )
        return (
            select(CarbonProject, col(User.display_name), has_grant)
            .outerjoin(User, col(CarbonProject.created_by) == col(User.id))
            .where(CarbonProject.carbon_report_type == CarbonReportType.SIMULATOR_PLAN)
        )

    async def list_plans_by_unit(
        self, unit_id: int
    ) -> list[tuple[CarbonProject, str | None, bool, list[dict]]]:
        """Plans of a unit with creator name and year-report stats, newest first.

        Ordered by id (creation order); created_at is nullable so ordering
        on it would need NULL handling. The per-plan report stats come from
        the same statement rather than a follow-up keyed on the ids this one
        returned (#2527 task 5) — one row per (plan, year report), folded
        back to one entry per plan below.

        Project Grant reports are excluded from the stats: how grant results
        combine with the per-year results is still open (#1977), and summing
        both would count the same project twice.
        """
        year_report = aliased(CarbonReport)
        statement = (
            self._plan_with_creator_stmt()
            .add_columns(col(year_report.id), col(year_report.stats))
            .outerjoin(
                year_report,
                and_(
                    col(year_report.carbon_project_id) == col(CarbonProject.id),
                    col(year_report.is_grant).is_(False),
                ),
            )
            .where(CarbonProject.unit_id == unit_id)
            .order_by(col(CarbonProject.id).desc())
        )
        result = await self.session.execute(statement)
        plans: dict[int | None, tuple[CarbonProject, str | None, bool, list[dict]]] = {}
        for project, display_name, is_grant_proposal, report_id, stats in result.all():
            entry = plans.setdefault(
                project.id, (project, display_name, bool(is_grant_proposal), [])
            )
            if report_id is not None:
                entry[3].append(dict(stats or {}))
        return list(plans.values())

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
    ) -> tuple[CarbonProject, str | None, bool] | None:
        """Get a plan project by ID, with the creator name and grant flag."""
        statement = self._plan_with_creator_stmt().where(CarbonProject.id == plan_id)
        result = await self.session.execute(statement)
        row = result.first()
        if row is None:
            return None
        project, display_name, is_grant_proposal = row
        return project, display_name, bool(is_grant_proposal)

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
