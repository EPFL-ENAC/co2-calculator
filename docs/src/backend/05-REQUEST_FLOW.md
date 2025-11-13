# Request Flow

This document shows how a typical HTTP request flows through the
backend layers. Use it to understand the request lifecycle and where
each layer processes data.

## Overview

A request travels through five layers before returning a response:

```
HTTP Request
    ↓
API Layer       - Validate and route
    ↓
Service Layer   - Check permissions, apply logic
    ↓
Repository Layer - Query database
    ↓
Database        - Return data
    ↓
HTTP Response
```

## Complete Flow Example

Here's how `GET /api/v1/resources` processes:

### 1. API Layer

**File**: `app/api/v1/resources.py`

```python
@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    return resource_service.list_resources(db, user)
```

**Actions**:

- Validate JWT token from Authorization header
- Extract User object from token
- Get database session
- Call service layer

### 2. Security Middleware

**File**: `app/core/security.py`

```python
def decode_jwt(token: str) -> dict:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

def get_user_by_id(user_id: str) -> User:
    # Fetch user from database
    return User(id="user@epfl.ch", roles=["user"], unit_id="ENAC")
```

**Actions**:

- Decode JWT token
- Load user from database
- Return User object with roles and unit

### 3. Service Layer

**File**: `app/services/resource_service.py`

```python
def list_resources(db: Session, user: User):
    # Check permissions
    if not user.has_permission("resource.read"):
        raise PermissionDenied()

    # Build filters for this user
    filters = {
        "unit_id": user.unit_id,
        "visibility": ["public", "unit"]
    }

    # Query with filters
    return resource_repo.get_resources(db, filters=filters)
```

**Actions**:

- Check user has permission to read resources
- Build filters based on user context (unit, role)
- Call repository with filters

### 4. Repository Layer

**File**: `app/repositories/resource_repo.py`

```python
def get_resources(db: Session, filters: dict):
    query = db.query(Resource)

    # Apply filters from service
    for key, value in filters.items():
        if isinstance(value, list):
            query = query.filter(
                getattr(Resource, key).in_(value)
            )
        else:
            query = query.filter(
                getattr(Resource, key) == value
            )

    return query.all()
```

**Actions**:

- Build SQLAlchemy query
- Apply filters to WHERE clause
- Execute query and return results

### 5. Database Query

**SQL Generated**:

```sql
SELECT * FROM resources
WHERE unit_id = 'ENAC'
  AND visibility IN ('public', 'unit')
```

**Result**:

```python
[
    Resource(id=1, name="Resource A", unit_id="ENAC", ...),
    Resource(id=2, name="Resource B", unit_id="ENAC", ...),
]
```

### 6. Serialization

**File**: `app/schemas/resource.py`

```python
class ResourceRead(BaseModel):
    id: int
    name: str
    unit_id: str
    visibility: str
    created_at: datetime
```

**Actions**:

- Convert SQLAlchemy models to Pydantic schemas
- Validate output matches schema
- Serialize to JSON

### 7. HTTP Response

```json
HTTP/1.1 200 OK
Content-Type: application/json

[
  {
    "id": 1,
    "name": "Resource A",
    "unit_id": "ENAC",
    "visibility": "unit",
    "created_at": "2025-10-29T10:00:00Z"
  },
  {
    "id": 2,
    "name": "Resource B",
    "unit_id": "ENAC",
    "visibility": "public",
    "created_at": "2025-10-29T11:00:00Z"
  }
]
```

## Authorization Decision Points

### Who? (Authentication)

- **Where**: `app/core/security.py`
- **Action**: Validate JWT token
- **Result**: User object with id, roles, unit_id

### What? (Authorization)

- **Where**: `app/services/resource_service.py`
- **Action**: Check user permissions
- **Result**: Allow or deny access

### Which? (Data Filtering)

- **Where**: `app/repositories/resource_repo.py`
- **Action**: Apply filters to SQL query
- **Result**: Only authorized resources returned

## Example Scenarios

### Regular User

```python
User: {roles: ["user"], unit_id: "ENAC"}
Filters: {unit_id: "ENAC", visibility: ["public", "unit"]}
SQL: WHERE unit_id = 'ENAC' AND visibility IN ('public', 'unit')
```

### Admin

```python
User: {roles: ["admin"], unit_id: "ENAC"}
Filters: {unit_id: "ENAC"}
SQL: WHERE unit_id = 'ENAC'
```

### Superuser

```python
User: {roles: ["admin"], is_superuser: true}
Filters: {}
SQL: (no WHERE clause - see all)
```

### Insufficient Permissions

```python
User: {roles: [], unit_id: "ENAC"}
Service: raise PermissionDenied()
Response: 403 Forbidden
```

## Key Concepts

### Fail Secure

When permissions are unclear or missing, deny access. Better to be too
restrictive than too permissive.

### Filter at Database Level

Apply filters in SQL queries, not in Python code. This is more
efficient and secure.

```python
# Good: Filter in database
filters = {"unit_id": user.unit_id}
resources = repo.get_resources(db, filters=filters)

# Bad: Filter in Python
all_resources = repo.get_all(db)
resources = [r for r in all_resources if r.unit_id == user.unit_id]
```

### Explicit Dependencies

FastAPI dependency injection makes dependencies visible:

```python
def endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    # Dependencies are clear in signature
```

## Common Patterns

### Create Resource

```
POST /api/v1/resources
    ↓
[API] Validate ResourceCreate schema
    ↓
[Service] Check create permission, add owner_id
    ↓
[Repository] INSERT into database
    ↓
[Response] Return created resource
```

### Update Resource

```
PATCH /api/v1/resources/{id}
    ↓
[API] Extract id, validate update schema
    ↓
[Service] Check ownership or admin role
    ↓
[Repository] UPDATE database
    ↓
[Response] Return updated resource
```

### Delete Resource

```
DELETE /api/v1/resources/{id}
    ↓
[API] Extract id
    ↓
[Service] Check ownership or admin role
    ↓
[Repository] DELETE from database
    ↓
[Response] 204 No Content
```

## Summary

Requests flow through distinct layers: API validates, services check
permissions, repositories query data. Each layer has one job and passes
results to the next layer.

Authorization happens in the service layer by building filters based on
user context. Repositories apply these filters at the database level
for efficiency and security.

When adding features, follow the layer sequence and never skip layers.
