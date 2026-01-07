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
    transport_mode: 'plane',
  });

  if (limit !== undefined) {
    params.append('limit', limit.toString());
  }

  const res = await api
    .get(`locations/search?${params.toString()}`)
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
    transport_mode: 'train',
  });

  if (limit !== undefined) {
    params.append('limit', limit.toString());
  }

  const res = await api
    .get(`locations/search?${params.toString()}`)
    .json<RailwayStationResponse[]>();
  return res;
}

/**
 * Generic search for locations (airports or railway stations).
 * Maps 'flight' to 'plane' for API compatibility.
 *
 * @param query - Search query string (minimum 2 characters)
 * @param transportMode - Transport mode: 'flight' (maps to 'plane') or 'train'
 * @param limit - Maximum number of results to return (default: 5, max: 20)
 * @returns Promise resolving to an array of locations
 */
export async function searchLocations(
  query: string,
  transportMode: 'flight' | 'train',
  limit?: number,
): Promise<Location[]> {
  // Map 'flight' to 'plane' for API
  const apiTransportMode: TransportMode =
    transportMode === 'flight' ? 'plane' : 'train';

  const params = new URLSearchParams({
    query: query.trim(),
    transport_mode: apiTransportMode,
  });

  if (limit !== undefined) {
    params.append('limit', limit.toString());
  }

  const res = await api
    .get(`locations/search?${params.toString()}`)
    .json<Location[]>();
  return res;
}

/**
 * Calculate distance between two locations based on transport mode.
 *
 * For flights: Haversine distance + 95 km (airport approaches, routing, taxiing)
 * For trains: Haversine distance × 1.2 (track routing, curves, detours)
 *
 * @param originLocationId - Origin location ID
 * @param destinationLocationId - Destination location ID
 * @param transportMode - Transport mode: 'flight' or 'train'
 * @returns Promise resolving to distance in kilometers
 */
export async function calculateDistance(
  originLocationId: number,
  destinationLocationId: number,
  transportMode: 'flight' | 'train',
): Promise<number> {
  const params = new URLSearchParams({
    origin_location_id: originLocationId.toString(),
    destination_location_id: destinationLocationId.toString(),
    transport_mode: transportMode,
  });

  const res = await api
    .get(`locations/calculate-distance?${params.toString()}`)
    .json<{ distance_km: number }>();
  return res.distance_km;
}
