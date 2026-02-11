"""Location API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.location import LocationRead, TransportModeEnum
from app.models.user import User
from app.services.location_service import LocationService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/search", response_model=List[LocationRead])
async def search_locations(
    query: str = Query(
        ...,
        min_length=2,
        description="Search query string (minimum 2 characters)",
    ),
    limit: int = Query(
        5,
        ge=1,
        le=20,
        description="Maximum number of results to return (default: 5, max: 20)",
    ),
    transport_mode: Optional[TransportModeEnum] = Query(
        None,
        description=(
            "Filter by transport mode: 'train' or 'plane'. "
            "If not provided, returns both types."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Search locations by name with relevance ordering.

    Results are ordered by relevance:
    1. Exact matches (name = query)
    2. Starts with query (name ILIKE 'query%')
    3. Contains query (name ILIKE '%query%')

    Args:
        query: Search query string (minimum 2 characters)
        limit: Maximum number of results (default: 5, max: 20)
        transport_mode: Filter by transport mode ('train' or 'plane').
            If None, returns both types.
        db: Database session
        current_user: Authenticated user

    Returns:
        List of LocationRead DTOs ordered by relevance
    """
    if transport_mode is None:
        logger.warning(
            "Search locations without transport_mode filter",
            extra={
                "user_id": current_user.id,
                "query": sanitize(query),
                "limit": limit,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transport_mode must be either 'train' or 'plane'",
        )
    service = LocationService(db)
    locations = await service.search_locations(
        query=query,
        limit=limit,
        transport_mode=transport_mode,
    )

    logger.info(
        "User searched locations",
        extra={
            "user_id": current_user.id,
            "query": sanitize(query),
            "transport_mode": transport_mode,
            "limit": limit,
            "count": len(locations),
        },
    )

    return locations


@router.get("/calculate-distance")
async def calculate_distance(
    origin_location_id: int = Query(..., description="Origin location ID"),
    destination_location_id: int = Query(..., description="Destination location ID"),
    transport_mode: TransportModeEnum = Query(
        ...,
        description="Transport mode: 'plane' or 'train'",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calculate distance between two locations based on transport mode.

    For flights: Haversine distance + 95 km (airport approaches, routing, taxiing)
    For trains: Haversine distance × 1.2 (track routing, curves, detours)

    Args:
        origin_location_id: Origin location ID
        destination_location_id: Destination location ID
        transport_mode: 'plane' or 'train'
        db: Database session
        current_user: Authenticated user

    Returns:
        Dictionary with distance_km in kilometers

    Raises:
        HTTPException 404: If location not found
        HTTPException 400: If transport_mode is invalid or coordinates are invalid
    """
    service = LocationService(db)
    result = await service.calculate_distance(
        origin_location_id=origin_location_id,
        destination_location_id=destination_location_id,
        transport_mode=transport_mode,
    )

    logger.info(
        "Distance calculated",
        extra={
            "user_id": current_user.id,
            "origin_location_id": origin_location_id,
            "destination_location_id": destination_location_id,
            "transport_mode": transport_mode,
            "distance_km": result["distance_km"],
        },
    )

    return result
