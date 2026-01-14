"""Location service for business logic."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import Location, LocationRead
from app.repositories.location_repo import LocationRepository
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
)

logger = get_logger(__name__)


class LocationService:
    """Service for location business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LocationRepository(session)

    async def search_locations(
        self,
        query: str,
        limit: int = 20,
        transport_mode: Optional[str] = None,
    ) -> List[LocationRead]:
        """
        Search locations by name with relevance ordering.

        Args:
            query: Search query string
            limit: Maximum number of results
            transport_mode: Filter by transport mode ('train' or 'plane')

        Returns:
            List of LocationRead DTOs ordered by relevance

        Raises:
            HTTPException 400: If transport_mode is invalid or query is too short
        """
        # Validate transport_mode if provided
        if transport_mode and transport_mode not in ["train", "plane"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="transport_mode must be either 'train' or 'plane'",
            )

        # Normalize and validate query
        query = query.strip()
        if len(query) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query must be at least 2 characters long",
            )

        # Search via repository
        locations = await self.repo.search_location(
            query=query,
            limit=limit,
            transport_mode=transport_mode,
        )

        # Convert to DTOs
        return [LocationRead.model_validate(location) for location in locations]

    async def get_location_by_id(self, location_id: int) -> Optional[Location]:
        """
        Get location by ID.

        Args:
            location_id: Location ID

        Returns:
            Location if found, None otherwise
        """
        return await self.repo.get_by_id(location_id)

    async def calculate_distance(
        self,
        origin_location_id: int,
        destination_location_id: int,
        transport_mode: str,
    ) -> dict[str, float]:
        """
        Calculate distance between two locations based on transport mode.

        For flights: Haversine distance + 95 km (airport approaches, routing, taxiing)
        For trains: Haversine distance × 1.2 (track routing, curves, detours)

        Args:
            origin_location_id: Origin location ID
            destination_location_id: Destination location ID
            transport_mode: 'flight' or 'train'

        Returns:
            Dict with distance_km in kilometers

        Raises:
            HTTPException 400: If transport_mode is invalid or coordinates are invalid
            HTTPException 404: If location not found
        """
        # Validate transport_mode
        if transport_mode not in ["flight", "train"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="transport_mode must be either 'flight' or 'train'",
            )

        # Fetch locations
        origin_location = await self.repo.get_by_id(origin_location_id)
        if not origin_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Origin location with ID {origin_location_id} not found",
            )

        destination_location = await self.repo.get_by_id(destination_location_id)
        if not destination_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Destination location with ID {destination_location_id} not found"
                ),
            )

        # Validate and correct coordinates
        origin_lat, origin_lon = self._validate_and_correct_coordinates(
            origin_location, "origin"
        )
        dest_lat, dest_lon = self._validate_and_correct_coordinates(
            destination_location, "destination"
        )

        # Create corrected location objects
        origin_corrected = Location(
            id=origin_location.id,
            name=origin_location.name,
            transport_mode=origin_location.transport_mode,
            latitude=origin_lat,
            longitude=origin_lon,
        )
        dest_corrected = Location(
            id=destination_location.id,
            name=destination_location.name,
            transport_mode=destination_location.transport_mode,
            latitude=dest_lat,
            longitude=dest_lon,
        )

        # Calculate distance
        try:
            if transport_mode == "flight":
                distance_km = calculate_plane_distance(origin_corrected, dest_corrected)
            else:  # train
                distance_km = calculate_train_distance(origin_corrected, dest_corrected)
        except ValueError as e:
            logger.error(
                "Distance calculation failed",
                extra={
                    "error": str(e),
                    "origin_location_id": origin_location_id,
                    "destination_location_id": destination_location_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Distance calculation failed: {str(e)}",
            )

        return {"distance_km": round(distance_km, 2)}

    def _validate_and_correct_coordinates(
        self, location: Location, location_type: str
    ) -> tuple[float, float]:
        """
        Validate and correct coordinates for a location.

        Checks if coordinates are swapped (common data issue) and corrects them.

        Args:
            location: Location object to validate
            location_type: Type of location ('origin' or 'destination')
                for error messages

        Returns:
            Tuple of (corrected_latitude, corrected_longitude)

        Raises:
            HTTPException 400: If coordinates are invalid
        """
        lat = location.latitude
        lon = location.longitude

        # Check for swapped coordinates (lat in lon field or vice versa)
        if not (-90 <= lat <= 90):
            if -180 <= lat <= 180 and -90 <= lon <= 90:
                # Coordinates appear swapped
                logger.warning(
                    f"{location_type.capitalize()} coordinates appear swapped",
                    extra={
                        "location_id": location.id,
                        "location_name": location.name,
                        "stored_lat": lat,
                        "stored_lon": lon,
                    },
                )
                # Swap them for calculation
                lat, lon = lon, lat
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid {location_type} coordinates: "
                        f"lat={location.latitude}, lon={location.longitude}. "
                        "Latitude must be between -90 and 90, "
                        "longitude between -180 and 180."
                    ),
                )

        if not (-180 <= lon <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid {location_type} longitude: {location.longitude}. "
                    "Must be between -180 and 180 degrees."
                ),
            )

        return lat, lon
