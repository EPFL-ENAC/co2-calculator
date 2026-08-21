"""The identity an interactive write already resolved (#2050 J4).

``resolve_report_module`` reads the carbon report, its project and the module
before any route body runs. Four services then re-derived the same three rows
nine times between them, because each is constructed with only a session —
``DataEntryEmissionService`` even holds a report memo that could not help,
since the route had used a different instance. This carries the resolved rows
down instead.
"""

from pydantic import BaseModel

from app.schemas.carbon_report import CarbonReportModuleRead, CarbonReportRead


class WriteScope(BaseModel):
    """Resolved identity for one interactive write."""

    report: CarbonReportRead
    module: CarbonReportModuleRead
    # Whether the module's report belongs to a Simulator project — the single
    # fact ``is_simulator_module`` needed its own three-table JOIN to answer.
    is_simulator: bool

    @property
    def year(self) -> int | None:
        return self.report.year

    @property
    def unit_id(self) -> int | None:
        return self.report.unit_id
