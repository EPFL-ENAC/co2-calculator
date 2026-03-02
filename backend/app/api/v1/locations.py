"""Location API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.location import LocationRead, TransportModeEnum
from app.models.user import User
from app.services.location_service import LocationService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/search/plane", response_model=List[LocationRead])
async def search_plane_locations(
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = LocationService(db)
    locations = await service.search_locations(
        query=query,
        mode=TransportModeEnum.plane,
        limit=limit,
    )
    logger.info(
        "User searched plane locations",
        extra={
            "user_id": current_user.id,
            "query": sanitize(query),
            "limit": limit,
            "count": len(locations),
        },
    )
    return locations


@router.get("/search/train", response_model=List[LocationRead])
async def search_train_locations(
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = LocationService(db)
    locations = await service.search_locations(
        query=query,
        mode=TransportModeEnum.train,
        limit=limit,
    )
    logger.info(
        "User searched train locations",
        extra={
            "user_id": current_user.id,
            "query": sanitize(query),
            "limit": limit,
            "count": len(locations),
        },
    )
    return locations


@router.get("/calculate-distance/plane")
async def calculate_plane_distance(
    origin_location_id: int = Query(..., description="Origin location ID"),
    destination_location_id: int = Query(..., description="Destination location ID"),
    number_of_trips: int = Query(
        1,
        ge=1,
        description="Number of trips (default: 1).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = LocationService(db)
    result = await service.calculate_distance(
        origin_location_id=origin_location_id,
        destination_location_id=destination_location_id,
        mode=TransportModeEnum.plane,
        number_of_trips=number_of_trips,
    )
    logger.info(
        "Plane distance calculated",
        extra={
            "user_id": current_user.id,
            "origin_location_id": origin_location_id,
            "destination_location_id": destination_location_id,
            "number_of_trips": number_of_trips,
            "distance_km": result["distance_km"],
        },
    )
    return result


@router.get("/calculate-distance/train")
async def calculate_train_distance(
    origin_location_id: int = Query(..., description="Origin location ID"),
    destination_location_id: int = Query(..., description="Destination location ID"),
    number_of_trips: int = Query(
        1,
        ge=1,
        description="Number of trips (default: 1).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = LocationService(db)
    result = await service.calculate_distance(
        origin_location_id=origin_location_id,
        destination_location_id=destination_location_id,
        mode=TransportModeEnum.train,
        number_of_trips=number_of_trips,
    )
    logger.info(
        "Train distance calculated",
        extra={
            "user_id": current_user.id,
            "origin_location_id": origin_location_id,
            "destination_location_id": destination_location_id,
            "number_of_trips": number_of_trips,
            "distance_km": result["distance_km"],
        },
    )
    return result
