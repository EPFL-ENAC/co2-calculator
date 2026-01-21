Generating Mermaid ERD...

```mermaid
erDiagram
  data_ingestion_jobs {
    INTEGER entity_id
    VARCHAR entity_type
    INTEGER id PK
    VARCHAR ingestion_method
    JSON meta
    INTEGER module_type_id FK
    VARCHAR provider
    VARCHAR status
    VARCHAR status_message
    VARCHAR target_type
    INTEGER year
  }
  emission_factors {
    TIMESTAMP created_at
    VARCHAR created_by "indexed"
    JSON factor_metadata
    VARCHAR factor_name "indexed"
    INTEGER id PK
    VARCHAR region "indexed"
    VARCHAR source
    TIMESTAMP valid_from
    TIMESTAMP valid_to
    FLOAT value
    INTEGER version "indexed"
  }
  equipment {
    FLOAT active_usage_pct
    VARCHAR category "indexed"
    VARCHAR cost_center "indexed"
    VARCHAR cost_center_description
    TIMESTAMP created_at
    VARCHAR created_by "indexed"
    VARCHAR equipment_class "indexed"
    JSON equipment_metadata
    INTEGER id PK
    VARCHAR name "indexed"
    FLOAT passive_usage_pct
    INTEGER power_factor_id FK
    TIMESTAMP service_date
    VARCHAR status "indexed"
    VARCHAR sub_class
    VARCHAR submodule "indexed"
    INTEGER unit_id "indexed"
    TIMESTAMP updated_at
    VARCHAR updated_by "indexed"
  }
  equipment_emissions {
    FLOAT annual_kwh
    JSON calculation_inputs
    TIMESTAMP computed_at "indexed"
    INTEGER emission_factor_id FK
    INTEGER equipment_id FK
    VARCHAR formula_version
    INTEGER id PK
    BOOLEAN is_current "indexed"
    FLOAT kg_co2eq
    INTEGER power_factor_id FK
  }
  headcounts {
    VARCHAR cf
    VARCHAR cf_name
    VARCHAR cf_user_id
    DATETIME created_at
    INTEGER created_by "indexed"
    DATE date
    VARCHAR display_name
    FLOAT fte
    VARCHAR function
    VARCHAR function_role
    INTEGER id PK
    VARCHAR provider
    VARCHAR provider_source
    VARCHAR sciper "indexed"
    VARCHAR status
    VARCHAR submodule "indexed"
    INTEGER unit_id "indexed"
    VARCHAR unit_name
    DATETIME updated_at
    INTEGER updated_by "indexed"
  }
  inventory {
    INTEGER id PK
    INTEGER unit_id
    INTEGER year
  }
  inventory_module {
    INTEGER id PK
    INTEGER inventory_id FK
    INTEGER module_type_id FK
    INTEGER status
  }
  locations {
    VARCHAR countrycode "indexed"
    DATETIME created_at
    INTEGER created_by "indexed"
    VARCHAR iata_code "indexed"
    INTEGER id PK
    FLOAT latitude
    FLOAT longitude
    VARCHAR name "indexed"
    VARCHAR transport_mode "indexed"
    DATETIME updated_at
    INTEGER updated_by "indexed"
  }
  module_types {
    VARCHAR description
    INTEGER id PK
    VARCHAR name "indexed"
  }
  modules {
    JSON data
    INTEGER id PK
    INTEGER inventory_module_id FK
    INTEGER module_type_id FK
    INTEGER variant_type_id FK
  }
  plane_impact_factors {
    VARCHAR category "indexed"
    DATETIME created_at
    INTEGER created_by "indexed"
    VARCHAR factor_type "indexed"
    INTEGER id PK
    FLOAT impact_score
    FLOAT max_distance
    FLOAT min_distance
    FLOAT rfi_adjustment
    VARCHAR source
    DATETIME updated_at
    INTEGER updated_by "indexed"
    TIMESTAMP valid_from
    TIMESTAMP valid_to
  }
  power_factors {
    FLOAT active_power_w
    TIMESTAMP created_at
    VARCHAR created_by "indexed"
    VARCHAR equipment_class "indexed"
    INTEGER id PK
    JSON power_metadata
    VARCHAR source
    FLOAT standby_power_w
    VARCHAR sub_category "indexed"
    VARCHAR sub_class "indexed"
    VARCHAR submodule "indexed"
    TIMESTAMP valid_from
    TIMESTAMP valid_to
    INTEGER version "indexed"
  }
  professional_travel_emissions {
    JSON calculation_inputs
    TIMESTAMP computed_at "indexed"
    FLOAT distance_km
    VARCHAR formula_version
    INTEGER id PK
    BOOLEAN is_current "indexed"
    FLOAT kg_co2eq
    INTEGER plane_impact_factor_id FK
    INTEGER professional_travel_id FK
    INTEGER train_impact_factor_id FK
  }
  professional_travels {
    VARCHAR class
    DATETIME created_at
    INTEGER created_by "indexed"
    DATE departure_date
    INTEGER destination_location_id FK
    INTEGER id PK
    BOOLEAN is_round_trip
    INTEGER number_of_trips
    INTEGER origin_location_id FK
    VARCHAR provider
    VARCHAR transport_mode
    INTEGER traveler_id
    VARCHAR traveler_name
    INTEGER unit_id "indexed"
    DATETIME updated_at
    INTEGER updated_by "indexed"
    INTEGER year "indexed"
  }
  train_impact_factors {
    VARCHAR countrycode "indexed"
    DATETIME created_at
    INTEGER created_by "indexed"
    INTEGER id PK
    FLOAT impact_score
    VARCHAR source
    DATETIME updated_at
    INTEGER updated_by "indexed"
    TIMESTAMP valid_from
    TIMESTAMP valid_to
  }
  unit_users {
    VARCHAR role "indexed"
    INTEGER unit_id PK
    INTEGER user_id PK
  }
  units {
    JSON affiliations
    JSON cost_centers
    INTEGER id PK
    VARCHAR name "indexed"
    VARCHAR principal_user_provider_code FK
    VARCHAR provider
    VARCHAR provider_code "indexed"
  }
  users {
    VARCHAR display_name
    VARCHAR email "indexed"
    VARCHAR function
    INTEGER id PK
    DATETIME last_login
    VARCHAR provider
    VARCHAR provider_code "indexed"
    JSON roles_raw
  }
  variant_types {
    VARCHAR description
    INTEGER id PK
    INTEGER module_type_id FK
    VARCHAR name "indexed"
  }
  emission_factors ||--}o equipment_emissions : "emission_factor_id"
  equipment ||--}o equipment_emissions : "equipment_id"
  inventory ||--}o inventory_module : "inventory_id"
  inventory_module ||--}o modules : "inventory_module_id"
  locations ||--}o professional_travels : "destination_location_id"
  locations ||--}o professional_travels : "origin_location_id"
  module_types ||--}o data_ingestion_jobs : "module_type_id"
  module_types ||--}o inventory_module : "module_type_id"
  module_types ||--}o modules : "module_type_id"
  module_types ||--}o variant_types : "module_type_id"
  plane_impact_factors ||--}o professional_travel_emissions : "plane_impact_factor_id"
  power_factors ||--}o equipment : "power_factor_id"
  power_factors ||--}o equipment_emissions : "power_factor_id"
  professional_travels ||--}o professional_travel_emissions : "professional_travel_id"
  train_impact_factors ||--}o professional_travel_emissions : "train_impact_factor_id"
  units ||--}o unit_users : "unit_id"
  users ||--}o unit_users : "user_id"
  users ||--}o units : "principal_user_provider_code"
  variant_types ||--}o modules : "variant_type_id"
```

Mermaid ERD generation complete.
