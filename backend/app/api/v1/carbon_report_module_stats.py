"""Unit Results API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.user import User
from app.services import equipment_service
from app.services.headcount_service import HeadcountService
from app.services.professional_travel_service import ProfessionalTravelService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}/{year}/totals", response_model=dict[str, float])
async def get_module_totals(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, float]:
    """
    Get total tCO2eq for equipment-electric-consumption and professional-travel modules.

    Args:
        unit_id: Unit ID
        year: Year for the data
        db: Database session
        current_user: Authenticated user
    """
    logger.info(
        f"GET module totals: unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    totals: dict[str, float] = {
        "total": 0.0,
        "equipment-electric-consumption": 0.0,
        "professional-travel": 0.0,
    }

    # Get equipment module totals
    try:
        await _check_module_permission(
            current_user, "equipment-electric-consumption", "view"
        )
        equipment_kg_co2eq = await equipment_service.get_total_kg_co2eq(
            session=db, unit_id=unit_id, year=year
        )
        equipment_tco2eq = round(float(equipment_kg_co2eq or 0.0) / 1000.0, 2)
        totals["equipment-electric-consumption"] = equipment_tco2eq
        logger.info(
            f"Equipment module totals: {equipment_kg_co2eq} kg CO2eq = "
            f"{equipment_tco2eq} tCO2eq for unit_id={sanitize(unit_id)}"
        )
    except HTTPException:
        # Permission denied, skip this module
        logger.warning("Permission denied for equipment module")
    except Exception as e:
        logger.error(f"Error getting equipment stats: {e}", exc_info=True)

    # Get professional travel module totals
    try:
        await _check_module_permission(current_user, "professional-travel", "view")
        travel_service = ProfessionalTravelService(db)
        travel_stats = await travel_service.get_module_stats(
            unit_id=unit_id, year=year, user=current_user
        )
        travel_kg_co2eq = travel_stats.get("total_kg_co2eq", 0.0)
        travel_tco2eq = round(float(travel_kg_co2eq or 0.0) / 1000.0, 2)
        totals["professional-travel"] = travel_tco2eq
        logger.debug(f"Professional Travel module: {travel_tco2eq} tCO2eq")
    except HTTPException:
        # Permission denied, skip this module
        logger.warning("Permission denied for professional travel module")
    except Exception as e:
        logger.error(f"Error getting professional travel stats: {e}", exc_info=True)

    # Calculate total
    totals["total"] = round(
        totals["equipment-electric-consumption"] + totals["professional-travel"], 2
    )

    logger.info(
        f"Module totals returned: total={totals['total']} tCO2eq "
        f"(equipment: {totals['equipment-electric-consumption']}, "
        f"travel: {totals['professional-travel']})"
    )

    return totals


@router.get("/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, float])
async def get_module_stats(
    unit_id: int,
    year: int,
    module_id: str,
    aggregate_by: str = Query(default="submodule", description="Aggregate by field"),
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
        List of integers with statistics (e.g., total items, total submodules)
    """
    await _check_module_permission(current_user, module_id, "view")

    logger.info(
        f"GET module stats: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    stats: dict[str, float] = {}
    if module_id == "equipment-electric-consumption":
        stats = await equipment_service.get_module_stats(
            session=db,
            unit_id=unit_id,
            aggregate_by=aggregate_by,
        )
    elif module_id == "my-lab":
        stats = await HeadcountService(db).get_module_stats(
            unit_id=unit_id,
            year=year,
            aggregate_by=aggregate_by,
        )
    elif module_id == "professional-travel":
        # Get summary stats for professional travel
        summary = await ProfessionalTravelService(db).get_module_stats(
            unit_id=unit_id, year=year, user=current_user
        )
        stats = {
            "total_items": float(summary["total_items"]),
            "total_kg_co2eq": summary["total_kg_co2eq"],
            "total_distance_km": summary["total_distance_km"],
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {module_id} not found",
        )
    logger.info(f"Module stats returned: {stats}")

    return stats
