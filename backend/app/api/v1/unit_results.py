"""Unit Results API endpoints."""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import require_unit_access
from app.models.unit import Unit
from app.models.user import User
from app.services.unit_totals_service import UnitTotalsService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}/{year}/totals", response_model=dict)
async def get_unit_totals(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total carbon footprint metrics for a unit across all modules.

    Returns:
        Dict with:
        - total_kg_co2eq: Total carbon footprint in kg CO2eq
        - total_tonnes_co2eq: Total carbon footprint in tonnes CO2eq
        - total_fte: Total FTE count
        - kg_co2eq_per_fte: Carbon footprint per FTE
        - previous_year_total_kg_co2eq: Previous year's total (if available)
        - previous_year_total_tonnes_co2eq: Previous year's total in tonnes
        - year_comparison_percentage: Percentage change from previous year
    """
    logger.info(f"GET unit totals: unit_id={sanitize(unit_id)}, year={sanitize(year)}")

    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)

    service = UnitTotalsService(db)
    totals = await service.get_unit_totals(
        unit_id=unit_id, year=year, user=current_user
    )

    return totals


@router.get("/{unit_id}/yearly-validated-emissions")
async def get_validated_emissions(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Get validated emission totals per year for a unit.

    Returns:
        [{"year": 2023, "total_tonnes_co2eq": 61.7}, ...]
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    rows = await UnitTotalsService(db).get_validated_emissions_by_unit(unit_id=unit_id)
    return [
        {
            "year": row["year"],
            "total_tonnes_co2eq": row["kg_co2eq"] / 1000.0,
        }
        for row in rows
    ]
