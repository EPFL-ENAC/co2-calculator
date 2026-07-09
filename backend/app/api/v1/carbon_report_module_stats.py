"""Module stats API endpoints.

The heavy chart payloads (emission breakdown, IT breakdown) are gone: the
frontend reads the persisted ``carbon_report.stats`` /
``carbon_report_module.stats`` shapes written at recompute time. Only the
results summary remains an endpoint because it compares against the
previous year's report, which can change after this report was computed.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import User
from app.schemas.carbon_report import CarbonReportModuleRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_service import DataEntryService
from app.services.unit_totals_service import UnitTotalsService
from app.utils.report_computations import (
    compute_results_summary,
    compute_validated_totals,
)

logger = get_logger(__name__)
router = APIRouter()


async def build_validated_totals(db: AsyncSession, carbon_report_id: int) -> dict:
    """Compute validated totals for a carbon report from persisted stats.

    Aggregates emissions (kg → tonnes CO2eq) and FTE across all validated
    modules. Both are keyed by module_type_id so headcount appears with
    total_fte while other modules show total_tonnes_co2eq. Simulator Explore
    reports have no validation step, so every module counts there.

    Returns:
        {
            "modules": {1: 25.5, 2: 15.0, 4: 41.7, 7: 5.0},
            "total_tonnes_co2eq": 61.7,
            "total_fte": 25.5
        }
    """
    report_type_row = await db.execute(
        select(CarbonProject.carbon_report_type)
        .join(
            CarbonReport, col(CarbonReport.carbon_project_id) == col(CarbonProject.id)
        )
        .where(col(CarbonReport.id) == carbon_report_id)
    )
    report_type = report_type_row.scalar_one_or_none()
    validated_only = report_type != CarbonReportType.SIMULATOR_EXPLORE

    rows = (
        await db.execute(
            select(
                col(CarbonReportModule.module_type_id),
                col(CarbonReportModule.status),
                col(CarbonReportModule.stats),
            ).where(col(CarbonReportModule.carbon_report_id) == carbon_report_id)
        )
    ).all()

    emission_stats: dict[str, float] = {}
    fte_stats: dict[str, float] = {}
    for module_type_id, module_status, stats in rows:
        if validated_only and module_status != ModuleStatus.VALIDATED:
            continue
        if not isinstance(stats, dict):
            continue
        total = stats.get("total", 0.0) or 0.0
        if total:
            emission_stats[str(module_type_id)] = total
        if stats.get("total_fte"):
            fte_stats[str(module_type_id)] = stats["total_fte"]

    return compute_validated_totals(
        emission_stats, fte_stats, str(ModuleTypeEnum.headcount.value)
    )


@router.get(
    "/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, float | None]
)
async def get_module_stats(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, float | None]:
    """
    Get module statistics such as total items and submodules.

    Args:
        module_id: Module identifier
        unit_id: Unit ID to filter equipment
        year: Year for the data
        db: Database session
        current_user: Authenticated user
    Returns:
        Dict with statistics (e.g., total items, total kg_co2eq)
    """
    unit = await db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit {unit_id} not found",
        )
    await _check_module_permission(
        current_user,
        module_id,
        "view",
        institutional_id=unit.institutional_id,
    )

    logger.info(
        f"GET module stats: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    stats: dict[str, float | None] = {}
    carbon_report_module: CarbonReportModuleRead = await CarbonReportModuleService(
        db
    ).get_carbon_report_by_year_and_unit(
        unit_id=unit_id, year=year, module_type_id=ModuleTypeEnum[module_id]
    )

    if module_id == "equipment":
        stats = await DataEntryService(db).get_stats(
            carbon_report_module_id=carbon_report_module.id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {module_id} not found",
        )
    logger.info(f"Module stats returned: {stats}")

    return stats


@router.get("/{carbon_report_id}/report-stats", response_model=dict)
async def get_report_stats(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the persisted report stats with the validated headline merged in.

    Same payload as the ``stats`` field of the workspace-home aggregate; used
    by the frontend to refresh charts after mutations without refetching the
    whole home bundle.
    """
    report = await db.get(CarbonReport, carbon_report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon report {carbon_report_id} not found",
        )
    stats = dict(report.stats or {})
    validated = await build_validated_totals(db, carbon_report_id)
    stats["total_tonnes_validated_co2eq"] = validated["total_tonnes_co2eq"]
    return stats


@router.get("/{carbon_report_id}/validated-totals", response_model=dict)
async def get_validated_totals(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Validated-only totals per module (tonnes; FTE for headcount)."""
    return await build_validated_totals(db, carbon_report_id)


@router.get("/{carbon_report_id}/results-summary", response_model=dict)
async def get_results_summary(
    carbon_report_id: int,
    exclude_modules: list[int] = Query(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get results summary for a carbon report, broken down by module.

    Returns unit-wide totals and per-module results including:
    - total_tonnes_co2eq, total_fte, tonnes_co2eq_per_fte
    - equivalent_car_km, previous year comparison
    """
    logger.info(f"GET results summary: carbon_report_id={sanitize(carbon_report_id)}")

    try:
        raw = await UnitTotalsService(db).get_results_summary(carbon_report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon report {carbon_report_id} not found",
        )

    return compute_results_summary(
        raw["current_emissions"],
        raw["current_fte"],
        raw["prev_emissions"],
        get_settings().CO2_PER_KM_KG,
        str(ModuleTypeEnum.headcount.value),
        exclude_module_type_ids=set(exclude_modules),
    )
