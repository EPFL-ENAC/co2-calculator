# Backend Architecture Documentation

## Overview

This document describes the FastAPI backend architecture for the CO2 Calculator application. The backend implements a clean, layered architecture with Open Policy Agent (OPA) integration for fine-grained authorization.

---

## 📁 File Structure

```
backend/
├── app/
│   ├── __init__.py                 # Package initialization
│   ├── main.py                     # FastAPI application entrypoint
│   ├── db.py                       # Database configuration & session management
│   │
│   ├── api/                        # API Layer (HTTP endpoints)
│   │   ├── __init__.py
│   │   ├── deps.py                 # Dependency injection helpers
│   │   ├── router.py               # Main API router configuration
│   │   └── v1/                     # API version 1
│   │       ├── __init__.py
│   │       ├── resources.py        # Resource endpoints
│   │       └── users.py            # User & auth endpoints
│   │
│   ├── core/                       # Core Infrastructure
│   │   ├── __init__.py
│   │   ├── config.py               # Application settings (Pydantic)
│   │   ├── security.py             # JWT auth & password hashing
│   │   ├── opa_client.py           # OPA HTTP client
│   │   └── logging.py              # Logging configuration
│   │
│   ├── models/                     # Database Models (SQLAlchemy ORM)
│   │   ├── __init__.py
│   │   ├── user.py                 # User model
│   │   └── resource.py             # Resource model
│   │
│   ├── schemas/                    # API Schemas (Pydantic)
│   │   ├── __init__.py
│   │   ├── user.py                 # User request/response schemas
│   │   └── resource.py             # Resource request/response schemas
│   │
│   ├── repositories/               # Data Access Layer
│   │   ├── __init__.py
│   │   ├── user_repo.py            # User database operations
│   │   └── resource_repo.py        # Resource database operations
│   │
│   ├── services/                   # Business Logic Layer
│   │   ├── __init__.py
│   │   ├── user_service.py         # User business logic
│   │   └── resource_service.py     # Resource logic + OPA integration
│   │
│   └── policies/                   # OPA Policy Files (Rego)
│       ├── README.md               # Policy documentation
│       └── resource_policy.rego    # Resource authorization rules
│
├── Makefile                        # Build & dev commands
├── requirements.txt                # Python dependencies
└── docker-compose.yml              # Local development setup
```

---

## 🧩 Layer Responsibilities

### 1. **API Layer** (`app/api/`)

**Purpose**: Handle HTTP requests and responses

**Responsibilities**:

- Define FastAPI routes and endpoints
- Validate request data (via Pydantic schemas)
- Handle HTTP-specific concerns (status codes, headers)
- Dependency injection (auth, database sessions)
- Call service layer for business logic

**Files**:

- `router.py` - Aggregates all API routers
- `deps.py` - Reusable dependencies (get_db, get_current_user)
- `v1/resources.py` - Resource CRUD endpoints
- `v1/users.py` - User management & authentication endpoints

**Example**:

```python
@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    return resource_service.list_resources(db, user)
```

---

### 2. **Core Layer** (`app/core/`)

**Purpose**: Infrastructure and cross-cutting concerns

**Responsibilities**:

- Application configuration
- Security (JWT, password hashing)
- OPA client for authorization
- Logging setup

**Files**:

- `config.py` - Pydantic Settings (environment variables)
- `security.py` - JWT encoding/decoding, password verification
- `opa_client.py` - HTTP client for querying OPA
- `logging.py` - Centralized logging configuration

**Key Features**:

- Settings loaded from `.env` file
- JWT token creation and validation
- OPA query with error handling and fallback
- Structured logging

---

### 3. **Models Layer** (`app/models/`)

**Purpose**: Database schema definition

**Responsibilities**:

- Define SQLAlchemy ORM models
- Specify table relationships
- Add database constraints
- Define model methods

**Files**:

- `user.py` - User table (auth, roles, unit membership)
- `resource.py` - Resource table (with JSONB data)

**Example**:

```python
class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    unit_id = Column(String, index=True, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"))
    visibility = Column(String, default="private")
    data = Column(JSONB, default=dict)
```

---

### 4. **Schemas Layer** (`app/schemas/`)

**Purpose**: Request/response validation and serialization

**Responsibilities**:

- Define Pydantic models for API I/O
- Validate incoming data
- Serialize outgoing data
- Provide API documentation

**Files**:

- `user.py` - User schemas (Create, Update, Read, Token)
- `resource.py` - Resource schemas (Create, Update, Read, List)

**Example**:

```python
class ResourceCreate(BaseModel):
    name: str
    unit_id: str
    visibility: str = "private"
    data: Dict[str, Any] = {}
```

---

### 5. **Repositories Layer** (`app/repositories/`)

**Purpose**: Pure data access (no business logic)

**Responsibilities**:

- Execute database queries
- Apply filters to queries
- CRUD operations
- No authorization logic (that's in services)

**Files**:

- `user_repo.py` - User database operations
- `resource_repo.py` - Resource database operations

**Key Principle**: Repositories are **policy-agnostic**. They receive filters from the service layer and apply them blindly.

**Example**:

```python
def get_resources(db: Session, filters: dict):
    query = db.query(Resource)
    for key, value in filters.items():
        query = query.filter(getattr(Resource, key) == value)
    return query.all()
```

---

### 6. **Services Layer** (`app/services/`)

**Purpose**: Business logic and authorization

**Responsibilities**:

- Orchestrate repository calls
- Query OPA for authorization decisions
- Apply business rules
- Handle errors and exceptions
- Log authorization events

**Files**:

- `user_service.py` - User management logic
- `resource_service.py` - Resource logic with OPA integration

**This is where authorization happens!**

**Example**:

```python
def list_resources(db: Session, user: User):
    # 1. Build OPA input
    input_data = {
        "action": "read",
        "user": {"id": user.id, "roles": user.roles}
    }

    # 2. Query OPA
    decision = query_opa("authz/resource/list", input_data)

    # 3. Check if allowed
    if not decision.get("allow"):
        return []

    # 4. Get filters from OPA
    filters = decision.get("filters", {})

    # 5. Query database with filters
    return resource_repo.get_resources(db, filters=filters)
```

---

### 7. **Policies Layer** (`app/policies/`)

**Purpose**: Authorization rules in Rego

**Responsibilities**:

- Define who can access what
- Determine filters for queries
- Provide deny reasons
- Implement RBAC logic

**Files**:

- `resource_policy.rego` - Resource authorization rules
- `README.md` - Policy documentation

**Key Concepts**:

- **Roles**: `admin`, `unit_admin`, `resource.create`
- **Visibility**: `public`, `private`, `unit`
- **Actions**: `read`, `create`, `update`, `delete`

**Example Policy**:

```rego
# Users can read resources in their unit with "unit" visibility
allow if {
    input.action == "read"
    input.resource.visibility == "unit"
    input.resource.unit_id == input.user.unit_id
}
```

---

## 🔄 Request Flow

Here's how a typical request flows through the system:

### Example: `GET /api/v1/resources`

```
1. HTTP Request
   ↓
   [API Layer: app/api/v1/resources.py]
   - Extract query parameters
   - Validate JWT token → get User object
   - Get database session
   ↓
2. Dependency Injection
   ↓
   [Service Layer: app/services/resource_service.py]
   - Build OPA input with user context
   - Call OPA client
   ↓
3. Authorization Query
   ↓
   [Core Layer: app/core/opa_client.py]
   - HTTP POST to OPA
   - Parse response
   ↓
4. OPA Decision
   ↓
   [External: Open Policy Agent]
   - Evaluate resource_policy.rego
   - Return: { "allow": true, "filters": {...} }
   ↓
5. Apply Filters
   ↓
   [Repository Layer: app/repositories/resource_repo.py]
   - Build SQLAlchemy query
   - Apply filters from OPA
   - Execute query
   ↓
6. Database Query
   ↓
   [Database: PostgreSQL]
   - Return matching rows
   ↓
7. Serialize Response
   ↓
   [Schemas Layer: app/schemas/resource.py]
   - Convert models to Pydantic schemas
   - Return JSON
   ↓
8. HTTP Response
```

---

## 🔐 Authorization Model

### Three Types of Authorization

1. **Authentication** (Who are you?)
   - JWT token validation
   - Handled in `core/security.py`
   - Dependency: `get_current_active_user`

2. **Role-Based Access Control** (What can your role do?)
   - Defined in OPA policies
   - Roles stored in User model
   - Examples: `admin`, `unit_admin`, `resource.create`

3. **Attribute-Based Access Control** (What specific data can you access?)
   - Based on user attributes (unit_id, ownership)
   - OPA returns filters
   - Applied at database query level

### Authorization Decision Flow

```python
# Service Layer
input_data = {
    "action": "read",
    "user": {
        "id": "user@epfl.ch",
        "roles": ["user"],
        "unit_id": "ENAC"
    }
}

decision = query_opa("authz/resource/list", input_data)
# Returns:
# {
#     "allow": true,
#     "filters": {
#         "unit_id": "ENAC",
#         "visibility": ["public", "unit"]
#     }
# }

# Repository applies filters
resources = get_resources(db, filters=decision["filters"])
```

---

## 🎯 Key Design Principles

### 1. **Separation of Concerns**

Each layer has ONE job:

- API → HTTP handling
- Services → Business logic + authorization
- Repositories → Database access
- Policies → Authorization rules

### 2. **Policy-Driven Authorization**

Authorization logic lives in OPA policies (Rego files), not in Python code. This allows:

- Centralized policy management
- Easy policy updates without code changes
- Testable authorization rules
- Potential policy UI in the future

### 3. **Fail Closed**

If OPA is unreachable or returns an error, the default is **deny access**. Security over availability.

### 4. **Explicit Dependencies**

FastAPI dependency injection makes dependencies explicit:

```python
def endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    # Dependencies are clear
```

### 5. **Testability**

Each layer can be tested independently:

- Mock OPA responses in service tests
- Mock database in repository tests
- Integration tests for full flow

---

## 🚀 Running Locally

### Prerequisites

- Python 3.10+
- PostgreSQL
- OPA (Open Policy Agent)

### Setup

1. **Install dependencies**:

```bash
cd backend
pip install -r requirements.txt
```

2. **Configure environment**:

```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start services** (Docker Compose):

```bash
docker-compose up -d
# Starts: PostgreSQL, OPA, Backend
```

4. **Run migrations** (if using Alembic):

```bash
alembic upgrade head
```

5. **Start development server**:

```bash
uvicorn app.main:app --reload
```

6. **Access API**:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- OPA: http://localhost:8181

---

## 🧪 Testing Authorization

### Test OPA Policy Directly

```bash
# Query OPA
curl -X POST http://localhost:8181/v1/data/authz/resource/list \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "read",
      "user": {
        "id": "test@epfl.ch",
        "roles": ["user"],
        "unit_id": "ENAC"
      }
    }
  }'
```

### Test API Endpoint

```bash
# 1. Get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/users/token \
  -d "username=test@epfl.ch&password=password" | jq -r .access_token)

# 2. List resources
curl http://localhost:8000/api/v1/resources \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 Database Schema

### Users Table

```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    full_name VARCHAR,
    unit_id VARCHAR,
    sciper VARCHAR UNIQUE,
    roles VARCHAR[],
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);
```

### Resources Table

```sql
CREATE TABLE resources (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    unit_id VARCHAR NOT NULL,
    owner_id VARCHAR REFERENCES users(id),
    visibility VARCHAR DEFAULT 'private',
    data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Application
APP_NAME=CO2 Calculator API
DEBUG=true
API_VERSION=/api/v1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/co2_calculator

# Security
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OPA
OPA_URL=http://localhost:8181
OPA_ENABLED=true
OPA_TIMEOUT=1.0

# Logging
LOG_LEVEL=INFO
```

---

## 🔄 Alternative: Permissions in Code

If you want to avoid OPA initially, you can implement permissions directly in Python:

**Create `app/core/permissions.py`**:

```python
def get_filters_for_user(user: User, action: str) -> dict:
    """Get database filters based on user permissions."""

    if user.is_superuser:
        return {}  # No filters = see all

    if "admin" in user.roles:
        return {"unit_id": user.unit_id}

    # Regular users see public + unit + own resources
    return {
        "visibility": ["public", "unit"],
        "unit_id": user.unit_id
    }
```

**Update service**:

```python
# Instead of:
decision = query_opa("authz/resource/list", input_data)
filters = decision.get("filters", {})

# Use:
from app.core.permissions import get_filters_for_user
filters = get_filters_for_user(user, "read")
```

This gives you the same layer structure with easier local development.

---

## 📈 Scaling Considerations

### Current Architecture Benefits

- ✅ Clean separation allows independent scaling
- ✅ Stateless API (can run multiple instances)
- ✅ OPA can be deployed as sidecar or centralized
- ✅ Repository pattern allows easy database migration

### Future Enhancements

- **Caching**: Add Redis for OPA decisions
- **Async**: Use async database drivers (SQLAlchemy 2.0)
- **Message Queue**: Add Celery for background tasks
- **API Gateway**: Add Kong or similar for rate limiting
- **Observability**: Add OpenTelemetry for tracing

---

## 🐛 Debugging

### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

### Check OPA Decisions

All OPA queries are logged in the service layer:

```python
    logger.info("OPA ...", extra={"user_id": user.id, "action": "list_resources", "decision": decision, "input_data": input_data})
```

### Disable OPA for Testing

```env
OPA_ENABLED=false
```

This will return `allow=true` for all requests (development only!).

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Open Policy Agent](https://www.openpolicyagent.org/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [JWT](https://jwt.io/)

---

## 🤝 Contributing

When adding new features:

1. **Add model** in `app/models/`
2. **Add schemas** in `app/schemas/`
3. **Add repository** in `app/repositories/`
4. **Add service** in `app/services/` (with OPA integration)
5. **Add API endpoints** in `app/api/v1/`
6. **Add OPA policy** in `app/policies/`
7. **Test** all layers

Keep the layers clean and respect the separation of concerns!

---

## Summary

This backend architecture provides:

- ✅ **Clean layered structure** for maintainability
- ✅ **OPA integration** for flexible authorization
- ✅ **Type safety** with Pydantic
- ✅ **Async-ready** FastAPI
- ✅ **Testable** at every layer
- ✅ **Scalable** design
- ✅ **Well-documented** code

The key innovation is using **OPA for authorization decisions** while keeping business logic in Python. This provides the best of both worlds: flexible policy management with robust application code.
