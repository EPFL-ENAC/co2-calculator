Generating Mermaid ERD...

```mermaid
erDiagram
  carbon_report_modules {
    INTEGER carbon_report_id FK
    INTEGER id PK
    INTEGER module_type_id "indexed"
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
    INTEGER data_entry_type_id "indexed"
    INTEGER id PK
    VARCHAR status
  }
  data_entry_emissions {
    TIMESTAMP computed_at "indexed"
    INTEGER data_entry_id FK
    INTEGER emission_type_id "indexed"
    VARCHAR formula_version
    INTEGER id PK
    FLOAT kg_co2eq
    JSON meta
    INTEGER primary_factor_id FK
    VARCHAR subcategory
  }
  data_ingestion_jobs {
    INTEGER data_entry_type_id
    INTEGER entity_id
    VARCHAR entity_type
    INTEGER id PK
    VARCHAR ingestion_method
    JSON meta
    INTEGER module_type_id
    VARCHAR provider
    VARCHAR status
    VARCHAR status_message
    VARCHAR target_type
    INTEGER year
  }
  factors {
    JSON classification
    INTEGER data_entry_type_id "indexed"
    INTEGER emission_type_id "indexed"
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
  factors ||--}o data_entry_emissions : "primary_factor_id"
  units ||--}o carbon_reports : "unit_id"
  units ||--}o unit_users : "unit_id"
  users ||--}o unit_users : "user_id"
  users ||--}o units : "principal_user_provider_code"
```

Mermaid ERD generation complete.
