"""Professional Travel API endpoints."""

from typing import Any, List

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User
from app.services.professional_travel_service import ProfessionalTravelService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}/evolution-over-time")
async def get_professional_travel_evolution_over_time(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[dict[str, Any]]:
    """
    Get professional travel statistics aggregated by year and transport mode.

    Args:
        unit_id: Unit ID to filter data
        db: Database session
        current_user: Authenticated user

    Returns:
        List of dicts with year, transport_mode, and kg_co2eq:
        [
            {"year": 2020, "transport_mode": "flight", "kg_co2eq": 15000.0},
            {"year": 2020, "transport_mode": "train", "kg_co2eq": 8000.0},
            ...
        ]
    """
    logger.info(
        f"GET professional travel evolution over time: unit_id={sanitize(unit_id)}"
    )

    stats = await ProfessionalTravelService(db).get_evolution_over_time(
        unit_id=unit_id, user=current_user
    )
    logger.info(
        f"Professional travel evolution over time returned: {len(stats)} data points"
    )

    return stats


@router.get("/{unit_id}/{year}/stats-by-class")
async def get_professional_travel_stats_by_class(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[dict[str, Any]]:
    """
    Get professional travel statistics aggregated by transport mode and class.

    Args:
        unit_id: Unit ID to filter data
        year: Year for the data
        db: Database session
        current_user: Authenticated user

    Returns:
        List of dicts in treemap format with hierarchical structure
    """
    logger.info(
        f"GET professional travel stats by class: "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    stats = await ProfessionalTravelService(db).get_stats_by_class(
        unit_id=unit_id, year=year, user=current_user
    )
    logger.info(f"Professional travel stats by class returned: {len(stats)} categories")

    return stats
