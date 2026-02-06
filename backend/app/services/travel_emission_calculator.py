"""Service for calculating travel-related emissions."""

from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import Location
from app.repositories.factor_repo import FactorRepository
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
)

logger = get_logger(__name__)


class TravelEmissionCalculator:
    """Calculator for travel emissions (flights, trains)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.factor_repo = FactorRepository(session)

    async def calculate_flight_emission(
        self,
        origin_loc: Location,
        dest_loc: Location,
        number_of_trips: int = 1,
    ) -> dict:
        """
        Calculate flight emissions based on origin/destination locations.

        Returns dict with:
            - distance_km: calculated distance
            - category: haul category (short/medium/long)
            - primary_factor_id: the factor ID used
            - kg_co2eq: calculated emissions

        Raises ValueError if no factor found for the haul category.
        """
        distance_km = calculate_plane_distance(origin_loc, dest_loc)
        category = get_haul_category(distance_km)

        factor = await self.factor_repo.get_flight_factor(category)
        if not factor:
            raise ValueError(f"No flight factor found for category: {category}")

        impact_score = factor.values.get("impact_score", 0)
        rfi_adjustment = factor.values.get("rfi_adjustment", 1)
        kg_co2eq = distance_km * impact_score * rfi_adjustment * number_of_trips

        logger.debug(
            f"Flight: {distance_km}km × {impact_score} × {rfi_adjustment} "
            f"× {number_of_trips} = {kg_co2eq:.2f} kg CO2eq"
        )

        return {
            "distance_km": distance_km,
            "category": category,
            "primary_factor_id": factor.id,
            "kg_co2eq": round(kg_co2eq, 2),
        }

    async def calculate_train_emission(
        self,
        origin_loc: Location,
        dest_loc: Location,
        number_of_trips: int = 1,
    ) -> dict:
        """
        Calculate train emissions based on origin/destination locations.

        Returns dict with:
            - distance_km: calculated distance
            - countrycode: destination country code
            - primary_factor_id: the factor ID used
            - kg_co2eq: calculated emissions

        Raises ValueError if no factor found for the country.
        """
        distance_km = calculate_train_distance(origin_loc, dest_loc)
        dest_country = dest_loc.countrycode or "RoW"

        factor = await self.factor_repo.get_train_factor(dest_country)
        if not factor:
            raise ValueError(f"No train factor found for country: {dest_country}")

        impact_score = factor.values.get("impact_score", 0)
        kg_co2eq = distance_km * impact_score * number_of_trips

        logger.debug(
            f"Train ({dest_country}): {distance_km}km × {impact_score} "
            f"× {number_of_trips} = {kg_co2eq:.2f} kg CO2eq"
        )

        return {
            "distance_km": distance_km,
            "countrycode": dest_country,
            "primary_factor_id": factor.id,
            "kg_co2eq": round(kg_co2eq, 2),
        }

    async def resolve_travel_emission(
        self,
        origin_location_id: Optional[int],
        destination_location_id: Optional[int],
        transport_mode: Optional[str],
        number_of_trips: int = 1,
    ) -> dict:
        """
        Resolve travel emission data including location lookups.

        Returns dict with emission data to merge into payload:
            - origin: origin location name (if found)
            - destination: destination location name (if found)
            - distance_km, category/countrycode, primary_factor_id, kg_co2eq
        """
        result = {}

        # Look up locations
        origin_loc = (
            await self.session.get(Location, origin_location_id)
            if origin_location_id
            else None
        )
        dest_loc = (
            await self.session.get(Location, destination_location_id)
            if destination_location_id
            else None
        )

        # Store location names
        if origin_loc:
            result["origin"] = origin_loc.name
        if dest_loc:
            result["destination"] = dest_loc.name

        # Calculate distance and emissions if we have both locations and mode
        if origin_loc and dest_loc and transport_mode:
            try:
                if transport_mode == "flight":
                    emission_data = await self.calculate_flight_emission(
                        origin_loc, dest_loc, number_of_trips
                    )
                    result.update(emission_data)
                elif transport_mode == "train":
                    emission_data = await self.calculate_train_emission(
                        origin_loc, dest_loc, number_of_trips
                    )
                    result.update(emission_data)
            except Exception as e:
                logger.error(f"Error calculating travel emissions: {e}")

        return result
