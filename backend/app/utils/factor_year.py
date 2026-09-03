"""Factor-year resolution shared by emission computation paths."""

from datetime import UTC, datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.user import User
from app.repositories.carbon_project_repo import CarbonProjectRepository
from app.schemas.carbon_report import CarbonReportRead
from app.services.year_config_service import is_year_started


async def resolve_factor_year(
    session: AsyncSession, report: CarbonReport | CarbonReportRead
) -> int | None:
    """Return the year whose factors apply to ``report``'s entries.

    The reference year wins: Simulator Plan reports source all factors from
    their baseline year (plan years can be in the future, where no factors
    exist). A plan year without a reference year falls back to the year of
    the unit's most recent Calculator report, so an "en amont" project (no
    baseline chosen) still computes with real factors. Explore reports
    (#2656) ignore their own year entirely — it's just the sandbox's
    creation year, never a year with published factors — and always price
    against the latest started year instead. Calculator reports, and plans
    of units without any Calculator report, use their own year.
    """
    if report.reference_year is not None:
        return report.reference_year
    if report.carbon_project_id is not None:
        project = await session.get(CarbonProject, report.carbon_project_id)
        if project is not None:
            if project.carbon_report_type == CarbonReportType.SIMULATOR_PLAN:
                latest = await CarbonProjectRepository(
                    session
                ).get_latest_calculator_year(report.unit_id)
                if latest is not None:
                    return latest
            if project.carbon_report_type == CarbonReportType.SIMULATOR_EXPLORE:
                return await _resolve_explore_factor_year(session, project.created_by)
    return report.year


async def _resolve_explore_factor_year(
    session: AsyncSession, created_by: int | None
) -> int:
    """Explore always prices against the latest started year (#2656).

    Never the sandbox's own year — there's no published factor set for an
    arbitrary current/future year. Tries last year, falls back to the year
    before that, and raises rather than silently pricing against nothing.
    """
    if created_by is None:
        raise ValueError("Explore project has no creator to resolve a provider from")
    user = await session.get(User, created_by)
    if user is None:
        raise ValueError(f"Explore project creator {created_by} not found")
    this_year = datetime.now(UTC).year
    for candidate in (this_year - 1, this_year - 2):
        if await is_year_started(session, candidate, user.provider):
            return candidate
    raise ValueError(f"No published factors for {this_year - 1} or {this_year - 2}")
