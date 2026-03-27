"""Module stats API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.carbon_report import CarbonReportModule
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.schemas.carbon_report import CarbonReportModuleRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.unit_totals_service import UnitTotalsService
from app.utils.emission_category import build_chart_breakdown
from app.utils.report_computations import (
    compute_results_summary,
    compute_validated_totals,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{carbon_report_id}/validated-totals")
async def get_validated_totals(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get validated totals for a carbon report.

    Aggregates emissions (kg → tonnes CO2eq) and FTE across all validated
    modules in the given carbon report. Both are keyed by module_type_id so
    headcount appears with total_fte while other modules show total_tonnes_co2eq.

    Returns:
        {
            "modules": {1: 25.5, 2: 15.0, 4: 41.7, 7: 5.0},
            "total_tonnes_co2eq": 61.7,
            "total_fte": 25.5
        }
    """
    logger.info(f"GET validated totals: carbon_report_id={sanitize(carbon_report_id)}")

    emission_stats = await DataEntryEmissionService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id
    )
    fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id,
        aggregate_by="module_type_id",
    )

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
    await _check_module_permission(current_user, module_id, "view")

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

    if module_id == "equipment-electric-consumption":
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


@router.get("/{carbon_report_id}/results-summary", response_model=dict)
async def get_results_summary(
    carbon_report_id: int,
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
    )


@router.get("/{carbon_report_id}/emission-breakdown")
async def get_emission_breakdown(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return chart-ready emission breakdown for a carbon report.

    Serves both ModuleCarbonFootprintChart (module_breakdown +
    additional_breakdown) and CarbonFootPrintPerPersonChart
    (per_person_breakdown).
    """
    logger.info(
        f"GET emission breakdown: carbon_report_id={sanitize(carbon_report_id)}"
    )

    emission_rows = await DataEntryEmissionService(db).get_emission_breakdown(
        carbon_report_id=carbon_report_id,
    )

    fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id,
        aggregate_by="module_type_id",
    )
    total_fte = sum(fte_stats.values())

    result = await db.execute(
        select(
            CarbonReportModule.module_type_id,
            CarbonReportModule.status,
        ).where(
            CarbonReportModule.carbon_report_id == carbon_report_id,
        )
    )
    module_statuses = {row[0]: row[1] for row in result.all()}
    headcount_validated = (
        module_statuses.get(ModuleTypeEnum.headcount.value) == ModuleStatus.VALIDATED
    )
    validated_module_type_ids = {
        mid
        for mid, status in module_statuses.items()
        if status == ModuleStatus.VALIDATED
    }

    return build_chart_breakdown(
        rows=emission_rows,
        total_fte=total_fte,
        headcount_validated=headcount_validated,
        validated_module_type_ids=validated_module_type_ids,
    )
