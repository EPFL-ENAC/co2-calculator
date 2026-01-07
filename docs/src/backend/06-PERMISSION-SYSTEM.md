# Backend Permission System

The CO2 Calculator uses permission-based access control. Permissions
are calculated dynamically from user roles on every request. They are
never stored in the database.

## How It Works

The backend calculates permissions during `/auth/me` response
serialization:

1. Read user from database with `roles_raw` field
2. Convert roles to Role objects via `User.roles` property
3. Call `calculate_permissions()` in UserRead schema
4. Map roles to permissions using `calculate_user_permissions()`
5. Include computed permissions in response

Permissions are computed in-memory. No database writes occur.

## Permission Structure

Permissions use flat dot-notation keys:

```json
{
  "backoffice.users": {
    "view": true,
    "edit": false,
    "export": false
  },
  "system.users": {
    "edit": false
  },
  "modules.headcount": {
    "view": true,
    "edit": true
  },
  "modules.equipment": {
    "view": true,
    "edit": true
  },
  "modules.professional_travel": {
    "view": true,
    "edit": false
  },
  "modules.infrastructure": {
    "view": true,
    "edit": false
  },
  "modules.purchase": {
    "view": true,
    "edit": false
  },
  "modules.internal_services": {
    "view": true,
    "edit": false
  },
  "modules.external_cloud": {
    "view": true,
    "edit": false
  }
}
```

Three independent domains exist:

- `backoffice.*` - Administrative features
- `modules.*` - CO2 calculation modules
- `system.*` - System routes (reserved)

Domains are independent. Backoffice roles do not grant module access.

## Role Mapping

| Role                   | Scope  | Permissions                                                 |
| ---------------------- | ------ | ----------------------------------------------------------- |
| `co2.backoffice.admin` | Global | `backoffice.users`: view, edit, export                      |
| `co2.backoffice.std`   | Global | `backoffice.users`: view only                               |
| `co2.user.principal`   | Unit   | `modules.*`: view, edit (all modules)                       |
| `co2.user.std`         | Unit   | `modules.professional_travel`: view only (no other modules) |
| `co2.user.secondary`   | Unit   | `modules.*`: view only (all modules)                        |
| `co2.service.mgr`      | Global | `system.users`: edit (reserved for future)                  |

Permissions from different domains combine when a user has multiple
roles.

## API Response

The `/auth/me` endpoint returns:

```json
{
  "id": "123456",
  "email": "user@epfl.ch",
  "roles": [...],
  "permissions": {
    "backoffice.users": {"view": false, "edit": false, "export": false},
    "system.users": {"edit": false},
    "modules.headcount": {"view": true, "edit": true},
    "modules.equipment": {"view": true, "edit": true},
    "modules.professional_travel": {"view": true, "edit": true},
    "modules.infrastructure": {"view": true, "edit": true},
    "modules.purchase": {"view": true, "edit": true},
    "modules.internal_services": {"view": true, "edit": true},
    "modules.external_cloud": {"view": true, "edit": true}
  }
}
```

Use the `permissions` field for access control. The `roles` field is
for display only.

## Implementation

Files:

- `app/models/user.py` - User model with `calculate_permissions()`
- `app/schemas/user.py` - UserRead schema with `@computed_field`
- `app/utils/permissions.py` - Permission calculation logic

The UserRead schema computes permissions:

```python
@computed_field
def permissions(self) -> dict:
    return self.calculate_permissions()
```

## Key Principles

1. Permissions are calculated from roles, never stored
2. Frontend checks permissions, not roles
3. Permissions recalculate on every `/auth/me` call
4. Domains are independent and combine when needed
5. Flat structure with dot-notation for easy checking
