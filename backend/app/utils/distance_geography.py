"""Distance and geography calculation utilities for travel emissions.

This module provides functions for calculating distances between locations
and determining travel categories based on distance.
"""

from typing import Optional

from haversine import Unit, haversine

from app.models.factor import Factor
from app.models.location import Location

FLIGHT_APPROACH_KM: int = 95
TRAIN_ROUTING_FACTOR: float = 1.2


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Calculate great circle distance between two points using Haversine formula.

    Uses the haversine library for accurate distance calculation.

    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point

    Returns:
        Distance in kilometers (int, rounded)

    Raises:
        ValueError: If coordinates are out of valid range
    """
    # Validate coordinate ranges
    if not (-90 <= lat1 <= 90) or not (-90 <= lat2 <= 90):
        raise ValueError(
            f"Invalid latitude: lat1={lat1}, lat2={lat2}. "
            "Latitude must be between -90 and 90 degrees."
        )
    if not (-180 <= lon1 <= 180) or not (-180 <= lon2 <= 180):
        raise ValueError(
            f"Invalid longitude: lon1={lon1}, lon2={lon2}. "
            "Longitude must be between -180 and 180 degrees."
        )

    point1 = (lat1, lon1)
    point2 = (lat2, lon2)
    distance_km = haversine(point1, point2, unit=Unit.KILOMETERS)
    return round(distance_km)


def calculate_plane_distance(origin_airport: Location, dest_airport: Location) -> int:
    """
    Calculate plane travel distance between two airports.

    Formula: Haversine distance + 95 km (to account for airport approaches,
    routing, and taxiing).

    Args:
        origin_airport: Origin airport Location object
        dest_airport: Destination airport Location object

    Returns:
        Adjusted distance in kilometers (int, rounded)
    """
    great_circle_distance = haversine_distance(
        origin_airport.latitude,
        origin_airport.longitude,
        dest_airport.latitude,
        dest_airport.longitude,
    )
    # Add 95 km for airport approaches, routing, and taxiing
    adjusted_distance = great_circle_distance + FLIGHT_APPROACH_KM
    return round(adjusted_distance)


def calculate_train_distance(origin_station: Location, dest_station: Location) -> int:
    """
    Calculate train travel distance between two stations.

    Formula: Haversine distance * 1.2 (to account for track routing,
    curves, and detours that trains take compared to straight-line distance).

    Args:
        origin_station: Origin station Location object
        dest_station: Destination station Location object

    Returns:
        Adjusted distance in kilometers (int, rounded)
    """
    great_circle_distance = haversine_distance(
        origin_station.latitude,
        origin_station.longitude,
        dest_station.latitude,
        dest_station.longitude,
    )
    # Multiply by 1.2 to account for track routing
    adjusted_distance = great_circle_distance * TRAIN_ROUTING_FACTOR
    return round(adjusted_distance)


def get_haul_category(distance_km: float) -> str:
    """
    Determine plane haul category based on distance.

    Categories:
        - very_short_haul: < 800 km
        - short_haul: 800-1500 km
        - medium_haul: 1500-4000 km
        - long_haul: > 4000 km

    Args:
        distance_km: Distance in kilometers (float)

    Returns:
        Haul category string: 'very_short_haul', 'short_haul',
        'medium_haul', or 'long_haul'
    """
    if distance_km < 800:
        return "very_short_haul"
    elif distance_km < 1500:
        return "short_haul"
    elif distance_km < 4000:
        return "medium_haul"
    else:
        return "long_haul"


def resolve_flight_factor(
    origin: Location,
    dest: Location,
    factors: list[Factor],
) -> tuple[int, Optional[Factor]]:
    """
    Compute flight distance and select the matching factor by haul category.

    Distance is an intermediary value: it determines the haul category,
    which in turn selects the correct factor from the candidates.

    Args:
        origin: Origin airport Location
        dest: Destination airport Location
        factors: Candidate flight factors (pre-filtered by kind='plane')

    Returns:
        Tuple of (distance_km, matched factor or None)
    """
    distance_km = calculate_plane_distance(origin, dest)
    category = get_haul_category(distance_km)
    factor = next(
        (f for f in factors if f.classification.get("category") == category),
        None,
    )
    return distance_km, factor


def _determine_train_countrycode(origin: Location, dest: Location) -> str:
    """
    Determine which country's impact factor to use for a train trip.

    Rule: Use CH factor only if BOTH origin AND destination are in Switzerland.
    Otherwise, prefer the non-CH country's factor (destination first, then origin).
    Falls back to 'RoW' if neither side has a usable non-CH country code.

    See issue #357 for the rationale behind this country selection logic.
    """
    origin_country = origin.country_code
    dest_country = dest.country_code

    if origin_country == "CH" and dest_country == "CH":
        return "CH"

    # Prefer destination if it's a valid non-CH country, otherwise use origin;
    # if neither side is a valid non-CH country, fall back to RoW.
    if dest_country and dest_country != "CH":
        return dest_country
    if origin_country and origin_country != "CH":
        return origin_country
    return "RoW"


def resolve_train_factor(
    origin: Location,
    dest: Location,
    factors: list[Factor],
) -> tuple[int, Optional[Factor]]:
    """
    Compute train distance and select the matching factor by country.

    Uses the country selection rule from issue #357: CH factor is used
    only when both origin and destination are in Switzerland. Otherwise,
    the non-CH country's factor is preferred (destination first, then
    origin), with 'RoW' as a final fallback.

    Args:
        origin: Origin station Location
        dest: Destination station Location
        factors: Candidate train factors (pre-filtered by kind='train')

    Returns:
        Tuple of (distance_km, matched factor or None)
    """
    DEFAULT_COUNTRY_CODE = "RoW"
    distance_km = calculate_train_distance(origin, dest)
    countrycode = _determine_train_countrycode(origin, dest)
    factor = next(
        (f for f in factors if f.classification.get("country_code") == countrycode),
        None,
    )
    if not factor:
        # Fallback to RoW
        factor = next(
            (
                f
                for f in factors
                if f.classification.get("country_code") == DEFAULT_COUNTRY_CODE
            ),
            None,
        )
    return distance_km, factor
