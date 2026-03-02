import { api } from 'src/api/http';

import type {
  AirportResponse,
  Location,
  RailwayStationResponse,
  TransportMode,
} from 'src/constant/locations';

/**
 * Search for airports by name.
 *
 * @param query - Search query string (minimum 2 characters)
 * @param limit - Maximum number of results to return (default: 5, max: 20)
 * @returns Promise resolving to an array of airports
 */
export async function searchAirports(
  query: string,
  limit?: number,
): Promise<AirportResponse[]> {
  const params = new URLSearchParams({
    query: query.trim(),
  });

  if (limit !== undefined) {
    params.append('limit', limit.toString());
  }

  const res = await api
    .get(`locations/search/plane?${params.toString()}`)
    .json<AirportResponse[]>();
  return res;
}

/**
 * Search for railway stations by name.
 *
 * @param query - Search query string (minimum 2 characters)
 * @param limit - Maximum number of results to return (default: 5, max: 20)
 * @returns Promise resolving to an array of railway stations
 */
export async function searchRailwayStations(
  query: string,
  limit?: number,
): Promise<RailwayStationResponse[]> {
  const params = new URLSearchParams({
    query: query.trim(),
  });

  if (limit !== undefined) {
    params.append('limit', limit.toString());
  }

  const res = await api
    .get(`locations/search/train?${params.toString()}`)
    .json<RailwayStationResponse[]>();
  return res;
}

/**
 * Generic search for locations (airports or railway stations).
 *
 * @param query - Search query string (minimum 2 characters)
 * @param transportMode - Transport mode: 'plane' or 'train'
 * @param limit - Maximum number of results to return (default: 5, max: 20)
 * @returns Promise resolving to an array of locations
 */
export async function searchLocations(
  query: string,
  transportMode: TransportMode,
  limit?: number,
): Promise<Location[]> {
  if (transportMode === 'plane') {
    return searchAirports(query, limit);
  }
  return searchRailwayStations(query, limit);
}

/**
 * Calculate distance between two locations.
 *
 * For planes: Haversine distance + 95 km (airport approaches, routing, taxiing)
 * For trains: Haversine distance × 1.2 (track routing, curves, detours)
 *
 * The returned distance is the total distance (per-trip distance × number_of_trips).
 *
 * @param originLocationId - Origin location ID
 * @param destinationLocationId - Destination location ID
 * @param numberOfTrips - Number of trips (default: 1)
 * @returns Promise resolving to total distance in kilometers
 */
export async function calculateDistance(
  originLocationId: number,
  destinationLocationId: number,
  transportMode: TransportMode,
  numberOfTrips: number = 1,
): Promise<number> {
  const params = new URLSearchParams({
    origin_location_id: originLocationId.toString(),
    destination_location_id: destinationLocationId.toString(),
    number_of_trips: numberOfTrips.toString(),
  });

  const res = await api
    .get(`locations/calculate-distance/${transportMode}?${params.toString()}`)
    .json<{ distance_km: number }>();
  return res.distance_km;
}
