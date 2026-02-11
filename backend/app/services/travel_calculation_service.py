"""Travel calculation service for CO2 emissions.

This service calculates CO2 emissions for plane and train travel based on:
- Distance calculations (Haversine formula with adjustments)
- Haul categories (for planes) or country factors (for trains)
- Impact scores and RFI adjustments from database
- Class multipliers for different travel classes
"""

from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import Location
from app.models.travel_impact_factor import PlaneImpactFactor, TrainImpactFactor
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
)

logger = get_logger(__name__)


class TravelCalculationService:
    """Service for calculating travel emissions."""

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session."""
        self.session = session

    async def calculate_plane_emissions(
        self,
        origin_airport: Location,
        dest_airport: Location,
        class_: Optional[str],
        number_of_trips: int = 1,
    ) -> Tuple[float, float]:
        """
        Calculate plane travel emissions.

        Formula:
        kg_CO₂-eq = (Haversine distance + 95km) × Impact_Score × RFI_adjustment
                    × number_of_trips

        Args:
            origin_airport: Origin airport Location object
            dest_airport: Destination airport Location object
            class_: Travel class (eco, eco_plus, business, first) or None
                (not used in calculation, kept for API compatibility)
            number_of_trips: Number of trips (default: 1)

        Returns:
            Tuple of (distance_km, kg_co2eq)

        Raises:
            HTTPException: If impact factor not found for haul category
        """
        # 1. Calculate distance (Haversine + 95km)
        distance_km = calculate_plane_distance(origin_airport, dest_airport)

        # 2. Determine haul category
        haul_category = get_haul_category(distance_km)

        # 3. Get impact_score and RFI_adjustment from factor table
        statement = select(PlaneImpactFactor).where(
            col(PlaneImpactFactor.category) == haul_category,
            col(PlaneImpactFactor.valid_to).is_(None),  # Current/active factors only
        )
        result = await self.session.execute(statement)
        impact_factor = result.scalar_one_or_none()

        if not impact_factor:
            logger.error(f"Plane impact factor not found for category: {haul_category}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Impact factor not found for haul category: {haul_category}",
            )

        impact_score = impact_factor.impact_score
        rfi_adjustment = impact_factor.rfi_adjustment

        # 4. Calculate CO2 emissions
        # Formula: distance × impact_score × rfi_adjustment × number_of_trips
        kg_co2eq = distance_km * impact_score * rfi_adjustment * number_of_trips

        logger.debug(
            f"Plane emissions calculated: distance={distance_km:.2f}km, "
            f"category={haul_category}, impact_score={impact_score}, "
            f"rfi={rfi_adjustment}, class={class_}, "
            f"trips={number_of_trips}, kg_co2eq={kg_co2eq:.2f}"
        )

        return (distance_km, kg_co2eq)

    async def calculate_train_emissions(
        self,
        origin_station: Location,
        dest_station: Location,
        class_: Optional[str],
        number_of_trips: int = 1,
    ) -> Tuple[float, float]:
        """
        Calculate train travel emissions.

        Formula:
        kg_CO₂-eq = (Haversine distance × 1.2) × Impact_Score × number_of_trips

        Geography rules:
        1. Use CH factor only if BOTH origin AND destination are in CH
        2. Otherwise, prefer the destination country if it's a valid non-CH
           country, then fall back to origin country if it's a valid non-CH
           country, otherwise use RoW
        3. If country not in table → use RoW (Rest of World)

        Args:
            origin_station: Origin station Location object
            dest_station: Destination station Location object
            class_: Travel class (class_1, class_2) or None
                (not used in calculation, kept for API compatibility)
            number_of_trips: Number of trips (default: 1)

        Returns:
            Tuple of (distance_km, kg_co2eq)

        Raises:
            HTTPException: If impact factor not found for country
        """
        # 1. Calculate distance (Haversine × 1.2)
        distance_km = calculate_train_distance(origin_station, dest_station)

        # 2. Determine country factor to use
        # Rule: Use CH factor only if BOTH origin AND destination are in CH
        # Otherwise, prefer the non-CH country's factor (or RoW as fallback)
        origin_country = origin_station.countrycode
        dest_country = dest_station.countrycode

        if origin_country == "CH" and dest_country == "CH":
            countrycode = "CH"
        else:
            # Prefer destination if it's a valid non-CH country, otherwise use origin;
            # if neither side is a valid non-CH country, fall back to RoW.
            if dest_country and dest_country != "CH":
                countrycode = dest_country
            elif origin_country and origin_country != "CH":
                countrycode = origin_country
            else:
                countrycode = "RoW"

        # 3. Get impact_score from factor table
        statement = select(TrainImpactFactor).where(
            col(TrainImpactFactor.countrycode) == countrycode,
            col(TrainImpactFactor.valid_to).is_(None),  # Current/active factors only
        )
        result = await self.session.execute(statement)
        impact_factor = result.scalar_one_or_none()

        # If country not found, try RoW as fallback
        if not impact_factor and countrycode != "RoW":
            logger.warning(
                f"Train impact factor not found for country: {countrycode}, "
                "trying RoW as fallback"
            )
            statement = select(TrainImpactFactor).where(
                col(TrainImpactFactor.countrycode) == "RoW",
                col(TrainImpactFactor.valid_to).is_(None),
            )
            result = await self.session.execute(statement)
            impact_factor = result.scalar_one_or_none()
            countrycode = "RoW"

        if not impact_factor:
            logger.error(f"Train impact factor not found for country: {countrycode}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Impact factor not found for country: {countrycode}",
            )

        impact_score = impact_factor.impact_score

        # 5. Calculate CO2 emissions
        # Formula: distance × impact_score × number_of_trips
        kg_co2eq = distance_km * impact_score * number_of_trips

        logger.debug(
            f"Train emissions calculated: distance={distance_km:.2f}km, "
            f"origin_country={origin_country}, dest_country={dest_country}, "
            f"used_country={countrycode}, impact_score={impact_score}, "
            f"class={class_}, trips={number_of_trips}, kg_co2eq={kg_co2eq:.2f}"
        )

        return (distance_km, kg_co2eq)
