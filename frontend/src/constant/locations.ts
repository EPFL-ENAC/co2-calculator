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

  /** Location name (e.g., 'Lyndhurst Halt', 'Utirik Airport') */
  name: string;

  /** Latitude coordinate in decimal degrees */
  latitude: number;

  /** Longitude coordinate in decimal degrees */
  longitude: number;

  /** IATA airport code (e.g., 'UTK', 'OCA') - only for planes */
  iata_code: string | null;

  /** ISO country code (e.g., 'AE', 'AL', 'AM') */
  country_code: string | null;

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
}

/**
 * Response type for location search API endpoint.
 */
export type LocationSearchResponse = Location[];

/**
 * Response type for airport search.
 */
export type AirportResponse = Location;

/**
 * Response type for railway station search.
 */
export type RailwayStationResponse = Location;
