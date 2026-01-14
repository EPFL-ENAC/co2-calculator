# Developer Guide: Permission-Based Authorization

## Table of Contents

1. [Introduction](#introduction)
2. [Adding New Permissions](#adding-new-permissions)
3. [Using require_permission() Decorator](#using-require_permission-decorator)
4. [Implementing Data Filtering in Services](#implementing-data-filtering-in-services)
5. [Resource-Level Access Control](#resource-level-access-control)
6. [Permission Checks in Frontend](#permission-checks-in-frontend)
7. [Testing Permission-Based Features](#testing-permission-based-features)
8. [Common Patterns](#common-patterns)
9. [Troubleshooting](#troubleshooting)
10. [Migration from Role-Based Code](#migration-from-role-based-code)

---

## Introduction

The CO2 Calculator API uses a **permission-based authorization model** where:

- **Roles are assigned** to users (e.g., `co2.user.principal`, `co2.backoffice.admin`)
- **Permissions are calculated** dynamically from roles at authentication time
- **Authorization checks** are performed at multiple levels: route, service, and resource

### Key Concepts

#### Permissions

Permissions use dot-notation paths with actions:

- Path: `backoffice.users`, `modules.headcount`, `modules.professional_travel`
- Actions: `view` (read), `edit` (create/update/delete), `export` (data export)

#### Roles

Roles are assigned to users and determine which permissions they receive:

- `co2.user.std` - Standard user with own-scope access
- `co2.user.principal` - Unit manager with unit-scope access
- `co2.user.secondary` - Delegated unit manager (same as principal)
- `co2.backoffice.std` - Backoffice user with unit-scope admin access
- `co2.backoffice.admin` - Backoffice administrator with global access
- `co2.service.mgr` - System administrator with full access

#### Scopes

Scopes determine the data a user can access:

- **Global** - See all data (backoffice admin, service manager)
- **Unit** - See data for assigned units (principals, secondaries)
- **Own** - See only own data (standard users)

#### Resources

Resources are individual data records (e.g., a specific headcount entry, a travel record).
Resource-level policies can enforce business rules like "API trips are read-only."

### When to Use What

- **Route-level checks** (`require_permission`) - Most common, checks if user has permission to access endpoint
- **Service-level filtering** (`get_data_filters`) - Automatically filter data by scope (global/unit/own)
- **Resource-level checks** (`check_resource_access`) - Check if user can access/edit specific resource

---

## Adding New Permissions

Follow these steps to add a new permission to the system:

### Step 1: Define Permission in `app/utils/permissions.py`

Add the permission to the structure and map roles to it:

```python
def initialize_permissions() -> dict:
    """Initialize the permission structure with all available permissions."""
    return {
        "backoffice": {
            "users": {"view": False, "edit": False},
            "files": {"view": False},
            "access": {"view": False},
            "your_new_resource": {"view": False, "edit": False},  # ADD THIS
        },
        "modules": {
            "headcount": {"view": False, "edit": False},
            # ... other modules
        },
        # ... other categories
    }
```

Then map roles to the new permission:

```python
def map_role_permissions(role: str) -> dict:
    """Map role to permissions."""
    permissions = initialize_permissions()

    if role == "co2.backoffice.admin":
        permissions["backoffice"]["users"]["view"] = True
        permissions["backoffice"]["users"]["edit"] = True
        permissions["backoffice"]["files"]["view"] = True
        permissions["backoffice"]["access"]["view"] = True
        permissions["backoffice"]["your_new_resource"]["view"] = True  # ADD THIS
        permissions["backoffice"]["your_new_resource"]["edit"] = True  # ADD THIS
        # ... grant permissions for other modules

    # Repeat for other relevant roles
    return permissions
```

### Step 2: Use in Routes with `require_permission()`

Add permission check to your route:

```python
from app.core.security import require_permission
from app.models.user import User
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get(
    "/your-endpoint",
    response_model=YourResponseModel,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: backoffice.your_new_resource.view required"
                    }
                }
            }
        }
    }
)
async def get_your_resource(
    current_user: User = Depends(require_permission("backoffice.your_new_resource", "view"))
):
    """
    Get your resource.

    **Required Permission**: `backoffice.your_new_resource.view`

    **Authorization**:
    - Backoffice admin: Can access all resources
    - Other users: No access

    **Raises**:
    - 403: Missing required permission
    """
    # Your implementation here
    pass
```

### Step 3: Update Frontend Permission Checks

If you have UI elements that should be conditionally shown/disabled:

```typescript
// In your React component
import { hasPermission } from '@/utils/permissions'

function YourComponent() {
  const { permissions } = useAuth()

  const canView = hasPermission(permissions, 'backoffice.your_new_resource', 'view')
  const canEdit = hasPermission(permissions, 'backoffice.your_new_resource', 'edit')

  return (
    <div>
      {canView && <ViewButton />}
      {canEdit && <EditButton />}
    </div>
  )
}
```

### Step 4: Add Tests

Test the permission in your test suite:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_endpoint_requires_permission(client: AsyncClient, standard_user_token):
    """Test that endpoint requires proper permission."""
    response = await client.get(
        "/api/v1/your-endpoint",
        headers={"Authorization": f"Bearer {standard_user_token}"}
    )
    assert response.status_code == 403
    assert "backoffice.your_new_resource.view required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_endpoint_with_permission(client: AsyncClient, backoffice_admin_token):
    """Test that endpoint works with proper permission."""
    response = await client.get(
        "/api/v1/your-endpoint",
        headers={"Authorization": f"Bearer {backoffice_admin_token}"}
    )
    assert response.status_code == 200
```

---

## Using require_permission() Decorator

The `require_permission()` decorator is the primary way to enforce authorization at the route level.

### Syntax

```python
from app.core.security import require_permission
from app.models.user import User
from fastapi import Depends

async def your_endpoint(
    current_user: User = Depends(require_permission("path.resource", "action"))
):
    # Your implementation
    pass
```

### Parameters

- **path** (str): Permission path (e.g., `"modules.headcount"`, `"backoffice.users"`)
- **action** (str): Permission action - `"view"`, `"edit"`, or `"export"`

### Common Permission Paths

#### Backoffice Permissions

```python
require_permission("backoffice.users", "view")   # View users
require_permission("backoffice.users", "edit")   # Manage users
require_permission("backoffice.files", "view")   # Access file storage
require_permission("backoffice.access", "view")  # General backoffice access
```

#### Module Permissions

```python
require_permission("modules.headcount", "view")              # View headcount data
require_permission("modules.headcount", "edit")              # Edit headcount data
require_permission("modules.professional_travel", "view")    # View travel data
require_permission("modules.professional_travel", "edit")    # Edit travel data
require_permission("modules.professional_travel", "export")  # Export travel data
require_permission("modules.equipment", "view")              # View equipment data
require_permission("modules.equipment", "edit")              # Edit equipment data
```

### Examples from Codebase

#### Example 1: Headcount Endpoints ([app/api/v1/headcounts.py](../../../../backend/app/api/v1/headcounts.py))

```python
@router.get(
    "/units/{unit_id}/years/{year}/headcounts",
    response_model=list[HeadCount]
)
async def get_headcounts(
    unit_id: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "view"))
) -> list[HeadCount]:
    """
    Get headcount records.

    **Required Permission**: `modules.headcount.view`

    Data is automatically filtered by user scope:
    - Global scope: See all units
    - Unit scope: See assigned units
    - Own scope: See own data only
    """
    service = HeadcountService(db, user=current_user)
    headcounts = await service.get_headcounts(unit_id=unit_id, year=year)
    return headcounts
```

#### Example 2: User Management ([app/api/v1/backoffice.py](../../../../backend/app/api/v1/backoffice.py))

```python
@router.get("/users", response_model=List[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "view"))
):
    """
    List users with policy-based filtering.

    **Required Permission**: `backoffice.users.view`

    **Authorization**:
    - Backoffice admin: See all users
    - Other users: No access
    """
    # Implementation
    pass
```

#### Example 3: File Access ([app/api/v1/files.py](../../../../backend/app/api/v1/files.py))

```python
@router.get(
    "/{file_path:path}",
    status_code=200,
    description="Download any assets from file storage"
)
async def get_file(
    file_path: str,
    download: bool = Query(False, alias="d"),
    current_user: User = Depends(require_permission("backoffice.files", "view"))
):
    """
    Retrieve a file from file storage.

    **Required Permission**: `backoffice.files.view`

    Granted to backoffice admin and standard backoffice users.
    """
    # Implementation
    pass
```

### What Happens on Permission Denial

When a user lacks the required permission, the decorator raises `HTTPException(403)`:

```json
{
  "detail": "Permission denied: modules.headcount.edit required"
}
```

The error message includes the exact permission that was required, making it easy to debug and request access.

---

## Implementing Data Filtering in Services

Services should filter data based on user scope to ensure users only see data they're authorized to access.

### When to Use `get_data_filters()`

Use `get_data_filters()` in service methods that list or query multiple records:

- List endpoints (e.g., get all headcounts, get all trips)
- Search/filter operations
- Aggregate queries

### How Scope-Based Filtering Works

The `get_data_filters()` function returns different filters based on user scope:

- **Global scope** - Empty filters (no restrictions)
- **Unit scope** - `{"unit_ids": ["unit1", "unit2"]}`
- **Own scope** - `{"user_id": "user-123"}`

### Implementation Pattern

#### Step 1: Get Filters in Service Constructor or Method

```python
from app.services.authorization_service import get_data_filters

class HeadcountService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user

    async def get_headcounts(
        self,
        unit_id: str,
        year: int,
        limit: int = 100,
        offset: int = 0
    ) -> list[HeadCount]:
        """Get headcounts with scope-based filtering."""

        # Get filters based on user scope
        filters = await get_data_filters(
            user=self.user,
            resource_type="headcount",
            action="list"
        )

        # Apply filters to query
        headcounts = await self.repository.get_headcounts(
            db=self.db,
            unit_id=unit_id,
            year=year,
            filters=filters,  # Pass filters to repository
            limit=limit,
            offset=offset
        )

        return headcounts
```

#### Step 2: Apply Filters in Repository

```python
from sqlmodel import select

class HeadcountRepository:
    async def get_headcounts(
        self,
        db: AsyncSession,
        unit_id: str,
        year: int,
        filters: dict,
        limit: int = 100,
        offset: int = 0
    ) -> list[HeadCount]:
        """Get headcounts with filters applied."""

        query = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            HeadCount.year == year
        )

        # Apply scope-based filters
        scope = filters.get("scope", "own")

        if scope == "global":
            # No additional filters - see everything
            pass
        elif scope == "unit":
            # Filter by unit_ids
            unit_ids = filters.get("unit_ids", [])
            if unit_ids:
                query = query.where(HeadCount.unit_id.in_(unit_ids))
        elif scope == "own":
            # Filter by user_id
            user_id = filters.get("user_id")
            if user_id:
                query = query.where(HeadCount.created_by == user_id)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()
```

### Example from HeadcountService

Full example from [app/services/headcount_service.py](../../../../backend/app/services/headcount_service.py):

```python
from app.services.authorization_service import get_data_filters

class HeadcountService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repository = HeadcountRepository()

    async def get_headcounts(
        self,
        unit_id: str,
        year: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc"
    ) -> list[HeadCount]:
        """
        Get headcounts with policy-based filtering.

        Automatically filters data based on user scope:
        - Global: See all headcounts
        - Unit: See headcounts for assigned units
        - Own: See own headcounts only
        """
        # Get data filters based on user scope
        filters = await get_data_filters(
            user=self.user,
            resource_type="headcount",
            action="list"
        )

        logger.info(
            "Fetching headcounts with filters",
            extra={
                "user_id": self.user.id,
                "unit_id": unit_id,
                "year": year,
                "filters": filters,
            },
        )

        # Use repository with filters
        headcounts = await self.repository.get_headcounts(
            db=self.db,
            unit_id=unit_id,
            year=year,
            filters=filters,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return headcounts
```

### Benefits of This Pattern

1. **Centralized Authorization** - Filter logic is in one place (policy module)
2. **Automatic Filtering** - Services don't need to know about roles or scopes
3. **Type Safety** - Filters are structured dicts with known keys
4. **Auditable** - Filter decisions are logged for debugging

---

## Resource-Level Access Control

Resource-level access control checks if a user can access/edit a specific resource (individual record).

### When to Use `check_resource_access()`

Use resource access checks for:

- Update operations on individual records
- Delete operations on individual records
- When business rules apply (e.g., "API trips are read-only")
- When ownership matters (e.g., "users can only edit their own trips")

### How It Works

The `check_resource_access()` function uses OPA policies to evaluate access based on:

- Resource type (e.g., `professional_travel`, `headcount`)
- Resource properties (e.g., `provider`, `created_by`, `unit_id`)
- User roles and scope
- Business logic rules

### Implementation Pattern

```python
from app.services.authorization_service import check_resource_access
from fastapi import HTTPException

async def update_resource(
    resource_id: int,
    update_data: ResourceUpdate,
    user: User,
    db: AsyncSession
):
    """Update a resource with access control."""

    # Step 1: Fetch the resource
    resource = await repository.get_by_id(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Step 2: Check resource-level access
    resource_dict = {
        "id": resource.id,
        "created_by": resource.created_by,
        "unit_id": resource.unit_id,
        # Include other relevant fields
    }

    has_access = await check_resource_access(
        user=user,
        resource_type="your_resource_type",
        resource=resource_dict,
        action="access"
    )

    if not has_access:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to edit this resource"
        )

    # Step 3: Proceed with update
    updated_resource = await repository.update(db, resource_id, update_data)
    return updated_resource
```

### Professional Travel Example

Professional travel has complex resource-level rules defined in [app/core/policy.py](../../../../backend/app/core/policy.py):

#### Rules

1. **API trips are read-only** - Cannot be edited by anyone
2. **Backoffice admin** - Can edit all trips (global scope)
3. **Principals/Secondaries** - Can edit manual/CSV trips in their units
4. **Standard users** - Can only edit their own manual trips

#### Implementation

```python
from app.services.authorization_service import check_resource_access

async def update_professional_travel(
    trip_id: int,
    update_data: TravelUpdate,
    user: User,
    db: AsyncSession
):
    """Update a professional travel record with access control."""

    # Fetch the trip
    trip = await repository.get_by_id(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Check resource-level access
    resource = {
        "id": trip.id,
        "created_by": trip.created_by,
        "unit_id": trip.unit_id,
        "provider": trip.provider,  # Important: determines if API trip
    }

    has_access = await check_resource_access(
        user=user,
        resource_type="professional_travel",
        resource=resource,
        action="access"
    )

    if not has_access:
        # Policy will return specific denial reason
        raise HTTPException(
            status_code=403,
            detail="Access denied: Cannot edit this trip"
        )

    # Proceed with update
    updated_trip = await repository.update(db, trip_id, update_data)
    return updated_trip
```

#### Policy Logic ([app/core/policy.py](../../../../backend/app/core/policy.py#L146-L205))

```python
async def _evaluate_resource_access_policy(input_data: dict) -> dict:
    """Evaluate resource-level access policy for specific resources."""

    if resource_type == "professional_travel":
        provider = resource.get("provider", "")
        created_by = resource.get("created_by", "")
        resource_unit_id = resource.get("unit_id", "")

        # Rule 1: API trips are read-only
        if provider == "api":
            return {
                "allow": False,
                "reason": "API trips are read-only and cannot be edited"
            }

        # Rule 2: Global scope (backoffice admin)
        has_global_scope = any(
            isinstance(role.on, GlobalScope)
            for role in roles
        )
        if has_global_scope:
            return {"allow": True, "reason": "Global scope access"}

        # Rule 3: Unit scope (principals/secondaries)
        user_unit_ids = set()
        principal_or_secondary = False
        for role in roles:
            if role.role in ["co2.user.principal", "co2.user.secondary"]:
                principal_or_secondary = True
                if role.on.unit:
                    user_unit_ids.add(role.on.unit)

        if principal_or_secondary and resource_unit_id in user_unit_ids:
            return {"allow": True, "reason": "Unit scope access"}

        # Rule 4: Ownership (standard users)
        if user_id and created_by == user_id:
            return {"allow": True, "reason": "Owner access"}

        return {"allow": False, "reason": "Insufficient permissions"}
```

### Adding Custom Resource Policies

To add custom business rules for a new resource type:

1. Add policy logic in `_evaluate_resource_access_policy()` in [app/core/policy.py](../../../../backend/app/core/policy.py)
2. Check resource type and apply rules:

```python
if resource_type == "your_new_resource":
    # Your custom rules here
    if some_condition:
        return {"allow": False, "reason": "Your denial reason"}

    return {"allow": True, "reason": "Access granted"}
```

---

## Permission Checks in Frontend

The frontend receives permissions from the `/api/v1/auth/me` endpoint and uses them for UI control.

### How Frontend Receives Permissions

When a user authenticates, the `/auth/me` endpoint returns:

```json
{
  "id": "user-123",
  "email": "user@example.com",
  "roles": [...],
  "permissions": {
    "backoffice": {
      "users": {"view": false, "edit": false},
      "files": {"view": true}
    },
    "modules": {
      "headcount": {"view": true, "edit": true},
      "professional_travel": {"view": true, "edit": true, "export": false}
    }
  }
}
```

### Using `hasPermission()` Helper

The frontend should have a utility function:

```typescript
// utils/permissions.ts
export function hasPermission(
  permissions: Record<string, any>,
  path: string,
  action: string,
): boolean {
  const parts = path.split(".");
  let current = permissions;

  for (const part of parts) {
    if (!current || typeof current !== "object") {
      return false;
    }
    current = current[part];
  }

  return current?.[action] === true;
}
```

### Conditional Rendering Based on Permissions

```typescript
import { hasPermission } from '@/utils/permissions'
import { useAuth } from '@/hooks/useAuth'

function HeadcountPage() {
  const { user } = useAuth()
  const permissions = user?.permissions || {}

  const canView = hasPermission(permissions, 'modules.headcount', 'view')
  const canEdit = hasPermission(permissions, 'modules.headcount', 'edit')

  if (!canView) {
    return <AccessDenied message="You don't have permission to view headcount data" />
  }

  return (
    <div>
      <HeadcountList />
      {canEdit && (
        <Button onClick={openCreateModal}>
          Create Headcount
        </Button>
      )}
    </div>
  )
}
```

### Disabling UI Elements Without Permission

```typescript
function EditButton({ tripId }: { tripId: number }) {
  const { user } = useAuth()
  const permissions = user?.permissions || {}

  const canEdit = hasPermission(permissions, 'modules.professional_travel', 'edit')

  return (
    <Button
      onClick={() => editTrip(tripId)}
      disabled={!canEdit}
      title={!canEdit ? "You don't have permission to edit trips" : undefined}
    >
      Edit
    </Button>
  )
}
```

### Example: Conditional Menu Items

```typescript
function Navigation() {
  const { user } = useAuth()
  const permissions = user?.permissions || {}

  return (
    <nav>
      <NavItem to="/">Home</NavItem>

      {hasPermission(permissions, 'modules.headcount', 'view') && (
        <NavItem to="/headcount">Headcount</NavItem>
      )}

      {hasPermission(permissions, 'modules.professional_travel', 'view') && (
        <NavItem to="/travel">Professional Travel</NavItem>
      )}

      {hasPermission(permissions, 'backoffice.users', 'view') && (
        <NavItem to="/backoffice/users">User Management</NavItem>
      )}
    </nav>
  )
}
```

### Important Notes

- **Frontend checks are for UX only** - They hide/disable UI elements but don't provide security
- **Backend enforces security** - All security is enforced by `require_permission()` on routes
- **Always implement both** - Frontend for better UX, backend for security

---

## Testing Permission-Based Features

### Creating Test Users with Specific Permissions

Create test fixtures for users with different roles:

```python
import pytest
from app.models.user import User, Role, RoleScope, GlobalScope

@pytest.fixture
async def standard_user(db):
    """Create a standard user with own-scope access."""
    user = User(
        id="user-std-123",
        email="standard@example.com",
        roles=[
            Role(role="co2.user.std", on=RoleScope(unit="12345"))
        ]
    )
    # Save to DB or mock as needed
    return user

@pytest.fixture
async def principal_user(db):
    """Create a principal with unit-scope access."""
    user = User(
        id="user-principal-123",
        email="principal@example.com",
        roles=[
            Role(role="co2.user.principal", on=RoleScope(unit="12345"))
        ]
    )
    return user

@pytest.fixture
async def backoffice_admin(db):
    """Create a backoffice admin with global access."""
    user = User(
        id="user-admin-123",
        email="admin@example.com",
        roles=[
            Role(role="co2.backoffice.admin", on=GlobalScope())
        ]
    )
    return user
```

### Mocking Permission Checks

For unit tests, you can mock the `require_permission` dependency:

```python
from unittest.mock import AsyncMock, patch
from app.core.security import require_permission

@pytest.mark.asyncio
async def test_endpoint_logic_without_auth():
    """Test endpoint logic without authentication."""

    # Mock the dependency
    mock_user = User(id="test-user", email="test@example.com")

    with patch('app.api.v1.your_router.require_permission') as mock_perm:
        mock_perm.return_value = lambda: mock_user

        # Test your endpoint
        response = await your_endpoint()
        assert response is not None
```

### Testing 403 Responses

Test that endpoints properly reject unauthorized users:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_headcount_edit_denied_for_standard_user(
    client: AsyncClient,
    standard_user_token: str
):
    """Test that standard users cannot edit headcounts."""

    response = await client.post(
        "/api/v1/units/12345/years/2024/headcounts",
        headers={"Authorization": f"Bearer {standard_user_token}"},
        json={"fte": 1.0, "month": 1}
    )

    assert response.status_code == 403
    assert "modules.headcount.edit required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_headcount_edit_allowed_for_principal(
    client: AsyncClient,
    principal_user_token: str
):
    """Test that principals can edit headcounts."""

    response = await client.post(
        "/api/v1/units/12345/years/2024/headcounts",
        headers={"Authorization": f"Bearer {principal_user_token}"},
        json={"fte": 1.0, "month": 1}
    )

    assert response.status_code == 201
```

### Integration Test Patterns

Test complete flows with permission checks:

```python
@pytest.mark.asyncio
async def test_data_filtering_by_scope(
    client: AsyncClient,
    db: AsyncSession,
    standard_user_token: str,
    principal_user_token: str,
    backoffice_admin_token: str
):
    """Test that data is properly filtered by user scope."""

    # Create test data for different units
    await create_headcount(db, unit_id="12345", created_by="user-std-123")
    await create_headcount(db, unit_id="67890", created_by="user-other")

    # Standard user should only see own data
    response = await client.get(
        "/api/v1/units/12345/years/2024/headcounts",
        headers={"Authorization": f"Bearer {standard_user_token}"}
    )
    assert len(response.json()) == 1

    # Principal should see unit data
    response = await client.get(
        "/api/v1/units/12345/years/2024/headcounts",
        headers={"Authorization": f"Bearer {principal_user_token}"}
    )
    assert len(response.json()) >= 1

    # Admin should see all data
    response = await client.get(
        "/api/v1/units/12345/years/2024/headcounts",
        headers={"Authorization": f"Bearer {backoffice_admin_token}"}
    )
    assert len(response.json()) >= 1
```

### Testing Resource-Level Access

Test resource-level business rules:

```python
@pytest.mark.asyncio
async def test_cannot_edit_api_trip(
    client: AsyncClient,
    backoffice_admin_token: str
):
    """Test that even admins cannot edit API trips."""

    # Create API trip
    trip = await create_trip(provider="api", unit_id="12345")

    # Try to edit as admin
    response = await client.patch(
        f"/api/v1/professional-travel/{trip.id}",
        headers={"Authorization": f"Bearer {backoffice_admin_token}"},
        json={"distance": 1000}
    )

    assert response.status_code == 403
    assert "read-only" in response.json()["detail"].lower()
```

---

## Common Patterns

### Pattern 1: Route-Level Permission Check (Most Common)

Use for most endpoints:

```python
@router.get("/resources")
async def list_resources(
    current_user: User = Depends(require_permission("path.resource", "view"))
):
    """List resources. Permission checked at route level."""
    service = ResourceService(db, user=current_user)
    return await service.list_resources()
```

**When to use**: Almost all endpoints should have route-level permission checks.

### Pattern 2: Service-Level Data Filtering

Use for list/query operations:

```python
class ResourceService:
    async def list_resources(self):
        """List resources with automatic scope filtering."""
        filters = await get_data_filters(
            user=self.user,
            resource_type="resource",
            action="list"
        )
        return await self.repository.get_all(filters=filters)
```

**When to use**: Any service method that returns multiple records.

### Pattern 3: Resource-Level Access Control

Use for update/delete operations:

```python
async def update_resource(self, resource_id: int, data: ResourceUpdate):
    """Update resource with access check."""
    resource = await self.repository.get_by_id(resource_id)

    has_access = await check_resource_access(
        user=self.user,
        resource_type="resource",
        resource={"id": resource.id, "created_by": resource.created_by},
        action="access"
    )

    if not has_access:
        raise HTTPException(403, "Access denied")

    return await self.repository.update(resource_id, data)
```

**When to use**: Update and delete operations where ownership or business rules matter.

### Pattern 4: Combined Permission + Resource Check

Use when both permission and resource-level checks are needed:

```python
@router.patch("/trips/{trip_id}")
async def update_trip(
    trip_id: int,
    data: TripUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.professional_travel", "edit"))
):
    """
    Update trip with both permission and resource checks.

    1. Route-level: Check user has edit permission
    2. Resource-level: Check user can edit THIS specific trip
    """
    service = TravelService(db, user=current_user)
    return await service.update_trip(trip_id, data)  # Does resource check inside
```

**When to use**: Most edit/delete operations in production.

---

## Troubleshooting

### Debugging Permission Denials

#### Problem: 403 Error with "Permission denied" message

**Steps to debug**:

1. **Check the exact permission required** - The error message shows it:

   ```json
   { "detail": "Permission denied: modules.headcount.edit required" }
   ```

2. **Check user's calculated permissions** - Call `/api/v1/auth/me`:

   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/auth/me
   ```

   Look for the permission in the response:

   ```json
   {
     "permissions": {
       "modules": {
         "headcount": { "view": true, "edit": false }
       }
     }
   }
   ```

3. **Check user's roles** - Permissions come from roles:

   ```json
   {
     "roles": [{ "role": "co2.user.std", "on": { "unit": "12345" } }]
   }
   ```

4. **Check role-to-permission mapping** - Look in [app/utils/permissions.py](../../../../backend/app/utils/permissions.py) to see if the role grants the permission.

5. **Check for typos** - Ensure permission path matches exactly (case-sensitive).

#### Problem: User has permission but still gets 403

**Possible causes**:

1. **Scope mismatch** - User has permission but wrong scope:
   - User is principal for unit "12345" but trying to access unit "67890"
   - Check logs for scope filtering decisions

2. **Resource-level denial** - Route permission passed but resource check failed:
   - Check if resource has special rules (e.g., API trips read-only)
   - Look at `check_resource_access()` logs

3. **JWT token expired or invalid** - User isn't actually authenticated:
   - Check token expiration
   - Try refreshing token

### Common Mistakes

#### Mistake 1: Using role checks instead of permission checks

```python
# WRONG - Deprecated pattern
if user.has_role("co2.user.principal"):
    # Do something

# CORRECT - Use permissions
current_user: User = Depends(require_permission("modules.headcount", "edit"))
```

#### Mistake 2: Not applying data filters in service

```python
# WRONG - No filtering, users might see unauthorized data
async def list_resources(self):
    return await self.repository.get_all()

# CORRECT - Apply scope filters
async def list_resources(self):
    filters = await get_data_filters(self.user, "resource", "list")
    return await self.repository.get_all(filters=filters)
```

#### Mistake 3: Checking permissions in frontend only

```python
# WRONG - Security only in frontend
// Frontend: if (canEdit) { callAPI() }

# CORRECT - Security in backend
@router.patch("/resource/{id}")
async def update(
    current_user: User = Depends(require_permission("path.resource", "edit"))
):
    # Backend enforces permission
```

#### Mistake 4: Wrong permission path

```python
# WRONG - Path doesn't match permission structure
require_permission("headcount", "edit")  # Missing "modules."

# CORRECT
require_permission("modules.headcount", "edit")
```

#### Mistake 5: Not handling resource access for updates

```python
# WRONG - Only route-level check, no resource check
async def update_trip(trip_id: int, data: TripUpdate):
    return await repository.update(trip_id, data)
    # Problem: Standard user could edit other users' trips

# CORRECT - Check resource access
async def update_trip(trip_id: int, data: TripUpdate):
    trip = await repository.get_by_id(trip_id)
    has_access = await check_resource_access(
        self.user, "professional_travel", trip.dict()
    )
    if not has_access:
        raise HTTPException(403, "Access denied")
    return await repository.update(trip_id, data)
```

### Using Deprecation Warnings to Find Old Code

The codebase includes deprecation warnings for old role-based methods:

```python
# In app/models/user.py
def has_role(self, role_name: str) -> bool:
    """Check if user has a specific role.

    DEPRECATED: Use permission-based checks instead.
    """
    warnings.warn(
        "has_role() is deprecated. Use permission-based checks instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ...
```

**To find deprecated usage**:

```bash
# Run tests with warnings enabled
pytest -W default::DeprecationWarning

# Or run the app with warnings
PYTHONWARNINGS=default python -m app.main
```

You'll see warnings like:

```
DeprecationWarning: has_role() is deprecated. Use permission-based checks instead.
  File "app/api/v1/old_endpoint.py", line 42, in old_function
```

---

## Migration from Role-Based Code

### Identifying Deprecated Patterns

Look for these patterns in your code:

```python
# Pattern 1: Direct role checks
if user.has_role("co2.user.principal"):
    # ...

# Pattern 2: Role-based dependencies
current_user: User = Depends(get_current_active_user_with_any_role(["co2.backoffice.admin"]))

# Pattern 3: Role checks in services
if "co2.backoffice.admin" in [role.role for role in user.roles]:
    # ...
```

### Converting Role Checks to Permission Checks

#### Example 1: Route-Level Conversion

**Before (role-based)**:

```python
from app.api.deps import get_current_active_user_with_any_role

@router.get("/headcounts")
async def get_headcounts(
    current_user: User = Depends(
        get_current_active_user_with_any_role([
            "co2.user.principal",
            "co2.user.secondary",
            "co2.backoffice.admin"
        ])
    )
):
    # Implementation
    pass
```

**After (permission-based)**:

```python
from app.core.security import require_permission

@router.get("/headcounts")
async def get_headcounts(
    current_user: User = Depends(require_permission("modules.headcount", "view"))
):
    # Implementation
    pass
```

**Benefits**:

- Single permission check instead of listing multiple roles
- Easier to add new roles with the permission
- Clearer intent (what action, not which roles)

#### Example 2: Service-Level Conversion

**Before (role-based)**:

```python
class HeadcountService:
    async def get_headcounts(self):
        # Check if user is admin
        is_admin = any(
            role.role == "co2.backoffice.admin"
            for role in self.user.roles
        )

        if is_admin:
            # Get all headcounts
            return await self.repository.get_all()
        else:
            # Get only user's headcounts
            return await self.repository.get_by_user(self.user.id)
```

**After (permission-based)**:

```python
from app.services.authorization_service import get_data_filters

class HeadcountService:
    async def get_headcounts(self):
        # Get filters based on scope
        filters = await get_data_filters(
            user=self.user,
            resource_type="headcount",
            action="list"
        )

        # Repository applies filters automatically
        return await self.repository.get_all(filters=filters)
```

**Benefits**:

- Scope-based filtering is centralized in policy
- Supports more than just admin/non-admin (also principals with unit scope)
- Easier to test and audit

#### Example 3: Resource Access Conversion

**Before (role-based)**:

```python
async def update_trip(self, trip_id: int, data: TripUpdate):
    trip = await self.repository.get_by_id(trip_id)

    # Check if user can edit
    is_admin = self.user.has_role("co2.backoffice.admin")
    is_owner = trip.created_by == self.user.id

    if not (is_admin or is_owner):
        raise HTTPException(403, "Access denied")

    return await self.repository.update(trip_id, data)
```

**After (permission-based)**:

```python
from app.services.authorization_service import check_resource_access

async def update_trip(self, trip_id: int, data: TripUpdate):
    trip = await self.repository.get_by_id(trip_id)

    # Check resource access via policy
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

    return await self.repository.update(trip_id, data)
```

**Benefits**:

- Complex rules (API trips read-only, principals can edit unit trips) handled in policy
- Business logic is separated from authorization
- Can add new roles/rules without changing service code

### Handling has_role() Deprecation Warnings

When you see deprecation warnings:

```
DeprecationWarning: has_role() is deprecated. Use permission-based checks instead.
  File "app/services/my_service.py", line 42
```

**Steps to fix**:

1. **Identify the intent** - What was the role check trying to achieve?
   - Checking if user can view something? → Use `require_permission(..., "view")`
   - Checking if user can edit something? → Use `require_permission(..., "edit")`
   - Checking scope (admin vs regular)? → Use `get_data_filters()`

2. **Replace with permission check** - See examples above

3. **Test thoroughly** - Ensure new permission-based code works for all roles

4. **Remove deprecated code** - Once confirmed working, remove the old role check

### Migration Checklist

- [ ] Search codebase for `has_role()` calls
- [ ] Search for `get_current_active_user_with_any_role()`
- [ ] Search for role name strings in business logic (e.g., `"co2.backoffice.admin"`)
- [ ] Replace with `require_permission()` at route level
- [ ] Replace with `get_data_filters()` in services for list operations
- [ ] Replace with `check_resource_access()` in services for updates
- [ ] Add permission documentation to route docstrings
- [ ] Update tests to use permission checks
- [ ] Run tests with deprecation warnings enabled
- [ ] Verify all warnings are resolved

---

## Summary

This guide covered the complete workflow for working with permission-based authorization:

1. **Adding new permissions** - Define in permissions.py, use in routes, update frontend
2. **Route-level checks** - Use `require_permission()` decorator
3. **Service-level filtering** - Use `get_data_filters()` for scope-based queries
4. **Resource-level checks** - Use `check_resource_access()` for individual records
5. **Frontend integration** - Use `hasPermission()` for UI control
6. **Testing** - Create fixtures, test 403s, test filtering
7. **Common patterns** - Route + service + resource checks
8. **Troubleshooting** - Debug permissions, avoid common mistakes
9. **Migration** - Convert from role-based to permission-based

For more information, see:

- [Permission System Overview](./06-PERMISSION-SYSTEM.md)
- [Backend Architecture](./02-ARCHITECTURE.md)
- [Request Flow](./05-REQUEST_FLOW.md)
