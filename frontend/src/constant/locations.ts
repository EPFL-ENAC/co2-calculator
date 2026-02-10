/**
 * Location type definitions for train stations and airports.
 * These types match the backend Location model and LocationRead API response.
 */

/**
 * Transport mode type for locations.
 */
export type TransportMode = 'train' | 'plane';

/**
 * Location interface matching the backend LocationRead model.
 * Represents a train station or airport with geographic coordinates.
 */
export interface Location {
  /** Unique identifier for the location */
  id: number;

  /** Transport mode: 'train' or 'plane' */
  transport_mode: TransportMode;

  /** Location name (e.g., 'Lyndhurst Halt', 'Utirik Airport') */
  name: string;

  /** Latitude coordinate in decimal degrees */
  latitude: number;

  /** Longitude coordinate in decimal degrees */
  longitude: number;

  /** IATA airport code (e.g., 'UTK', 'OCA') - only for planes */
  iata_code: string | null;

  /** ISO country code (e.g., 'AE', 'AL', 'AM') */
  countrycode: string | null;

  /** Timestamp when the location was created */
  created_at: string;

  /** Timestamp when the location was last updated */
  updated_at: string;
}

/**
 * Search parameters for location search API endpoint.
 */
export interface LocationSearchParams {
  /** Search query string (minimum 2 characters) */
  query: string;

  /** Maximum number of results to return (default: 5, max: 20) */
  limit?: number;

  /** Filter by transport mode. If not provided, returns both types */
  transport_mode?: TransportMode;
}

/**
 * Response type for location search API endpoint.
 */
export type LocationSearchResponse = Location[];

/**
 * Response type for airport search - locations with transport_mode 'plane'.
 */
export type AirportResponse = Location;

/**
 * Response type for railway station search - locations with transport_mode 'train'.
 */
export type RailwayStationResponse = Location;
