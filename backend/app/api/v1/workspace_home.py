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
- ``emission_breakdown`` — chart data, augmented with
  ``total_tonnes_validated_co2eq`` (the validated-only headline figure, distinct
  from the breakdown's all-modules ``total_tonnes_co2eq``). Also carries
  ``module_states`` (per-module ``{module_type_id, status}``) which the frontend
  fans out to the sidebar timeline + validation gates — the breakdown already
  computes this map internally, so no separate ``list_modules`` call is needed.

It is deliberately *not* per-module permission-gated (only unit access is
enforced, like ``results-summary``) so limited users can load their home page
without tripping the global 403 → ``/unauthorized`` redirect.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.v1.carbon_report_module_stats import (
    build_emission_breakdown,
    build_validated_totals,
)
from app.api.v1.year_configuration import build_year_configuration_response
from app.core.logging import get_logger
from app.core.policy import require_unit_access
from app.models.unit import Unit
from app.models.user import User
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.year_configuration import YearConfigurationResponse
from app.services.carbon_report_service import CarbonReportService

logger = get_logger(__name__)
router = APIRouter()


class WorkspaceHomeResponse(BaseModel):
    """Minimal aggregate payload the frontend fans out across its stores."""

    carbon_report_id: int
    year_config: Optional[YearConfigurationResponse] = None
    emission_breakdown: dict


@router.get("/{unit_id}/{year}/home", response_model=WorkspaceHomeResponse)
async def get_workspace_home(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceHomeResponse:
    """Resolve the full workspace + home dashboard payload in one call.

    Gets (or creates) the carbon report for ``unit_id``/``year``, then bundles
    the year configuration and the emission breakdown (with the validated-only
    total merged in; the breakdown also carries the per-module states).
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)

    report_service = CarbonReportService(db)
    report = await report_service.get_by_unit_and_year(unit_id, year)
    if report is None:
        report = await report_service.create(
            CarbonReportCreate(unit_id=unit_id, year=year)
        )
        await db.commit()

    year_config = await build_year_configuration_response(
        db, year, current_user.provider
    )

    emission_breakdown = await build_emission_breakdown(db, report.id)
    # The headline needs the validated-only total, which differs from the
    # breakdown's all-modules total. Reuse the shared helper so validated
    # semantics (headcount FTE handling, simulator treat-all-validated) stay
    # identical to /modules-stats/{id}/validated-totals.
    validated = await build_validated_totals(db, report.id)
    emission_breakdown["total_tonnes_validated_co2eq"] = validated["total_tonnes_co2eq"]

    return WorkspaceHomeResponse(
        carbon_report_id=report.id,
        year_config=year_config,
        emission_breakdown=emission_breakdown,
    )
