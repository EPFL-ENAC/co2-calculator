# Backend Architecture

This document describes the layered architecture of the CO2 Calculator
backend. The system uses FastAPI with clean separation between API
handling, business logic, and data access. Read this to understand how
layers interact and where to place new code.

## Layer Overview

The backend uses five distinct layers, each with a single
responsibility:

```
┌─────────────────────────────────────┐
│     API Layer (app/api/)            │
│     HTTP routing, validation        │
├─────────────────────────────────────┤
│     Service Layer (app/services/)   │
│     Business logic, authorization   │
├─────────────────────────────────────┤
│  Repository Layer (app/repositories/)│
│     Database queries, filters       │
├─────────────────────────────────────┤
│     Models Layer (app/models/)      │
│     SQLAlchemy ORM definitions      │
└─────────────────────────────────────┘

      Cross-Cutting (app/core/)
      Config, Security, Logging
```

## API Layer

**Location**: `app/api/`

**Purpose**: Handle HTTP requests and responses

Handle HTTP-specific concerns like routing, validation, and
serialization. Extract user context from JWT tokens and pass to
services.

**Example**:

```python
@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    return resource_service.list_resources(db, user)
```

**Key Files**:

- `router.py` - Aggregates all API routers
- `deps.py` - Reusable dependencies (get_db, get_current_user)
- `v1/resources.py` - Resource CRUD endpoints
- `v1/users.py` - User endpoints

## Service Layer

**Location**: `app/services/`

**Purpose**: Implement business logic and authorization

Orchestrate repository calls, apply business rules, and check
permissions. Authorization happens here before data access.

**Example**:

```python
def list_resources(db: Session, user: User):
    # Check permissions
    if not user.has_permission("resource.read"):
        raise PermissionDenied()

    # Build filters based on user context
    filters = get_filters_for_user(user)

    # Query database with filters
    return resource_repo.get_resources(db, filters=filters)
```

**Key Files**:

- `user_service.py` - User management logic
- `resource_service.py` - Resource logic with authorization

## Repository Layer

**Location**: `app/repositories/`

**Purpose**: Execute database queries

Handle pure data access without business logic. Accept filters from
services and apply them to queries. No authorization logic here.

**Example**:

```python
def get_resources(db: Session, filters: dict):
    query = db.query(Resource)

    # Apply filters from service layer
    for key, value in filters.items():
        query = query.filter(getattr(Resource, key) == value)

    return query.all()
```

**Key Files**:

- `user_repo.py` - User database operations
- `resource_repo.py` - Resource database operations

## Models Layer

**Location**: `app/models/`

**Purpose**: Define database schema

Define SQLAlchemy ORM models that map to database tables. Specify
relationships and constraints.

**Example**:

```python
class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    unit_id = Column(String, index=True)
    owner_id = Column(String, ForeignKey("users.id"))
    visibility = Column(String, default="private")
    data = Column(JSONB, default=dict)
```

**Key Files**:

- `user.py` - User model
- `resource.py` - Resource model

## Schemas Layer

**Location**: `app/schemas/`

**Purpose**: Validate API input/output

Define Pydantic models for request/response validation and
serialization. Provide automatic API documentation.

**Example**:

```python
class ResourceCreate(BaseModel):
    name: str
    unit_id: str
    visibility: str = "private"
    data: Dict[str, Any] = {}

class ResourceRead(BaseModel):
    id: int
    name: str
    created_at: datetime
```

**Key Files**:

- `user.py` - User schemas
- `resource.py` - Resource schemas

## Core Infrastructure

**Location**: `app/core/`

**Purpose**: Cross-cutting concerns

Handle configuration, security, and logging across the application.

**Key Files**:

- `config.py` - Environment configuration (Pydantic Settings)
- `security.py` - JWT encoding/decoding, password hashing
- `logging.py` - Centralized logging setup

## Request Flow Example

Here's how a typical request flows through the layers:

```
GET /api/v1/resources
    ↓
[API Layer]
    - Validate JWT token
    - Extract User object
    - Call service layer
    ↓
[Service Layer]
    - Check user permissions
    - Build filters based on user context
    - Call repository
    ↓
[Repository Layer]
    - Build SQL query
    - Apply filters
    - Execute query
    ↓
[Database]
    - Return matching rows
    ↓
[Schema Layer]
    - Serialize to JSON
    ↓
HTTP Response
```

## Authorization Model

Authorization uses Role-Based Access Control (RBAC) implemented in
Python code.

### Roles

- `admin` - Full access to all resources in their unit
- `lab_manager` - Manage labs and their data
- `lab_member` - Read/write access to assigned labs
- `viewer` - Read-only access

### Permission Checks

Permissions are checked in the service layer:

```python
def update_resource(db: Session, resource_id: int, user: User):
    resource = resource_repo.get_by_id(db, resource_id)

    # Check ownership or admin role
    if resource.owner_id != user.id and not user.is_admin:
        raise PermissionDenied("Cannot update this resource")

    # Proceed with update
    return resource_repo.update(db, resource_id, data)
```

### Data Filtering

Users see only resources they have access to:

```python
def get_filters_for_user(user: User) -> dict:
    if user.is_superuser:
        return {}  # No filters = see all

    if user.is_admin:
        return {"unit_id": user.unit_id}

    # Regular users
    return {
        "unit_id": user.unit_id,
        "visibility": ["public", "unit"]
    }
```

## Design Principles

### Separation of Concerns

Each layer has one job. API handles HTTP, services handle logic,
repositories handle data. Never skip layers.

### Explicit Dependencies

Use FastAPI dependency injection to make dependencies clear:

```python
def endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    # Dependencies are explicit
```

### Fail Secure

When in doubt, deny access. Better to be too restrictive than too
permissive.

### Testability

Each layer can be tested independently with mocks. Services mock
repositories, APIs mock services.

## Adding New Features

Follow this sequence when adding features:

1. **Define Model** in `app/models/` - Database schema
2. **Create Schemas** in `app/schemas/` - API validation
3. **Build Repository** in `app/repositories/` - Data access
4. **Implement Service** in `app/services/` - Business logic
5. **Add API Endpoints** in `app/api/v1/` - HTTP interface
6. **Write Tests** for each layer

Keep layers clean and respect the separation.

## Common Patterns

### Create Pattern

```python
# API Layer
@router.post("/resources")
def create_resource(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    return resource_service.create(db, data, user)

# Service Layer
def create(db: Session, data: ResourceCreate, user: User):
    # Check permissions
    if not user.has_permission("resource.create"):
        raise PermissionDenied()

    # Add user context
    data_dict = data.dict()
    data_dict["owner_id"] = user.id
    data_dict["unit_id"] = user.unit_id

    return resource_repo.create(db, data_dict)

# Repository Layer
def create(db: Session, data: dict):
    resource = Resource(**data)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource
```

### List with Filtering Pattern

```python
# API Layer
@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    return resource_service.list(db, user)

# Service Layer
def list(db: Session, user: User):
    filters = get_filters_for_user(user)
    return resource_repo.list(db, filters=filters)

# Repository Layer
def list(db: Session, filters: dict):
    query = db.query(Resource)
    for key, value in filters.items():
        if isinstance(value, list):
            query = query.filter(getattr(Resource, key).in_(value))
        else:
            query = query.filter(getattr(Resource, key) == value)
    return query.all()
```

## Summary

The backend uses a five-layer architecture with clear separation of
concerns. API handles HTTP, services implement business logic and
authorization, repositories handle data access, models define schema,
and schemas validate I/O.

Authorization happens in the service layer using RBAC. Repositories
receive filters and are policy-agnostic.

When adding features, follow the layer sequence: model → schema →
repository → service → API. Test each layer independently.
