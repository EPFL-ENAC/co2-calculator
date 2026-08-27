"""Workspace-home aggregate endpoint.

Collapses the workspace/stats side of the home-page load into a single request.
The frontend used to fire a dependency chain (resolve/create the carbon report →
module states → year config → emission breakdown → validated total) because each
step needed the ``carbon_report_id`` returned by the previous one. This endpoint
resolves that chain server-side and returns exactly what the workspace pages
consume — nothing more:

- ``carbon_report_id`` — pages sharing the workspace guard fetch their own data
  keyed by this id.
- ``year_config`` — module visibility et al.; ``null`` mirrors the 404 of
  ``GET /year-configuration/{year}`` (frontend renders the "create year" state).
  Unlike that route, home returns a slim ``{year, config}`` shape (see
  ``HomeYearConfiguration``) with the *raw* stored config and **no** sync-job /
  incomplete / recalculation enrichment, and it drops the top-level
  ``is_started``/``updated_at``/``configuration_completed``/``pipeline_id``/
  ``recalculation_status`` fields — the workspace pages only read module
  ``enabled``/``uncertainty_tag`` and submodule ``enabled``/``threshold``/
  ``inputs_deactivated``/``csv_deactivated`` (+ ``reduction_objectives``). All of
  that is backoffice-only (data-management page, which refetches the full config),
  so skipping it here drops two DB queries per load and the per-submodule
  ``latest_*_job`` payload bloat.
- ``stats`` — the persisted ``CarbonReport.stats``, augmented with
  ``total_tonnes_validated_co2eq`` (the validated-only headline figure, distinct
  from the all-modules ``total``).
- ``module_states`` (per-module ``{module_type_id, status}``) which the frontend
  fans out to the sidebar timeline + validation gates.
- ``project_plans`` — the unit's Simulator Plans visible to the caller, each with
  its whole-range ``total_tonnes_co2eq``, backing the home-page planner table.
  Plans are per-unit and year-independent, so this block ignores ``year``; the
  table refetches ``GET /project-plans/unit/{unit_id}/`` (same shape) after
  create/duplicate/delete.

It is deliberately *not* per-module permission-gated (only unit access is
enforced, like ``results-summary``) so limited users can load their home page
without tripping the global 403 → ``/unauthorized`` redirect.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.v1.carbon_report_module_stats import build_validated_totals
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.plan_policy import PlanPolicy
from app.core.policy import require_unit_access
from app.models.carbon_report import CarbonReportModule
from app.models.unit import Unit
from app.models.user import User
from app.models.year_configuration import YearConfiguration
from app.schemas.simulator_plan import SimulatorPlanRead
from app.services.carbon_report_service import CarbonReportService
from app.services.simulator_plan_service import SimulatorPlanService

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


class HomeYearConfiguration(BaseModel):
    """Slim year-config for the home aggregate — only what workspace pages read.

    The workspace pages (home / module / results / sidebar) read module
    ``enabled``/``uncertainty_tag`` and submodule
    ``enabled``/``threshold``/``inputs_deactivated``/``csv_deactivated`` (plus
    ``reduction_objectives``) — all of which live under ``config``. Every other
    field of the full ``YearConfigurationResponse`` (``is_started``,
    ``updated_at``, ``configuration_completed``, ``pipeline_id``,
    ``recalculation_status``) is read only on the backoffice data-management page,
    which refetches the full config via ``GET /year-configuration/{year}``. So
    home omits them entirely.
    """

    year: int
    config: dict[str, Any]
    # The frontend's yearConfig store hard-errors on any year-config payload
    # missing this bound (#1204 follow-up), and the workspace guard feeds this
    # slim shape straight into it — so the aggregate must carry it too.
    min_configurable_year: int


async def build_home_year_configuration(
    db: AsyncSession, year: int, provider
) -> HomeYearConfiguration | None:
    """Slim year-configuration for the home aggregate — no job/recalc enrichment.

    Returns the raw stored config (or ``None`` if no row exists for
    ``(year, provider)``). Deliberately does NOT run the sync-job / incomplete /
    recalculation enrichment that ``build_year_configuration_response`` does for
    the backoffice data-management page: the workspace pages never read those
    fields, so skipping them avoids two extra DB queries and a large per-submodule
    ``latest_*_job`` payload.
    """
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == provider,
    )
    result = (await db.exec(stmt)).first()
    if not result:
        return None

    return HomeYearConfiguration(
        year=result.year,
        config=result.config,
        min_configurable_year=settings.MIN_CONFIGURABLE_YEAR,
    )


class WorkspaceHomeResponse(BaseModel):
    """Minimal aggregate payload the frontend fans out across its stores."""

    carbon_report_id: int
    year_config: HomeYearConfiguration | None = None
    stats: dict
    module_states: list[dict]
    project_plans: list[SimulatorPlanRead] = []


@router.get("/{unit_id}/{year}/home", response_model=WorkspaceHomeResponse)
async def get_workspace_home(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceHomeResponse:
    """Resolve the full workspace + home dashboard payload in one call.

    Gets the carbon report for ``unit_id``/``year``, then bundles the year
    configuration, the persisted report stats (with the validated-only total
    merged in) and the per-module states.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)

    report_service = CarbonReportService(db)
    report = await report_service.get_by_unit_and_year(unit_id, year)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found"
        )

    year_config = await build_home_year_configuration(db, year, current_user.provider)

    stats = dict(report.stats or {})
    # The headline needs the validated-only total with headcount-FTE and
    # simulator treat-all-validated semantics; reuse the shared helper.
    validated = await build_validated_totals(db, report.id)
    stats["total_tonnes_validated_co2eq"] = validated["total_tonnes_co2eq"]

    module_state_rows = (
        await db.execute(
            select(
                col(CarbonReportModule.module_type_id),
                col(CarbonReportModule.status),
            ).where(col(CarbonReportModule.carbon_report_id) == report.id)
        )
    ).all()
    module_states = [
        {"module_type_id": module_type_id, "status": module_status}
        for module_type_id, module_status in module_state_rows
    ]

    plans = await SimulatorPlanService(db).list_plans(unit_id)
    visible_plans = PlanPolicy.from_unit(current_user, unit).visible(plans)

    return WorkspaceHomeResponse(
        carbon_report_id=report.id,
        year_config=year_config,
        stats=stats,
        module_states=module_states,
        project_plans=visible_plans,
    )
