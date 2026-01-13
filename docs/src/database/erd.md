Generating Mermaid ERD...
```mermaid
erDiagram
  emission_types {
    VARCHAR code UK "indexed"
    VARCHAR description
    INTEGER id PK "indexed"
  }
  factors {
    INTEGER emission_type_id FK "indexed"
    BOOLEAN is_conversion "indexed"
    INTEGER data_entry_type_id FK "indexed"
    JSON classification
    JSON values
    INTEGER id PK "indexed"
  }
  carbon_reports {
    INTEGER year
    INTEGER department_id FK "indexed"
    INTEGER id PK
  }
  carbon_report_modules {
    INTEGER module_type_id FK "indexed"
    INTEGER status
    INTEGER carbon_report_id FK "indexed"
    INTEGER id PK
  }
  data_entries {
    INTEGER data_entry_type_id FK "indexed"
    INTEGER carbon_report_module_id FK "indexed"
    JSON data
    INTEGER id PK "indexed"
  }
  data_entry_emissions {
    INTEGER data_entry_id FK "indexed"
    INTEGER emission_type_id FK "indexed"
    INTEGER primary_factor_id FK "indexed"
    VARCHAR subcategory
    FLOAT kg_co2eq
    JSON meta
    VARCHAR formula_version
    TIMESTAMP computed_at "indexed"
    INTEGER id PK "indexed"
  }
  data_entry_types {
    VARCHAR name "indexed"
    VARCHAR description
    INTEGER module_type_id FK "indexed"
    INTEGER id PK "indexed"
  }
  departments {
    VARCHAR code UK "indexed"
    VARCHAR name "indexed"
    INTEGER principal_user_id FK "indexed"
    JSON cost_centers
    JSON affiliations
    INTEGER id PK "indexed"
    VARCHAR provider
  }
  department_users {
    INTEGER id PK
    INTEGER department_id FK "indexed"
    INTEGER user_id FK "indexed"
    VARCHAR role "indexed"
  }
  module_types {
    VARCHAR name UK "indexed"
    VARCHAR description
    INTEGER id PK "indexed"
  }
  users {
    JSON roles_raw
    DATETIME last_login
    INTEGER id PK "indexed"
    VARCHAR code UK "indexed"
    VARCHAR provider
    VARCHAR email UK "indexed"
    VARCHAR display_name
    VARCHAR function
  }
  document_versions {
    VARCHAR entity_type "indexed"
    INTEGER entity_id "indexed"
    INTEGER version "indexed"
    BOOLEAN is_current
    JSON data_snapshot
    JSON data_diff
    VARCHAR change_type
    VARCHAR change_reason
    VARCHAR changed_by
    DATETIME changed_at
    VARCHAR previous_hash
    VARCHAR current_hash
    INTEGER id PK "indexed"
  }
  emission_types ||--}o factors : emission_type_id
  data_entry_types ||--}o factors : data_entry_type_id
  departments ||--}o carbon_reports : department_id
  carbon_reports ||--}o carbon_report_modules : carbon_report_id
  module_types ||--}o carbon_report_modules : module_type_id
  carbon_report_modules ||--}o data_entries : carbon_report_module_id
  data_entry_types ||--}o data_entries : data_entry_type_id
  factors ||--}o data_entry_emissions : primary_factor_id
  emission_types ||--}o data_entry_emissions : emission_type_id
  data_entries ||--}o data_entry_emissions : data_entry_id
  module_types ||--}o data_entry_types : module_type_id
  users ||--}o departments : principal_user_id
  users ||--}o department_users : user_id
  departments ||--}o department_users : department_id
```
Mermaid ERD generation complete.
