Generating Mermaid ERD...
```mermaid
erDiagram
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
  users ||--}o resources : created_by
  users ||--}o resources : updated_by
  users ||--}o units : principal_user_id
  units ||--}o unit_users : unit_id
  users ||--}o unit_users : user_id
```
Mermaid ERD generation complete.
