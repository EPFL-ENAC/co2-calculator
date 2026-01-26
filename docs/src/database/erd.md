Generating Mermaid ERD...

```mermaid
erDiagram
  carbon_report_modules {
    INTEGER carbon_report_id FK
    INTEGER id PK
    INTEGER module_type_id FK
    INTEGER status
  }
  carbon_reports {
    INTEGER id PK
    INTEGER unit_id FK
    INTEGER year
  }
  data_entries {
    INTEGER carbon_report_module_id FK
    JSON data
    INTEGER data_entry_type_id FK
    INTEGER id PK
  }
  data_entry_emissions {
    TIMESTAMP computed_at "indexed"
    INTEGER data_entry_id FK
    INTEGER emission_type_id FK
    VARCHAR formula_version
    INTEGER id PK
    FLOAT kg_co2eq
    JSON meta
    INTEGER primary_factor_id FK
    VARCHAR subcategory
  }
  data_entry_types {
    VARCHAR id PK
    INTEGER module_type_id FK
    VARCHAR name "indexed"
  }
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
  emission_types {
    VARCHAR code "indexed"
    INTEGER id PK
  }
  factors {
    JSON classification
    INTEGER data_entry_type_id FK
    INTEGER emission_type_id FK
    INTEGER id PK
    BOOLEAN is_conversion "indexed"
    JSON values
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
  locations {
    VARCHAR airport_size
    VARCHAR continent "indexed"
    VARCHAR countrycode "indexed"
    DATETIME created_at
    INTEGER created_by "indexed"
    VARCHAR iata_code "indexed"
    INTEGER id PK
    VARCHAR keywords
    FLOAT latitude
    FLOAT longitude
    VARCHAR municipality "indexed"
    VARCHAR name "indexed"
    VARCHAR transport_mode "indexed"
    DATETIME updated_at
    INTEGER updated_by "indexed"
  }
  module_types {
    INTEGER id PK
    VARCHAR name "indexed"
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
    VARCHAR provider_source
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
  carbon_report_modules ||--}o data_entries : "carbon_report_module_id"
  carbon_reports ||--}o carbon_report_modules : "carbon_report_id"
  data_entries ||--}o data_entry_emissions : "data_entry_id"
  data_entry_types ||--}o data_entries : "data_entry_type_id"
  data_entry_types ||--}o factors : "data_entry_type_id"
  emission_types ||--}o data_entry_emissions : "emission_type_id"
  emission_types ||--}o factors : "emission_type_id"
  factors ||--}o data_entry_emissions : "primary_factor_id"
  locations ||--}o professional_travels : "destination_location_id"
  locations ||--}o professional_travels : "origin_location_id"
  module_types ||--}o carbon_report_modules : "module_type_id"
  module_types ||--}o data_entry_types : "module_type_id"
  module_types ||--}o data_ingestion_jobs : "module_type_id"
  plane_impact_factors ||--}o professional_travel_emissions : "plane_impact_factor_id"
  professional_travels ||--}o professional_travel_emissions : "professional_travel_id"
  train_impact_factors ||--}o professional_travel_emissions : "train_impact_factor_id"
  units ||--}o carbon_reports : "unit_id"
  units ||--}o unit_users : "unit_id"
  users ||--}o unit_users : "user_id"
  users ||--}o units : "principal_user_provider_code"
```

Mermaid ERD generation complete.
