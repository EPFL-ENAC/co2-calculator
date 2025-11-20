"""Unit Results API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()


unit_results = {
    "id": 12345,
    "name": "ENAC-IT4R",
    "updated_at": 1700000000,
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
