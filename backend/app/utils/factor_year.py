"""Factor-year resolution shared by emission computation paths."""

from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.repositories.carbon_project_repo import CarbonProjectRepository


async def resolve_factor_year(
    session: AsyncSession, report: CarbonReport
) -> Optional[int]:
    """Return the year whose factors apply to ``report``'s entries.

    The reference year wins: Simulator Plan reports source all factors from
    their baseline year (plan years can be in the future, where no factors
    exist). A plan year without a reference year falls back to the year of
    the unit's most recent Calculator report, so an "en amont" project (no
    baseline chosen) still computes with real factors. Calculator and
    Explore reports, and plans of units without any Calculator report, use
    their own year.
    """
    if report.reference_year is not None:
        return report.reference_year
    if report.carbon_project_id is not None:
        project = await session.get(CarbonProject, report.carbon_project_id)
        if (
            project is not None
            and project.carbon_report_type == CarbonReportType.SIMULATOR_PLAN
        ):
            latest = await CarbonProjectRepository(session).get_latest_calculator_year(
                report.unit_id
            )
            if latest is not None:
                return latest
    return report.year
