"""Module stats API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import get_settings
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.schemas.carbon_report import CarbonReportModuleRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.unit_totals_service import UnitTotalsService

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
            "modules": {1: 25.5, 2: 15.0, 4: 41.7, 7: 5.0},
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
        aggregate_by="module_type_id",
    )

    # Collect all module_type_ids from both queries
    all_module_ids = set(emission_stats.keys()) | set(fte_stats.keys())
    headcount_type_id = str(ModuleTypeEnum.headcount.value)

    modules: dict[int, float] = {}
    for module_type_id in sorted(all_module_ids, key=int):
        if module_type_id == headcount_type_id and module_type_id in fte_stats:
            modules[int(module_type_id)] = fte_stats[module_type_id]
        elif module_type_id in emission_stats:
            modules[int(module_type_id)] = emission_stats[module_type_id] / 1000.0

    total_tonnes_co2eq = sum(kg / 1000.0 for kg in emission_stats.values())
    total_fte = sum(fte_stats.values())

    return {
        "modules": modules,
        "total_tonnes_co2eq": total_tonnes_co2eq,
        "total_fte": total_fte,
    }


@router.get(
    "/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, float | None]
)
async def get_module_stats(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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

    current_emissions: dict[str, float | None] = raw["current_emissions"]
    current_fte: dict[str, float | None] = raw["current_fte"]
    prev_emissions: dict[str, float | None] = raw["prev_emissions"]

    # Total FTE from headcount module
    headcount_key = str(ModuleTypeEnum.headcount.value)
    total_fte = current_fte.get(headcount_key)

    # --- Per-module results (no rounding — frontend handles display) ---
    module_results: list[dict] = []
    for module_key, kg_co2eq in current_emissions.items():
        if kg_co2eq is None:
            continue
        total_tonnes = kg_co2eq / 1000
        tonnes_per_fte = (
            (total_tonnes / total_fte) if total_fte and total_fte > 0 else None
        )
        equivalent_car_km = kg_co2eq / get_settings().CO2_PER_KM_KG

        prev_kg = prev_emissions.get(module_key)
        prev_tonnes = prev_kg / 1000 if prev_kg is not None else None
        year_comparison = None
        if prev_kg is not None and prev_kg > 0:
            year_comparison = (kg_co2eq - prev_kg) / prev_kg * 100

        module_results.append(
            {
                "module_type_id": int(module_key),
                "total_tonnes_co2eq": total_tonnes,
                "total_fte": total_fte if module_key == headcount_key else None,
                "tonnes_co2eq_per_fte": tonnes_per_fte,
                "equivalent_car_km": equivalent_car_km,
                "previous_year_total_tonnes_co2eq": prev_tonnes,
                "year_comparison_percentage": year_comparison,
            }
        )

    # --- Unit totals (sum across all modules, no rounding) ---
    non_none_emissions = [v for v in current_emissions.values() if v is not None]
    non_none_prev = [v for v in prev_emissions.values() if v is not None]
    total_kg: float | None = sum(non_none_emissions) if non_none_emissions else None
    total_prev_kg: float | None = sum(non_none_prev) if non_none_prev else None
    total_tonnes_all = total_kg / 1000 if total_kg is not None else None
    total_tonnes_per_fte = (
        (total_tonnes_all / total_fte)
        if total_tonnes_all is not None and total_fte and total_fte > 0
        else None
    )
    total_car_km = (
        total_kg / get_settings().CO2_PER_KM_KG if total_kg is not None else None
    )
    total_year_comparison = None
    if total_prev_kg is not None and total_kg is not None and total_prev_kg > 0:
        total_year_comparison = (total_kg - total_prev_kg) / total_prev_kg * 100

    return {
        "unit_totals": {
            "total_tonnes_co2eq": total_tonnes_all,
            "total_fte": total_fte,
            "tonnes_co2eq_per_fte": total_tonnes_per_fte,
            "equivalent_car_km": total_car_km,
            "previous_year_total_tonnes_co2eq": (
                total_prev_kg / 1000 if total_prev_kg is not None else None
            ),
            "year_comparison_percentage": total_year_comparison,
        },
        "co2_per_km_kg": get_settings().CO2_PER_KM_KG,
        "module_results": module_results,
    }
