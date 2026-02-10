"""Unit Results API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User
from app.services.unit_totals_service import UnitTotalsService

logger = get_logger(__name__)
router = APIRouter()


unit_results = {
    "id": 12345,
    "name": "ENAC-IT4R",
    "updated_at": "2024-11-20T12:34:56Z",
    "years": [
        {
            "year": 2024,
            "completed_modules": 5,
            "kgco2": 41700,
            "last_year_comparison": -11.3,
            "report": "https://report.epfl.ch/enac-it4r/2024",
        },
        {
            "year": 2023,
            "completed_modules": 5,
            "kgco2": 51200,
            "last_year_comparison": 11.3,
            "report": "https://report.epfl.ch/enac-it4r/2023",
        },
        {
            "year": 2022,
            "completed_modules": 3,
            "kgco2": 38400,
            "report": "https://report.epfl.ch/enac-it4r/2022",
        },
    ],
}


@router.get("/{unit_id}/results", response_model=dict)
async def get_unit_results(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return unit_results


@router.get("/{unit_id}/{year}/totals", response_model=dict)
async def get_unit_totals(
    unit_id: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get total carbon footprint metrics for a unit across all modules.

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

    service = UnitTotalsService(db)
    totals = await service.get_unit_totals(
        unit_id=unit_id, year=year, user=current_user
    )

    return totals
