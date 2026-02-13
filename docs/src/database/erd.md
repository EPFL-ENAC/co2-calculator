Generating Mermaid ERD...

```mermaid
erDiagram
  audit_documents {
    VARCHAR change_reason
    VARCHAR change_type
    DATETIME changed_at
    VARCHAR changed_by
    VARCHAR current_hash
    JSON data_diff
    JSON data_snapshot
    INTEGER entity_id "indexed"
    VARCHAR entity_type "indexed"
    JSON handled_ids
    VARCHAR handler_id
    INTEGER id PK
    VARCHAR ip_address
    BOOLEAN is_current
    VARCHAR previous_hash
    VARCHAR route_path
    JSON route_payload
    INTEGER version "indexed"
  }
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
  locations {
    VARCHAR airport_size
    VARCHAR continent "indexed"
    VARCHAR country_code "indexed"
    VARCHAR iata_code "indexed"
    INTEGER id PK
    VARCHAR keywords
    FLOAT latitude
    FLOAT longitude
    VARCHAR municipality "indexed"
    VARCHAR name "indexed"
    VARCHAR transport_mode "indexed"
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
