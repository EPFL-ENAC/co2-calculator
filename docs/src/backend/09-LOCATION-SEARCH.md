# Location Search System

The location search system provides autocomplete functionality for finding airports and train stations in the professional travel module.

## Overview

The system supports:

- **Airports** (`transport_mode: 'plane'`) - medium and large airports worldwide
- **Train stations** (`transport_mode: 'train'`) - railway stations

## API Endpoints

### Search Locations

```
GET /api/v1/locations/search
```

| Parameter        | Type   | Required | Default | Description                                    |
| ---------------- | ------ | -------- | ------- | ---------------------------------------------- |
| `query`          | string | Yes      | -       | Search string (minimum 2 characters)           |
| `limit`          | int    | No       | 5       | Max results (1-20)                             |
| `transport_mode` | string | No       | -       | Filter: `'plane'` or `'train'`. Omit for both. |

**Response**: Array of `LocationRead` objects

```json
[
  {
    "id": 123,
    "transport_mode": "plane",
    "name": "Geneva Airport",
    "airport_size": "large_airport",
    "latitude": 46.2381,
    "longitude": 6.1089,
    "continent": "EU",
    "countrycode": "CH",
    "iata_code": "GVA",
    "municipality": "Geneva",
    "keywords": "Cointrin"
  }
]
```

### Calculate Distance

```
GET /api/v1/locations/calculate-distance
```

| Parameter                 | Type   | Required | Description             |
| ------------------------- | ------ | -------- | ----------------------- |
| `origin_location_id`      | int    | Yes      | Origin location ID      |
| `destination_location_id` | int    | Yes      | Destination location ID |
| `transport_mode`          | string | Yes      | `'plane'` or `'train'`  |

**Response**:

```json
{
  "distance_km": 412
}
```

## Search Algorithm

### Relevance Ordering

Results are ordered by:

1. **Country priority**: Switzerland (`CH`) locations appear first
2. **Airport size** (planes only): `large_airport` before `medium_airport`
3. **Match relevance**:
   - Exact match (highest)
   - Starts with query
   - Contains query (lowest)
4. **Alphabetical** by name

### Search Fields

The search queries across multiple fields:

- `name` - Location name (e.g., "Geneva Airport")
- `municipality` - City name (e.g., "Geneva")
- `keywords` - Alternative names (e.g., "Cointrin")

### Accent-Insensitive Search

Uses PostgreSQL ICU collations (`ch_fr_ci_ai`) for accent-insensitive, case-insensitive matching:

- "Geneve" matches "Geneve"
- "zurich" matches "Zurich"
- "BASEL" matches "Basel"

## Distance Calculation

### Plane Distance

```
distance = haversine(origin, destination) + 95 km
```

The 95 km adjustment accounts for:

- Airport approach patterns
- Air traffic routing
- Taxiing

### Train Distance

```
distance = haversine(origin, destination) * 1.2
```

The 1.2 multiplier accounts for:

- Track routing (not straight lines)
- Curves and geography
- Station-to-station detours

### Haul Categories (Planes)

| Category          | Distance           |
| ----------------- | ------------------ |
| `very_short_haul` | < 800 km           |
| `short_haul`      | 800 - 1,500 km     |
| `medium_haul`     | 1,500 - < 4,000 km |
| `long_haul`       | >= 4,000 km        |

## Data Model

### Location Table

| Field            | Type   | Description                                           |
| ---------------- | ------ | ----------------------------------------------------- |
| `id`             | int    | Primary key                                           |
| `transport_mode` | enum   | `'plane'` or `'train'`                                |
| `name`           | string | Location name                                         |
| `airport_size`   | string | `'medium_airport'` or `'large_airport'` (planes only) |
| `latitude`       | float  | Latitude in decimal degrees                           |
| `longitude`      | float  | Longitude in decimal degrees                          |
| `continent`      | string | Continent code (e.g., `'EU'`, `'NA'`)                 |
| `countrycode`    | string | ISO 2-letter country code                             |
| `iata_code`      | string | IATA airport code (planes only)                       |
| `municipality`   | string | City/municipality name                                |
| `keywords`       | string | Alternative names for search                          |

> Note: The `locations` table also includes standard audit columns (e.g. `created_at`, `updated_at`, etc.) via `AuditMixin`, which are omitted here for brevity.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  CO2DestinationInput.vue                                 │   │
│  │  - Autocomplete input with debounce (100ms)              │   │
│  │  - Shows name, IATA code, country                        │   │
│  │  - Swap origin/destination button                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  locations.ts (API client)                               │   │
│  │  - searchAirports()                                      │   │
│  │  - searchRailwayStations()                               │   │
│  │  - searchLocations()                                     │   │
│  │  - calculateDistance()                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  locations.py (API Router)                               │   │
│  │  - GET /search                                           │   │
│  │  - GET /calculate-distance                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  location_service.py (Business Logic)                    │   │
│  │  - Validates transport_mode                              │   │
│  │  - Validates query length                                │   │
│  │  - Corrects swapped coordinates                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  location_repo.py (Data Access)                          │   │
│  │  - ICU collation search                                  │   │
│  │  - Relevance scoring with CASE                           │   │
│  │  - Country and airport size prioritization               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  distance_geography.py (Utilities)                       │   │
│  │  - Haversine distance calculation                        │   │
│  │  - Plane/train distance adjustments                      │   │
│  │  - Haul category determination                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  locations table                                         │   │
│  │  - ICU collations: ch_fr_ci_ai, ch_de_ci_ai, ch_it_ci_ai │   │
│  │  - Indexes on: name, transport_mode, countrycode         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Seeding

Location data is seeded from CSV:

```
backend/SEED_DATA/seed_travel_location.csv
```

Run the seed script:

```bash
cd backend
uv run python -m app.seed.seed_locations
```

## Key Files

| File                                                                                                                    | Description            |
| ----------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| [backend/app/api/v1/locations.py](../../../backend/app/api/v1/locations.py)                                             | API endpoints          |
| [backend/app/services/location_service.py](../../../backend/app/services/location_service.py)                           | Business logic         |
| [backend/app/repositories/location_repo.py](../../../backend/app/repositories/location_repo.py)                         | Database queries       |
| [backend/app/models/location.py](../../../backend/app/models/location.py)                                               | Data model             |
| [backend/app/utils/distance_geography.py](../../../backend/app/utils/distance_geography.py)                             | Distance calculations  |
| [frontend/src/api/locations.ts](../../../frontend/src/api/locations.ts)                                                 | Frontend API client    |
| [frontend/src/components/atoms/CO2DestinationInput.vue](../../../frontend/src/components/atoms/CO2DestinationInput.vue) | Autocomplete component |
| [frontend/src/constant/locations.ts](../../../frontend/src/constant/locations.ts)                                       | TypeScript types       |

## Usage Example

### Frontend (Vue)

```vue
<CO2DestinationInput
  v-model:from="origin"
  v-model:to="destination"
  :transport-mode="transportMode"
  @from-location-selected="handleFromSelected"
  @to-location-selected="handleToSelected"
/>
```
