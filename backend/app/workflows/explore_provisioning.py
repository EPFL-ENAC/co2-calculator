"""Simulator Explore sandbox provisioning workflow (#2487, ADR-014).

The PUT route's one "does this exist" decision, replacing the GET → 404 →
POST pair the frontend used to orchestrate — two round trips, and the 404
used as control flow was exactly what manufactured the race #2483 had to
SAVEPOINT-guard. Explore's sandbox crosses three aggregates (CarbonProject,
CarbonReport, CarbonReportModule) via ``CarbonReportService``; per ADR-014
that makes existence an explicit workflow step, and the workflow — not the
service — owns the commit for the path that creates one.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.carbon_report import CarbonReportRead
from app.services.carbon_report_service import CarbonReportService


class ExploreProvisioningWorkflow:
    """Ensures a user's Simulator Explore sandbox exists for unit + year."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.report_service = CarbonReportService(session)

    async def ensure(
        self, *, unit_id: int, reference_year: int, created_by: int
    ) -> CarbonReportRead:
        """Idempotent: create the sandbox on first call, return it after.

        ``get_explore``/``create_explore`` are each single-purpose and
        never commit (services never commit); this is the one place that
        decides which of them applies, and the one place that commits the
        create path.
        """
        existing = await self.report_service.get_explore(
            unit_id=unit_id, reference_year=reference_year, created_by=created_by
        )
        if existing is not None:
            return existing
        created = await self.report_service.create_explore(
            unit_id=unit_id, reference_year=reference_year, created_by=created_by
        )
        await self.session.commit()
        return created
