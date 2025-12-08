Generating Mermaid ERD...

```mermaid
erDiagram
  emission_factors {
    VARCHAR factor_name
    FLOAT value
    INTEGER version
    TIMESTAMP valid_from
    TIMESTAMP valid_to
    VARCHAR region
    VARCHAR source
    JSON factor_metadata
    TIMESTAMP created_at
    VARCHAR created_by
    INTEGER id
  }
  power_factors {
    VARCHAR submodule
    VARCHAR sub_category
    VARCHAR equipment_class
    VARCHAR sub_class
    FLOAT active_power_w
    FLOAT standby_power_w
    INTEGER version
    TIMESTAMP valid_from
    TIMESTAMP valid_to
    VARCHAR source
    JSON power_metadata
    TIMESTAMP created_at
    VARCHAR created_by
    INTEGER id
  }
  equipment {
    VARCHAR cost_center
    VARCHAR cost_center_description
    VARCHAR name
    VARCHAR category
    VARCHAR submodule
    VARCHAR equipment_class
    VARCHAR sub_class
    TIMESTAMP service_date
    VARCHAR status
    FLOAT active_usage_pct
    FLOAT passive_usage_pct
    FLOAT active_power_w
    FLOAT standby_power_w
    INTEGER power_factor_id
    VARCHAR unit_id
    JSON equipment_metadata
    TIMESTAMP created_at
    TIMESTAMP updated_at
    VARCHAR created_by
    VARCHAR updated_by
    INTEGER id
  }
  equipment_emissions {
    INTEGER equipment_id
    FLOAT annual_kwh
    FLOAT kg_co2eq
    INTEGER emission_factor_id
    INTEGER power_factor_id
    VARCHAR formula_version
    TIMESTAMP computed_at
    JSON calculation_inputs
    BOOLEAN is_current
    INTEGER id
  }
  resources {
    VARCHAR name
    VARCHAR description
    VARCHAR visibility
    JSON data
    JSON resource_metadata
    TIMESTAMP created_at
    TIMESTAMP updated_at
    VARCHAR created_by
    VARCHAR updated_by
    VARCHAR unit_id
    INTEGER id
  }
  units {
    VARCHAR name
    VARCHAR principal_user_id
    JSON affiliations
    VARCHAR visibility
    TIMESTAMP created_at
    TIMESTAMP updated_at
    VARCHAR created_by
    VARCHAR updated_by
    VARCHAR id
  }
  unit_users {
    VARCHAR unit_id
    VARCHAR user_id
  }
  users {
    JSON roles
    VARCHAR sciper
    BOOLEAN is_active
    DATETIME last_login
    TIMESTAMP created_at
    TIMESTAMP updated_at
    VARCHAR created_by
    VARCHAR updated_by
    VARCHAR id
    VARCHAR email
  }
  users ||--}o emission_factors : created_by
  users ||--}o power_factors : created_by
  users ||--}o equipment : created_by
  users ||--}o equipment : updated_by
  power_factors ||--}o equipment : power_factor_id
  emission_factors ||--}o equipment_emissions : emission_factor_id
  equipment ||--}o equipment_emissions : equipment_id
  power_factors ||--}o equipment_emissions : power_factor_id
  users ||--}o resources : created_by
  users ||--}o resources : updated_by
  users ||--}o units : principal_user_id
  users ||--}o unit_users : user_id
  units ||--}o unit_users : unit_id
```

Mermaid ERD generation complete.
