# Request Flow Visualization

## 🔄 Complete Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATION                           │
│  (Browser / Mobile App / API Consumer)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ GET /api/v1/resources
                             │ Authorization: Bearer <JWT>
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     1. API LAYER (FastAPI)                           │
│  File: app/api/v1/resources.py                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ @router.get("/resources")                                      │ │
│  │ def list_resources(                                            │ │
│  │     db: Session = Depends(get_db),              ← Dependencies │ │
│  │     user: User = Depends(get_current_active_user)             │ │
│  │ )                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Validate JWT & Extract User
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 2. SECURITY MIDDLEWARE                               │
│  File: app/core/security.py                                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ decode_jwt(token)                                              │ │
│  │ ↓                                                              │ │
│  │ get_user_by_id(user_id)                                        │ │
│  │ ↓                                                              │ │
│  │ User(id="user@epfl.ch", roles=["user"], unit_id="ENAC")       │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Pass User Object
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              3. SERVICE LAYER (Business Logic)                       │
│  File: app/services/resource_service.py                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ def list_resources(db, user):                                  │ │
│  │                                                                │ │
│  │   # Build OPA input                                            │ │
│  │   input_data = {                                               │ │
│  │     "action": "read",                                          │ │
│  │     "user": {                                                  │ │
│  │       "id": "user@epfl.ch",                                    │ │
│  │       "roles": ["user"],                                       │ │
│  │       "unit_id": "ENAC"                                        │ │
│  │     }                                                           │ │
│  │   }                                                            │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Query OPA
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   4. OPA CLIENT                                      │
│  File: app/core/opa_client.py                                       │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ POST http://opa:8181/v1/data/authz/resource/list              │ │
│  │                                                                │ │
│  │ {                                                              │ │
│  │   "input": {                                                   │ │
│  │     "action": "read",                                          │ │
│  │     "user": {...}                                              │ │
│  │   }                                                            │ │
│  │ }                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTP POST
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                5. OPEN POLICY AGENT (OPA)                            │
│  File: app/policies/resource_policy.rego                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ package authz.resource                                         │ │
│  │                                                                │ │
│  │ # Evaluate: Can this user read resources?                     │ │
│  │ allow if {                                                     │ │
│  │   input.action == "read"                                       │ │
│  │   "user" in input.user.roles                                  │ │
│  │ }                                                              │ │
│  │                                                                │ │
│  │ # Return filters based on user context                        │ │
│  │ filters := {                                                   │ │
│  │   "unit_id": input.user.unit_id,        # ENAC                │ │
│  │   "visibility": ["public", "unit"]      # Not private         │ │
│  │ }                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Return Decision
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   OPA RESPONSE                                       │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ {                                                              │ │
│  │   "result": {                                                  │ │
│  │     "allow": true,                                             │ │
│  │     "filters": {                                               │ │
│  │       "unit_id": "ENAC",                                       │ │
│  │       "visibility": ["public", "unit"]                         │ │
│  │     }                                                           │ │
│  │   }                                                            │ │
│  │ }                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Parse Decision
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              6. SERVICE LAYER (Apply Filters)                        │
│  File: app/services/resource_service.py                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ decision = query_opa(...)                                      │ │
│  │                                                                │ │
│  │ if not decision.get("allow"):                                  │ │
│  │     return []  # Access denied                                 │ │
│  │                                                                │ │
│  │ filters = decision.get("filters", {})                          │ │
│  │ # filters = {"unit_id": "ENAC", "visibility": [...]}          │ │
│  │                                                                │ │
│  │ resources = resource_repo.get_resources(db, filters=filters)   │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Call Repository
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│               7. REPOSITORY LAYER (Data Access)                      │
│  File: app/repositories/resource_repo.py                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ def get_resources(db, filters):                                │ │
│  │     query = db.query(Resource)                                 │ │
│  │                                                                │ │
│  │     # Apply filters from OPA                                   │ │
│  │     for key, value in filters.items():                         │ │
│  │         if key == "unit_id":                                   │ │
│  │             query = query.filter(Resource.unit_id == "ENAC")   │ │
│  │         if key == "visibility":                                │ │
│  │             query = query.filter(                              │ │
│  │                 Resource.visibility.in_(["public", "unit"])    │ │
│  │             )                                                   │ │
│  │                                                                │ │
│  │     return query.all()                                         │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ SQL Query
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    8. DATABASE (PostgreSQL)                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ SELECT * FROM resources                                        │ │
│  │ WHERE unit_id = 'ENAC'                                         │ │
│  │   AND visibility IN ('public', 'unit')                         │ │
│  │                                                                │ │
│  │ Results:                                                       │ │
│  │ [                                                              │ │
│  │   {id: 1, name: "Resource A", unit_id: "ENAC", ...},          │ │
│  │   {id: 2, name: "Resource B", unit_id: "ENAC", ...},          │ │
│  │ ]                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Return Rows
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│               9. SCHEMA LAYER (Serialization)                        │
│  File: app/schemas/resource.py                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ class ResourceRead(BaseModel):                                 │ │
│  │     id: int                                                    │ │
│  │     name: str                                                  │ │
│  │     unit_id: str                                               │ │
│  │     ...                                                        │ │
│  │                                                                │ │
│  │ # Convert SQLAlchemy models to Pydantic                        │ │
│  │ [ResourceRead.from_orm(r) for r in resources]                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ JSON Response
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    10. HTTP RESPONSE                                 │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ HTTP/1.1 200 OK                                                │ │
│  │ Content-Type: application/json                                 │ │
│  │                                                                │ │
│  │ [                                                              │ │
│  │   {                                                            │ │
│  │     "id": 1,                                                   │ │
│  │     "name": "Resource A",                                      │ │
│  │     "unit_id": "ENAC",                                         │ │
│  │     "visibility": "unit",                                      │ │
│  │     "owner_id": "owner@epfl.ch",                               │ │
│  │     "created_at": "2025-10-29T10:00:00Z"                       │ │
│  │   },                                                           │ │
│  │   {                                                            │ │
│  │     "id": 2,                                                   │ │
│  │     "name": "Resource B",                                      │ │
│  │     "unit_id": "ENAC",                                         │ │
│  │     "visibility": "public"                                     │ │
│  │   }                                                            │ │
│  │ ]                                                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

```

## 🔐 Authorization Decision Points

### Point 1: Authentication (Who?)

- **Where**: `app/core/security.py`
- **What**: Validates JWT token
- **Result**: User object with id, roles, unit_id

### Point 2: Authorization (What?)

- **Where**: `app/services/resource_service.py` → OPA
- **What**: Queries policy with user context
- **Result**: `{ allow: true/false, filters: {...} }`

### Point 3: Data Filtering (Which?)

- **Where**: `app/repositories/resource_repo.py`
- **What**: Applies filters to SQL query
- **Result**: Only authorized resources returned

## 📊 Key Concepts

### 1. **Fail Closed Security**

```
OPA Unavailable → deny = true → return []
OPA Error       → deny = true → return []
OPA allow=false → return []
OPA allow=true  → proceed with filters
```

### 2. **Filter-Based Authorization**

```python
# Instead of: Load all → Filter in Python (inefficient)
all_resources = db.query(Resource).all()
filtered = [r for r in all_resources if can_access(user, r)]

# We do: Filter in database (efficient)
filters = get_filters_from_opa(user)
resources = db.query(Resource).filter_by(**filters).all()
```

### 3. **Separation of Concerns**

```
API        → HTTP concerns (validation, serialization)
Service    → Business logic + authorization
Repository → Database queries (no auth logic)
Policy     → Authorization rules (in Rego)
```

## 🎯 Example Scenarios

### Scenario 1: Regular User

```
User: { roles: ["user"], unit_id: "ENAC" }
OPA:  { allow: true, filters: { unit_id: "ENAC", visibility: ["public", "unit"] } }
SQL:  WHERE unit_id = 'ENAC' AND visibility IN ('public', 'unit')
```

### Scenario 2: Admin

```
User: { roles: ["admin"], unit_id: "ENAC" }
OPA:  { allow: true, filters: { unit_id: "ENAC" } }
SQL:  WHERE unit_id = 'ENAC'
```

### Scenario 3: Superuser

```
User: { roles: ["admin"], is_superuser: true }
OPA:  { allow: true, filters: {} }
SQL:  (no WHERE clause - see all)
```

### Scenario 4: Insufficient Permissions

```
User: { roles: [], unit_id: "ENAC" }
OPA:  { allow: false, reason: "Insufficient permissions" }
API:  return []
```

## 🚀 Performance Considerations

### Database Query Efficiency

✅ Filters applied at database level (fast)
❌ Loading all data then filtering in Python (slow)

### OPA Caching

- OPA decisions can be cached (Redis)
- Cache key: hash(user_context + action + resource_type)
- TTL: 5-60 seconds

### Connection Pooling

- SQLAlchemy connection pool
- OPA HTTP client connection reuse

## 🧪 Testing Strategy

### Unit Tests

- Mock OPA responses
- Test service logic
- Test repository queries

### Integration Tests

- Real OPA server
- Test database
- Full request flow

### Policy Tests

```bash
opa test app/policies/
```

---

This visualization shows exactly how authorization flows through the system!
