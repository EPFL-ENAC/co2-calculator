"""Unit Results API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.policy import require_unit_access
from app.models.unit import Unit
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
    unit_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    return unit_results


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
