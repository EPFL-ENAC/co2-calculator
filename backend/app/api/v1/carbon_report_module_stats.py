"""Module stats API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.schemas.carbon_report import CarbonReportModuleRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{carbon_report_id}/validated-totals")
async def get_validated_totals(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Get validated totals for a carbon report.

    Aggregates emissions (kg → tonnes CO2eq) and FTE across all validated
    modules in the given carbon report. Both are keyed by module_type_id so
    headcount appears with total_fte while other modules show total_tonnes_co2eq.

    Returns:
        {
            "modules": [
                {"module_type_id": 1, "total_fte": 25.5},
                {"module_type_id": 2, "total_tonnes_co2eq": 15.0},
                {"module_type_id": 4, "total_tonnes_co2eq": 41.7},
                {"module_type_id": 7, "total_tonnes_co2eq": 5.0}
            ],
            "total_tonnes_co2eq": 61.7,
            "total_fte": 25.5
        }
    """
    logger.info(f"GET validated totals: carbon_report_id={sanitize(carbon_report_id)}")

    # Emission totals per module (kg_co2eq grouped by module_type_id)
    emission_stats = await DataEntryEmissionService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id
    )

    # FTE totals grouped by module_type_id (only headcount modules have FTE)
    fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id,
    )

    # Collect all module_type_ids from both queries
    all_module_ids = set(emission_stats.keys()) | set(fte_stats.keys())

    modules = []
    for module_type_id in sorted(all_module_ids, key=int):
        entry: dict = {"module_type_id": int(module_type_id)}
        if module_type_id in emission_stats:
            entry["total_tonnes_co2eq"] = round(
                emission_stats[module_type_id] / 1000.0, 2
            )
        if module_type_id in fte_stats:
            entry["total_fte"] = round(fte_stats[module_type_id], 2)
        modules.append(entry)

    total_tonnes_co2eq = round(sum(kg / 1000.0 for kg in emission_stats.values()), 2)
    total_fte = round(sum(fte_stats.values()), 2)

    return {
        "modules": modules,
        "total_tonnes_co2eq": total_tonnes_co2eq,
        "total_fte": total_fte,
    }


@router.get("/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, float])
async def get_module_stats(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, float]:
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

    stats: dict[str, float] = {}
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
