# Autocomplete/Calculation for Professional Travel Destinations

## Overview

Add autocomplete functionality to the "from" and "to" fields in the professional travel form. The autocomplete shows airports when `transport_mode` is "flight" and railway stations when `transport_mode` is "train". Only activates when entering new data (not for API trips).

## Implementation Checklist

### Backend

- [ ] **Create database models** (`backend/app/models/location.py`)
  - [ ] `Airport` model with all CSV fields (id, name, latitude, longitude, iata_code, municipality)
  - [ ] `RailwayStation` model with tab-separated data fields (id, name, latitude, longitudy)
  - [ ] Add indexes on `name`, for airports
  - [ ] Add indexes on `name` for railway stations
  - [ ] Create Pydantic response models: `AirportResponse`, `RailwayStationResponse`

- [ ] **Create database migration** (`backend/alembic/versions/YYYY_MM_DD_HHMM-create_locations_tables.py`)
  - [ ] Create `airports` table with all CSV columns
  - [ ] Create `railway_stations` table with tab-separated columns
  - [ ] Add primary keys, unique constraints, and indexes

- [ ] **Create seed script** (`backend/app/seed_locations.py`)
  - [ ] Load airports from CSV file (comma-separated with header)
  - [ ] Load railway stations from tab-separated file
  - [ ] Handle optional/empty fields gracefully
  - [ ] Skip rows with missing required fields
  - [ ] Handle duplicates (skip if id already exists)
  - [ ] Validate data (latitude/longitude ranges)

- [ ] **Create repository** (`backend/app/repositories/location_repo.py`)
  - [ ] `search_airports(query: str, limit: int = 20) -> List[Airport]`
  - [ ] `search_railway_stations(query: str, limit: int = 20) -> List[RailwayStation]`
  - [ ] Order results by relevance (exact match first)

- [ ] **Create API endpoints** (`backend/app/api/v1/locations.py`)
  - [ ] `GET /api/v1/locations/airports?q={query}&limit={limit}`
  - [ ] `GET /api/v1/locations/railway-stations?q={query}&limit={limit}`
  - [ ] Validate query (minimum 2 characters)
  - [ ] Validate limit (default 20, max 50)
  - [ ] Return appropriate response models

- [ ] **Register router** (`backend/app/api/router.py`)
  - [ ] Import locations router
  - [ ] Add to api_router with prefix "/locations"

- [ ] **Export models** (`backend/app/models/__init__.py`)
  - [ ] Export Airport and RailwayStation models

- [ ] **Create travel impact factor models** (`backend/app/models/travel_impact_factor.py`)
  - [ ] `PlaneImpactFactor` model for haul categories (very_short_haul, short_haul, medium_haul, long_haul)
  - [ ] `TrainImpactFactor` model for country factors (CH, FR, DE, IT, AT, RoW)
  - [ ] Fields: factor_type, category/country, impact_score, rfi_adjustment (for planes), valid_from, valid_to
  - [ ] Create migration for `plane_impact_factors` and `train_impact_factors` tables

- [ ] **Create distance calculation utility** (`backend/app/utils/distance_geography.py`)
  - [ ] `haversine_distance(lat1, lon1, lat2, lon2) -> float` - Calculate great circle distance in km
  - [ ] `calculate_plane_distance(origin_airport, dest_airport) -> float` - Haversine + 95km
  - [ ] `calculate_train_distance(origin_station, dest_station) -> float` - Haversine \* 1.2
  - [ ] `get_haul_category(distance_km) -> str` - Determine plane haul category

- [ ] **Create travel calculation service** (`backend/app/services/travel_calculation_service.py`)
  - [ ] `calculate_plane_emissions(origin_airport, dest_airport, class_, number_of_trips) -> tuple[float, float]`
    - Calculate distance (Haversine + 95km)
    - Determine haul category
    - Get impact_score and RFI_adjustment from factor table
    - Apply class multiplier if provided
    - Return (distance_km, kg_co2eq)
  - [ ] `calculate_train_emissions(origin_station, dest_station, class_, number_of_trips) -> tuple[float, float]`
    - Calculate distance (Haversine \* 1.2)
    - Determine countries
    - Get impact_score from factor table
    - Apply class multiplier if provided
    - Return (distance_km, kg_co2eq)

- [ ] **Update professional travel service** (`backend/app/services/professional_travel_service.py`)
  - [ ] Replace placeholder `_calculate_distance_and_co2` method
  - [ ] Use travel calculation service
  - [ ] Look up airports/stations by name from location tables
  - [ ] Calculate distance and CO2 using selected locations
  - [ ] Handle cases where location not found (fallback to manual entry)

- [ ] **Create seed script for impact factors** (`backend/app/seed_travel_impact_factors.py`)
  - [ ] Seed plane impact factors (very_short_haul, short_haul, medium_haul, long_haul)
  - [ ] Seed train impact factors (CH, FR, DE, IT, AT, RoW)
  - [ ] Include RFI_adjustment values for plane factors

### Frontend

- [ ] **Create type definitions** (`frontend/src/types/locations.ts`)
  - [ ] `AirportResponse` interface
  - [ ] `RailwayStationResponse` interface

- [ ] **Create API service** (`frontend/src/api/locations.ts`)
  - [ ] `searchAirports(query: string, limit?: number): Promise<AirportResponse[]>`
  - [ ] `searchRailwayStations(query: string, limit?: number): Promise<RailwayStationResponse[]>`

- [ ] **Enhance DirectionInput component** (`frontend/src/components/atoms/CO2DestinationInput.vue`)
  - [ ] Add `transportMode` prop (optional, 'flight' | 'train')
  - [ ] Add autocomplete to "from" field
  - [ ] Add autocomplete to "to" field
  - [ ] Implement debouncing (300ms delay)
  - [ ] Show loading state while fetching
  - [ ] Display suggestions in dropdown
  - [ ] Handle selection and update field value
  - [ ] Store selected location coordinates (for distance calculation)
  - [ ] Emit location data (id, name, coordinates) when selected
  - [ ] Only enable when `transportMode` is set
  - [ ] Handle empty results gracefully
  - [ ] Handle API errors

- [ ] **Update ModuleForm** (`frontend/src/components/organisms/module/ModuleForm.vue`)
  - [ ] Pass `transportMode` prop from `form.transport_mode` to DirectionInput
  - [ ] Only pass when creating new entries (not editing API trips)
  - [ ] Store location coordinates when user selects from autocomplete
  - [ ] Pass location data to backend when submitting form (for distance calculation)

## Technical Details

### Autocomplete

- **Debounce**: 100ms delay after typing stops
- **Minimum characters**: 2 characters before searching
- **Max results**: 5 suggestions (configurable, max 50)
- **Search fields**:
  - Airports: name, municipality, iata_code
  - Railway stations: name, name_alt
- **Filtering**: Based on `transport_mode` (airports for flights, stations for trains)

### Distance & CO2 Calculations

**Plane Calculation:**

USE PYTHON LIBRARY FOR THIS

- `Distance(km) = Haversine(origin, destination) + 95 km`
- `kg_CO₂-eq = Distance(km) × Impact_Score × RFI_adjustment × Class_multiplier × number_of_trips`
- **Haul categories** (based on Distance):
  - Very short haul: < 800 km
  - Short haul: 800-1500 km
  - Medium haul: 1500-4000 km
  - Long haul: > 4000 km

**Train Calculation:**

- `Distance(km) = Haversine(origin, destination) × 1.2`
- `kg_CO₂-eq = Distance(km) × Impact_score × Class_multiplier × number_of_trips`
- **Impact score selection**:
  - If trip entirely in CH → use CH fleet average
  - If trip outside CH → use destination country factor (FR, DE, IT, AT)
  - If country not in factor table → use RoW (Rest of World)
