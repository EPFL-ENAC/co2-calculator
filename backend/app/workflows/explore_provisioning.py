"""Simulator Explore sandbox creation workflow (#2656, ADR-014).

Explore's sandbox crosses three aggregates (CarbonProject, CarbonReport,
CarbonReportModule) via ``CarbonReportService``; per ADR-014 that makes
creation an explicit workflow step, and the workflow — not the service —
owns the commit.

Until #2656 this was ``ensure()``: an idempotent get-or-create (#2487),
paired with a 24h TTL that refreshed a stale sandbox in place. Both are
gone. "Start an exploration" always creates a fresh sandbox — a page
mount/refresh included, so a refresh loses the working data by design —
and the route that calls :meth:`create` schedules a background task to
delete the user's other sandboxes for the unit right after. Create and
delete are now two separate, explicit steps instead of one endpoint
deciding both.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.carbon_report import CarbonReportRead
from app.services.carbon_report_service import CarbonReportService


class ExploreProvisioningWorkflow:
    """Creates a fresh Simulator Explore sandbox for a unit + user."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.report_service = CarbonReportService(session)

    async def create(self, *, unit_id: int, created_by: int) -> CarbonReportRead:
        """Always creates — no existence check, no reuse.

        ``create_explore`` never commits (services never commit); this is
        the one place that does, for the one aggregate-crossing create step.
        """
        created = await self.report_service.create_explore(
            unit_id=unit_id, created_by=created_by
        )
        await self.session.commit()
        return created
