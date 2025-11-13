# Backend File Structure

This document provides a guide to navigating the backend codebase. Use
it to find where specific functionality lives and understand the
project layout.

## Directory Tree

```
backend/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── db.py                # Database session management
│   │
│   ├── api/                 # HTTP Endpoints
│   │   ├── deps.py          # Dependency injection
│   │   ├── router.py        # Main router
│   │   └── v1/              # API version 1
│   │       ├── resources.py
│   │       └── users.py
│   │
│   ├── core/                # Infrastructure
│   │   ├── config.py        # Settings
│   │   ├── security.py      # JWT & passwords
│   │   └── logging.py
│   │
│   ├── models/              # Database Models
│   │   ├── user.py
│   │   └── resource.py
│   │
│   ├── schemas/             # Pydantic Schemas
│   │   ├── user.py
│   │   └── resource.py
│   │
│   ├── repositories/        # Data Access
│   │   ├── user_repo.py
│   │   └── resource_repo.py
│   │
│   └── services/            # Business Logic
│       ├── user_service.py
│       └── resource_service.py
│
├── tests/                   # Test Files
├── alembic/                 # Database Migrations
├── .env.example             # Environment template
├── requirements.txt         # Dependencies
├── Dockerfile              # Container image
└── Makefile                # Dev commands
```

## Key Files

### Entry Points

- **`app/main.py`** - Application initialization, middleware setup,
  router configuration
- **`app/api/router.py`** - Aggregates all API routers
- **`app/core/config.py`** - Environment configuration

### Core Infrastructure

- **`app/core/security.py`** - JWT token handling, password hashing
- **`app/core/logging.py`** - Logging configuration
- **`app/db.py`** - Database session and Base model

### Dependency Injection

- **`app/api/deps.py`** - Reusable dependencies like `get_db` and
  `get_current_active_user`

## Layer Structure

```
┌──────────────────────────┐
│    API Layer             │  app/api/v1/*.py
├──────────────────────────┤
│    Service Layer         │  app/services/*_service.py
├──────────────────────────┤
│    Repository Layer      │  app/repositories/*_repo.py
├──────────────────────────┤
│    Models Layer          │  app/models/*.py
└──────────────────────────┘
```

## Finding Functionality

### Authentication & Authorization

- JWT handling: `app/core/security.py`
- User extraction: `app/api/deps.py` (get_current_user)
- Permission checks: `app/services/*_service.py`

### Database Operations

- Schema definitions: `app/models/*.py`
- Queries: `app/repositories/*_repo.py`
- Migrations: `alembic/versions/*.py`

### API Endpoints

- User endpoints: `app/api/v1/users.py`
- Resource endpoints: `app/api/v1/resources.py`
- Main router: `app/api/router.py`

### Business Logic

- User logic: `app/services/user_service.py`
- Resource logic: `app/services/resource_service.py`

### Validation

- Request/response schemas: `app/schemas/*.py`

## Quick Commands

```bash
# Development
make install    # Install dependencies
make run        # Start dev server
make test       # Run tests

# Docker
make docker-up    # Start all services
make docker-down  # Stop services

# Database
make db-migrate     # Run migrations
make db-revision    # Create migration

# Code Quality
make format    # Format code
make lint      # Check code
```

## Learning Path

Start with these files in order:

1. **`app/main.py`** - Understand app initialization
2. **`app/core/config.py`** - See configuration options
3. **`app/api/router.py`** - See available endpoints
4. **`app/services/resource_service.py`** - Study business logic
5. **`app/repositories/resource_repo.py`** - See data access

## Adding New Features

When adding a new feature, create files in this order:

1. **Model**: `app/models/feature.py`
2. **Schema**: `app/schemas/feature.py`
3. **Repository**: `app/repositories/feature_repo.py`
4. **Service**: `app/services/feature_service.py`
5. **API**: `app/api/v1/features.py`
6. **Tests**: `tests/test_feature_*.py`

## Testing Structure

```
tests/
├── conftest.py           # Test fixtures
├── test_api/             # API endpoint tests
├── test_services/        # Service layer tests
└── test_repositories/    # Repository tests
```

## Summary

The backend follows a layered structure with clear file organization.
API endpoints live in `app/api/`, business logic in `app/services/`,
data access in `app/repositories/`, and models in `app/models/`.

Start exploring from `app/main.py`, then dive into specific layers as
needed.
