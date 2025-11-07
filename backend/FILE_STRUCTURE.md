# Backend File Structure Summary

This document provides a complete overview of the implemented FastAPI backend architecture.

## 📂 Complete File Tree

```
backend/
├── app/
│   ├── __init__.py                    # Package initialization
│   ├── main.py                        # FastAPI app entrypoint (★ START HERE)
│   ├── db.py                          # Database session & Base model
│   │
│   ├── api/                           # 🌐 API Layer - HTTP Endpoints
│   │   ├── __init__.py
│   │   ├── deps.py                    # Dependency injection helpers
│   │   ├── router.py                  # Main router aggregator
│   │   └── v1/                        # API version 1
│   │       ├── __init__.py
│   │       ├── resources.py           # Resource CRUD endpoints
│   │       └── users.py               # User & auth endpoints
│   │
│   ├── core/                          # ⚙️ Core Infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic settings (env vars)
│   │   ├── security.py                # JWT auth & password hashing
│   │   ├── opa_client.py              # OPA HTTP client (★ AUTHORIZATION)
│   │   └── logging.py                 # Logging configuration
│   │
│   ├── models/                        # 🗄️ Database Models (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── user.py                    # User table model
│   │   └── resource.py                # Resource table model
│   │
│   ├── schemas/                       # 📋 API Schemas (Pydantic)
│   │   ├── __init__.py
│   │   ├── user.py                    # User I/O schemas
│   │   └── resource.py                # Resource I/O schemas
│   │
│   ├── repositories/                  # 💾 Data Access Layer
│   │   ├── __init__.py
│   │   ├── user_repo.py               # User DB operations
│   │   └── resource_repo.py           # Resource DB operations (★ FILTERS)
│   │
│   ├── services/                      # 🧠 Business Logic Layer
│   │   ├── __init__.py
│   │   ├── user_service.py            # User business logic
│   │   └── resource_service.py        # Resource logic + OPA (★ KEY FILE)
│   │
│   └── policies/                      # 🔐 OPA Policies (Rego)
│       ├── README.md                  # Policy documentation
│       └── resource_policy.rego       # Authorization rules (★ POLICIES)
│
├── tests/                             # 🧪 Test Files
│   ├── conftest.py                    # Test configuration & fixtures
│   └── test_resource_service.py       # Example service tests
│
├── .env.example                       # Example environment variables
├── .gitignore                         # Git ignore patterns
├── ARCHITECTURE.md                    # 📘 Architecture documentation (★ READ THIS)
├── REQUEST_FLOW.md                    # 🔄 Request flow visualization
├── README.md                          # Quick start guide
├── requirements.txt                   # Python dependencies
├── Dockerfile                         # Docker image definition
├── docker-compose.yml                 # Local dev environment
└── Makefile                           # Development commands

```

## 🎯 Key Files Explained

### ★ Must-Read Files

1. **`ARCHITECTURE.md`** - Complete architecture documentation
2. **`REQUEST_FLOW.md`** - Visual request flow diagram
3. **`app/main.py`** - Application entrypoint
4. **`app/services/resource_service.py`** - Authorization integration example
5. **`app/policies/resource_policy.rego`** - Policy definitions

### Entry Points

| File                 | Purpose     | When to Use                        |
| -------------------- | ----------- | ---------------------------------- |
| `app/main.py`        | FastAPI app | Start server, configure middleware |
| `app/api/router.py`  | API routes  | Add new endpoint groups            |
| `app/core/config.py` | Settings    | Configure environment variables    |

## 📊 Layer Structure

```
┌─────────────────────────────────────────────────────────┐
│                    API LAYER                             │
│  (app/api/) - HTTP endpoints, validation                │
├─────────────────────────────────────────────────────────┤
│                  SERVICE LAYER                           │
│  (app/services/) - Business logic + OPA integration     │
├─────────────────────────────────────────────────────────┤
│                REPOSITORY LAYER                          │
│  (app/repositories/) - Database queries with filters    │
├─────────────────────────────────────────────────────────┤
│                  MODELS LAYER                            │
│  (app/models/) - SQLAlchemy ORM models                  │
└─────────────────────────────────────────────────────────┘

      ┌───────────────────────────────────┐
      │    CROSS-CUTTING CONCERNS         │
      │  (app/core/)                      │
      │  - Config                         │
      │  - Security                       │
      │  - OPA Client                     │
      │  - Logging                        │
      └───────────────────────────────────┘
```

## 🔄 Data Flow Summary

```
HTTP Request
    ↓
[API Layer] - Validates request, extracts JWT
    ↓
[Security] - Decodes JWT → User object
    ↓
[Service Layer] - Queries OPA with user context
    ↓
[OPA] - Returns { allow: true/false, filters: {...} }
    ↓
[Repository Layer] - Applies filters to SQL query
    ↓
[Database] - Returns matching rows
    ↓
[Schema Layer] - Serializes to JSON
    ↓
HTTP Response
```

## 🛠️ Quick Commands

```bash
# Development
make install              # Install dependencies
make run                  # Start dev server
make test                 # Run tests

# Docker
make docker-up            # Start all services
make docker-down          # Stop all services
make docker-logs          # View logs

# Database
make db-migrate           # Run migrations
make init-db              # Initialize DB (dev)

# OPA
make opa-test            # Test policies
make opa-run             # Run OPA locally

# Code Quality
make format              # Format code
make lint                # Lint code
```

## 📝 File Purposes at a Glance

### Core Files

- `config.py` - Environment configuration (DB, OPA, JWT settings)
- `security.py` - JWT encoding/decoding, password hashing
- `opa_client.py` - HTTP client for querying OPA
- `logging.py` - Centralized logging setup

### API Files

- `deps.py` - Reusable dependencies (get_db, get_current_user)
- `router.py` - Aggregates all API routers
- `resources.py` - Resource CRUD endpoints
- `users.py` - User management & authentication

### Data Layer

- `models/user.py` - User database table
- `models/resource.py` - Resource database table
- `schemas/user.py` - User request/response validation
- `schemas/resource.py` - Resource request/response validation

### Business Logic

- `repositories/user_repo.py` - User DB queries
- `repositories/resource_repo.py` - Resource DB queries (applies filters)
- `services/user_service.py` - User business logic
- `services/resource_service.py` - Resource logic + OPA integration

### Authorization

- `policies/resource_policy.rego` - Authorization rules in Rego
- `policies/README.md` - Policy documentation

## 🎓 Learning Path

### For New Developers

1. **Start with**: `README.md` (quick start)
2. **Understand**: `ARCHITECTURE.md` (system design)
3. **Visualize**: `REQUEST_FLOW.md` (how requests flow)
4. **Explore**: `app/main.py` (app initialization)
5. **Study**: `app/services/resource_service.py` (OPA integration)
6. **Learn**: `app/policies/resource_policy.rego` (authorization rules)

### For API Consumers

1. Start server: `make docker-up`
2. Visit: http://localhost:8000/docs
3. Read API documentation
4. Test endpoints with Swagger UI

### For Policy Authors

1. Read: `app/policies/README.md`
2. Edit: `app/policies/resource_policy.rego`
3. Test: `make opa-test`
4. Deploy: Restart services

## 🔐 Security Architecture

### Authentication Flow

```
Login → Verify Password → Create JWT → Return Token
```

### Authorization Flow

```
Request → Validate JWT → Extract User → Query OPA → Apply Filters → Query DB
```

### Key Security Files

- `app/core/security.py` - Authentication
- `app/core/opa_client.py` - Authorization queries
- `app/policies/*.rego` - Authorization policies

## 🧪 Testing Structure

```
tests/
├── conftest.py                  # Fixtures & test config
├── test_resource_service.py     # Service layer tests
├── test_repositories.py         # Repository tests (add these)
└── test_api.py                  # API endpoint tests (add these)
```

## 📦 Dependencies Overview

### Core Framework

- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy** - ORM
- **Pydantic** - Validation

### Security

- **python-jose** - JWT handling
- **passlib** - Password hashing
- **httpx** - HTTP client (for OPA)

### Development

- **pytest** - Testing
- **black** - Code formatting
- **flake8** - Linting
- **mypy** - Type checking

## 🚀 Deployment Checklist

- [ ] Set `DEBUG=false`
- [ ] Generate secure `SECRET_KEY`
- [ ] Configure production database URL
- [ ] Disallow `CORS_ORIGINS`
- [ ] Deploy OPA alongside backend
- [ ] Set up database migrations
- [ ] Configure logging/monitoring
- [ ] Set up HTTPS/TLS
- [ ] Configure backup strategy

## 💡 Common Tasks

### Add New Endpoint

1. Create route in `app/api/v1/`
2. Add business logic in `app/services/`
3. Add data access in `app/repositories/`
4. Add policy in `app/policies/`

### Add New Model

1. Create model in `app/models/`
2. Create schemas in `app/schemas/`
3. Create repository in `app/repositories/`
4. Create service in `app/services/`
5. Run migration: `make db-revision message="Add model"`

### Modify Authorization

1. Edit `app/policies/*.rego`
2. Test: `make opa-test`
3. Restart OPA service

## 📚 Additional Documentation

- `ARCHITECTURE.md` - Detailed architecture guide
- `REQUEST_FLOW.md` - Visual request flow
- `app/policies/README.md` - Policy documentation
- `README.md` - Quick start guide

## 🤝 Contributing

When adding features:

1. Follow the layered architecture
2. Keep authorization in OPA policies
3. Add tests for new code
4. Update documentation
5. Follow code style (run `make format`)

---

## Summary

This backend implements a **clean, layered architecture** with:

✅ **Clear separation of concerns** (API, Service, Repository, Models)  
✅ **OPA integration** for flexible authorization  
✅ **Type safety** with Pydantic  
✅ **Testable** at every layer  
✅ **Scalable** design  
✅ **Well-documented** code

The key innovation is using **OPA for authorization decisions** while keeping business logic clean and maintainable in Python.

**Start exploring with**: `ARCHITECTURE.md` → `app/main.py` → `app/services/resource_service.py`
