"""Factor-year resolution shared by emission computation paths."""

from datetime import UTC, datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.user import User
from app.schemas.carbon_report import CarbonReportRead
from app.services.year_config_service import is_year_started


async def resolve_factor_year(
    session: AsyncSession, report: CarbonReport | CarbonReportRead
) -> int | None:
    """Return the year whose factors apply to ``report``'s entries.

    The reference year wins: Simulator Plan reports source all factors from
    their baseline year (plan years can be in the future, where no factors
    exist). Without one — including a unit with no Calculator report at all
    — Plan falls through to the same latest-started-year check Explore uses
    (#2651), never its own arbitrary planning year. Explore reports (#2656)
    ignore their own year entirely and always use that same check directly,
    no reference tier to check first. Neither ever uses "the unit's latest
    Calculator report year": that year is whatever the Calculator happens to
    be on, which can itself be an unstarted/unpublished year (#2651) — there
    is no tier that trusts an unconfirmed year, only ``is_year_started``
    checks. Calculator reports use their own year; it's always a year with
    published factors by construction.
    """
    if report.reference_year is not None:
        return report.reference_year
    if report.carbon_project_id is not None:
        project = await session.get(CarbonProject, report.carbon_project_id)
        if project is not None:
            if project.carbon_report_type in (
                CarbonReportType.SIMULATOR_PLAN,
                CarbonReportType.SIMULATOR_EXPLORE,
            ):
                return await _resolve_latest_started_year(session, project.created_by)
    return report.year


async def resolve_factor_year_safe(
    session: AsyncSession, report: CarbonReport | CarbonReportRead
) -> int | None:
    """``resolve_factor_year``, but None instead of raising (#2631).

    For read-only responses (Explore's own routes, a Plan year's DTO): "no
    published factors for either fallback year" is a state the caller must
    display, not a reason to fail the request that's merely reporting it.
    """
    try:
        return await resolve_factor_year(session, report)
    except ValueError:
        return None


async def _resolve_latest_started_year(
    session: AsyncSession, created_by: int | None
) -> int:
    """The latest started year as of today, N-1 falling back to N-2.

    Shared tail for Explore and Plan once reference year is exhausted (both
    always for Explore, since it has none) — #2656 / #2651. N is today's
    calendar year, not any report's own year: a report opened in December
    2026 and one opened in January 2027 resolve to different N-1s, by
    design. Never a project's own year — there's no published factor set
    for an arbitrary current/future year. Raises rather than silently
    pricing against nothing.
    """
    if created_by is None:
        raise ValueError("Project has no creator to resolve a provider from")
    user = await session.get(User, created_by)
    if user is None:
        raise ValueError(f"Project creator {created_by} not found")
    this_year = datetime.now(UTC).year
    for candidate in (this_year - 1, this_year - 2):
        if await is_year_started(session, candidate, user.provider):
            return candidate
    raise ValueError(f"No published factors for {this_year - 1} or {this_year - 2}")
