# Backend Overview

This guide covers the FastAPI backend for CO2 emissions tracking.
Use it to set up your local environment, understand the API
structure, and deploy to production. The backend uses PostgreSQL
for data persistence, OIDC for authentication, and Celery for
asynchronous tasks.

Read this if you need to set up the backend locally, understand
how the API works, or deploy to production.

For deeper architectural details, see:

- [Architecture](02-ARCHITECTURE.md) - Layer patterns
- [File Structure](03-FILE_STRUCTURE.md) - Code organization
- [Request Flow](05-REQUEST_FLOW.md) - Request lifecycle

## Quick Start

Start all services with Docker Compose:

```bash
cd backend
make docker-up
```

The API runs at http://localhost:8000. View interactive docs at
http://localhost:8000/docs.

Stop services with:

```bash
make docker-down
```

### Local Development Without Docker

Install dependencies and configure your environment:

```bash
make install
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY, OIDC_* variables
```

Run migrations and start the server:

```bash
make db-migrate
make run
```

Requires Python 3.11+ and PostgreSQL 15+.

## Architecture Overview

The backend uses a layered architecture with clear separation of
concerns. Each layer handles one responsibility:

| Layer          | Location            | Purpose                        |
| -------------- | ------------------- | ------------------------------ |
| **API**        | `app/api/`          | HTTP routing, request handling |
| **Service**    | `app/services/`     | Business logic, authorization  |
| **Repository** | `app/repositories/` | Database queries               |
| **Models**     | `app/models/`       | SQLAlchemy ORM schemas         |
| **Schemas**    | `app/schemas/`      | Pydantic validation            |

Authorization happens in the service layer. Repositories are
policy-agnostic and receive filters from services.

See [Architecture](02-ARCHITECTURE.md) for complete layer details.

## Key API Endpoints

Visit http://localhost:8000/docs for the complete OpenAPI
specification. Main endpoint groups:

**Authentication**

- `POST /api/v1/auth/login` - Initiate OIDC login
- `GET /api/v1/users/me` - Current user profile

**Laboratory Management**

- `GET /api/v1/labs` - List labs
- `POST /api/v1/labs` - Create lab
- `PUT /api/v1/labs/{id}` - Update lab
- `DELETE /api/v1/labs/{id}` - Delete lab

**Data Import**

- `POST /api/v1/labs/{id}/imports` - Upload CSV
- `GET /api/v1/imports/{id}/status` - Check status

**Reporting**

- `GET /api/v1/reports/{lab_id}` - Generate report

## Development Workflow

### Running Tests

Run all tests with coverage:

```bash
make test
pytest tests/test_resources.py -v  # Specific file
```

Coverage reports appear in `htmlcov/index.html`.

### Code Quality

Format and lint your code:

```bash
make format     # Format with Ruff
make lint       # Check with ruff + mypy
```

### Database Migrations

Manage schema changes with Alembic:

```bash
make db-revision message="Add user preferences"
make db-migrate     # Apply migrations
make db-downgrade   # Rollback one step
```

## Configuration

Copy `.env.example` to `.env` and set these variables:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/co2calculator

# Security (generate: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OIDC Authentication
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret

# Background Tasks
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

For production: set `DEBUG=false`, use strong `SECRET_KEY`, and
restrict `CORS_ORIGINS` to your frontend domain.

## Background Processing

Celery handles long-running tasks with Redis as message broker:

```bash
make celery-worker  # Start worker
make celery-beat    # Start scheduler
make celery-flower  # Web monitoring UI
```

Tasks include CSV import processing, emission calculations,
report generation, and email notifications.

## Authentication & Authorization

### Authentication Flow (OIDC + JWT)

1. Frontend redirects user to Microsoft Entra ID
2. User authenticates with EPFL credentials
3. Backend validates OIDC token and extracts claims
4. Backend issues JWT for subsequent requests
5. Frontend includes JWT in `Authorization: Bearer <token>`

### Authorization (RBAC)

- **Roles**: `admin`, `lab_manager`, `lab_member`, `viewer`
- **Permissions**: Checked in service layer before data access
- **Resource ownership**: Users access only their labs (unless admin)

Authorization uses in-code RBAC for simplicity rather than Open
Policy Agent.

## Security Features

- **Input Validation**: Pydantic schemas on all endpoints
- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized
  queries
- **XSS Prevention**: JSON-only responses
- **Rate Limiting**: Configurable per endpoint
- **Authentication Required**: All endpoints except `/health`
  and `/docs`

CSRF protection is not needed (stateless JWT, no cookies).

## Troubleshooting

### Database Connection Issues

Check if PostgreSQL is running:

```bash
docker-compose ps postgres
docker-compose logs postgres
psql $DATABASE_URL -c "SELECT 1;"
```

### Background Task Failures

View worker logs:

```bash
docker-compose logs celery-worker
redis-cli -h localhost -p 6379 LLEN celery
```

### Enable Debug Logging

Set in `.env`:

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

View logs:

```bash
docker-compose logs -f backend
```

## Production Deployment

Critical checklist:

1. Set `DEBUG=false`
2. Generate secure `SECRET_KEY`: `openssl rand -hex 32`
3. Rotate database credentials regularly
4. Restrict `CORS_ORIGINS` to your frontend domain
5. Use Gunicorn with Uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Performance Optimization

Applied optimizations:

- **Connection Pooling**: SQLAlchemy pool (size: 20, overflow: 10)
- **Query Optimization**: Eager loading to avoid N+1 queries
- **Caching**: Redis for frequently accessed data
- **Async Operations**: FastAPI async endpoints for I/O tasks
- **Background Jobs**: Celery offloads long operations

## Next Steps

### For New Developers

1. Complete Quick Start above
2. Read [Architecture](02-ARCHITECTURE.md) for layer patterns
3. Study [Request Flow](05-REQUEST_FLOW.md) for request lifecycle
4. Explore [File Structure](03-FILE_STRUCTURE.md) for navigation

### For API Consumers

1. Start server: `make docker-up`
2. Open http://localhost:8000/docs
3. Test endpoints with Swagger UI

### External Documentation

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Celery](https://docs.celeryq.dev/)
- [Pydantic](https://docs.pydantic.dev/)

## Summary

FastAPI backend with layered architecture. Start with `make docker-up`,
explore API at `/docs`. Authorization in service layer, database
queries in repositories. Celery handles background tasks. See
[Architecture](02-ARCHITECTURE.md) for details.
