Generating Mermaid ERD...

```mermaid
erDiagram
  emission_factors {
    TIMESTAMP created_at
    VARCHAR created_by FK
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
    VARCHAR created_by FK
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
    VARCHAR unit_id "indexed"
    TIMESTAMP updated_at
    VARCHAR updated_by FK
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
    VARCHAR created_by "indexed"
    DATE date
    VARCHAR display_name
    FLOAT fte
    VARCHAR function
    VARCHAR function_role
    INTEGER id PK
    VARCHAR provider
    VARCHAR sciper "indexed"
    VARCHAR status
    VARCHAR submodule "indexed"
    VARCHAR unit_id "indexed"
    VARCHAR unit_name
    DATETIME updated_at
    VARCHAR updated_by "indexed"
  }
  inventory {
    INTEGER id PK
    VARCHAR unit_id
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
    VARCHAR created_by "indexed"
    VARCHAR iata_code "indexed"
    INTEGER id PK
    FLOAT latitude
    FLOAT longitude
    VARCHAR name "indexed"
    VARCHAR transport_mode "indexed"
    DATETIME updated_at
    VARCHAR updated_by "indexed"
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
    VARCHAR created_by "indexed"
    VARCHAR factor_type "indexed"
    INTEGER id PK
    FLOAT impact_score
    FLOAT max_distance
    FLOAT min_distance
    FLOAT rfi_adjustment
    VARCHAR source
    DATETIME updated_at
    VARCHAR updated_by "indexed"
    TIMESTAMP valid_from
    TIMESTAMP valid_to
  }
  power_factors {
    FLOAT active_power_w
    TIMESTAMP created_at
    VARCHAR created_by FK
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
    VARCHAR created_by "indexed"
    DATE departure_date
    INTEGER destination_location_id FK
    INTEGER id PK
    BOOLEAN is_round_trip
    INTEGER number_of_trips
    INTEGER origin_location_id FK
    VARCHAR provider
    VARCHAR transport_mode
    VARCHAR traveler_id
    VARCHAR traveler_name
    VARCHAR unit_id "indexed"
    DATETIME updated_at
    VARCHAR updated_by "indexed"
    INTEGER year "indexed"
  }
  resources {
    TIMESTAMP created_at
    VARCHAR created_by FK
    JSON data
    VARCHAR description
    INTEGER id PK
    VARCHAR name "indexed"
    JSON resource_metadata
    VARCHAR unit_id "indexed"
    TIMESTAMP updated_at
    VARCHAR updated_by FK
    VARCHAR visibility
  }
  train_impact_factors {
    VARCHAR countrycode "indexed"
    DATETIME created_at
    VARCHAR created_by "indexed"
    INTEGER id PK
    FLOAT impact_score
    VARCHAR source
    DATETIME updated_at
    VARCHAR updated_by "indexed"
    TIMESTAMP valid_from
    TIMESTAMP valid_to
  }
  unit_users {
    VARCHAR role "indexed"
    VARCHAR unit_id PK
    VARCHAR user_id PK
  }
  units {
    JSON affiliations
    VARCHAR cf
    VARCHAR code "indexed"
    TIMESTAMP created_at
    VARCHAR created_by "indexed"
    VARCHAR id PK
    VARCHAR name "indexed"
    VARCHAR principal_user_email
    VARCHAR principal_user_function
    VARCHAR principal_user_id "indexed"
    VARCHAR principal_user_name
    VARCHAR provider
    TIMESTAMP updated_at
    VARCHAR updated_by "indexed"
    VARCHAR visibility
  }
  users {
    TIMESTAMP created_at
    VARCHAR created_by "indexed"
    VARCHAR display_name
    VARCHAR email "indexed"
    VARCHAR id PK
    BOOLEAN is_active
    DATETIME last_login
    VARCHAR provider
    JSON roles_raw
    TIMESTAMP updated_at
    VARCHAR updated_by "indexed"
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
  module_types ||--}o inventory_module : "module_type_id"
  module_types ||--}o modules : "module_type_id"
  module_types ||--}o variant_types : "module_type_id"
  plane_impact_factors ||--}o professional_travel_emissions : "plane_impact_factor_id"
  power_factors ||--}o equipment : "power_factor_id"
  power_factors ||--}o equipment_emissions : "power_factor_id"
  professional_travels ||--}o professional_travel_emissions : "professional_travel_id"
  train_impact_factors ||--}o professional_travel_emissions : "train_impact_factor_id"
  units ||--}o unit_users : "unit_id"
  users ||--}o emission_factors : "created_by"
  users ||--}o equipment : "created_by"
  users ||--}o equipment : "updated_by"
  users ||--}o power_factors : "created_by"
  users ||--}o resources : "created_by"
  users ||--}o resources : "updated_by"
  users ||--}o unit_users : "user_id"
  variant_types ||--}o modules : "variant_type_id"
```

Mermaid ERD generation complete.
