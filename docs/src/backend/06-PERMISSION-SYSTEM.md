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
  "backoffice.files": {
    "view": false
  },
  "backoffice.access": {
    "view": false
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
    "edit": false,
    "export": false
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
  },
  "modules.surface": {
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

| Role                   | Scope  | Permissions                                                                  |
| ---------------------- | ------ | ---------------------------------------------------------------------------- |
| `co2.backoffice.admin` | Global | `backoffice.users`: view, edit, export                                       |
| `co2.backoffice.std`   | Global | `backoffice.users`: view only                                                |
| `co2.user.principal`   | Unit   | `modules.*`: view, edit (all modules)                                        |
| `co2.user.std`         | Unit   | `modules.professional_travel`: view, edit (own trips only, no other modules) |
| `co2.user.secondary`   | Unit   | `modules.*`: view only (all modules)                                         |
| `co2.service.mgr`      | Global | `system.users`: edit (reserved for future)                                   |

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
- `app/core/security.py` - `require_permission()` decorator for routes
- `app/core/policy.py` - OPA policy evaluations for data filtering and resource access
- `app/services/authorization_service.py` - Helper functions for data filtering and resource checks

The UserRead schema computes permissions:

```python
@computed_field
def permissions(self) -> dict:
    return self.calculate_permissions()
```

## Usage in Backend

### Route-Level Permission Checks

Use the `require_permission()` decorator to protect endpoints:

```python
from app.core.security import require_permission
from app.models.user import User
from fastapi import Depends

@router.get("/headcounts")
async def get_headcounts(
    current_user: User = Depends(require_permission("modules.headcount", "view"))
):
    """
    Get headcounts. Requires modules.headcount.view permission.

    Data is automatically filtered by user scope.
    """
    service = HeadcountService(db, user=current_user)
    return await service.get_headcounts()
```

**When permission is denied**, the decorator raises `HTTPException(403)`:

```json
{
  "detail": "Permission denied: modules.headcount.view required"
}
```

### Service-Level Data Filtering

Use `get_data_filters()` to automatically filter data by user scope:

```python
from app.services.authorization_service import get_data_filters

class HeadcountService:
    async def get_headcounts(self):
        # Get filters based on user scope
        filters = await get_data_filters(
            user=self.user,
            resource_type="headcount",
            action="list"
        )
        # filters = {"unit_ids": [...]} for unit scope
        # filters = {"user_id": "..."} for own scope
        # filters = {} for global scope

        # Apply filters to query
        return await self.repository.get_headcounts(filters=filters)
```

**Scope types:**

- **Global scope** (backoffice admin, service manager) - See all data, empty filters
- **Unit scope** (principals, secondaries) - See data for assigned units
- **Own scope** (standard users) - See only own data

### Resource-Level Access Control

Use `check_resource_access()` to check if user can access/edit specific resources:

```python
from app.services.authorization_service import check_resource_access

async def update_trip(self, trip_id: int, data: TripUpdate):
    # Fetch the resource
    trip = await self.repository.get_by_id(trip_id)

    # Check resource-level access
    has_access = await check_resource_access(
        user=self.user,
        resource_type="professional_travel",
        resource={
            "id": trip.id,
            "created_by": trip.created_by,
            "unit_id": trip.unit_id,
            "provider": trip.provider
        },
        action="access"
    )

    if not has_access:
        raise HTTPException(403, "Access denied")

    # Proceed with update
    return await self.repository.update(trip_id, data)
```

## Resource-Level Access Control

OPA policies enforce business rules for individual resources:

### Professional Travel Policy

The `authz/resource/access` policy in `app/core/policy.py` implements these rules for professional travel:

1. **API trips are read-only** - Cannot be edited by anyone (provider = "api")
2. **Backoffice admin** - Can edit all trips (global scope)
3. **Principals/Secondaries** - Can edit manual/CSV trips in their assigned units
4. **Standard users** - Can only edit their own manual trips

Example policy evaluation:

```python
# User tries to edit an API trip
resource = {
    "id": 123,
    "provider": "api",  # API trip
    "created_by": "user-456",
    "unit_id": "12345"
}

decision = await query_policy("authz/resource/access", {
    "user": user,
    "resource_type": "professional_travel",
    "resource": resource
})
# Returns: {"allow": False, "reason": "API trips are read-only"}
```

```python
# Standard user tries to edit own manual trip
resource = {
    "id": 123,
    "provider": "manual",
    "created_by": "user-123",  # Same as current user
    "unit_id": "12345"
}

decision = await query_policy("authz/resource/access", {
    "user": user,
    "resource_type": "professional_travel",
    "resource": resource
})
# Returns: {"allow": True, "reason": "Owner access"}
```

### Adding Custom Resource Policies

To add business rules for other resource types, extend `_evaluate_resource_access_policy()` in `app/core/policy.py`:

```python
if resource_type == "your_resource":
    # Your custom rules here
    if some_condition:
        return {"allow": False, "reason": "Your denial reason"}

    return {"allow": True, "reason": "Access granted"}
```

## Key Principles

1. Permissions are calculated from roles, never stored
2. Frontend checks permissions, not roles
3. Permissions recalculate on every `/auth/me` call
4. Domains are independent and combine when needed
5. Flat structure with dot-notation for easy checking
6. **Authorization checks at route level** via `require_permission()` decorator
7. **Service-level data filtering** via `get_data_filters()` based on scope
8. **Resource-level access control** via `check_resource_access()` for individual records
9. **Deprecated**: Direct role checks in business logic (use permissions instead)

## Further Reading

For detailed developer instructions and examples, see:

- [Developer Guide: Permission-Based Authorization](./07-DEVELOPER-GUIDE-PERMISSIONS.md)
- [Backend Architecture](./02-ARCHITECTURE.md)
- [Request Flow](./05-REQUEST_FLOW.md)
