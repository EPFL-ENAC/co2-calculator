# Backend

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Option 1: Docker Compose (Recommended)

```bash
# Start all services (PostgreSQL, OPA, Backend)
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

The API will be available at:

- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- OPA: http://localhost:8181

### Option 2: Local Development

```bash
# Install dependencies
make install

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Start PostgreSQL (if not using Docker)
# Start OPA (if not using Docker)
# opa run --server --addr :8181 app/policies/

# Run migrations
make db-migrate

# Start development server
make run
```

## Project Structure

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation.

```
backend/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Core infrastructure
│   ├── models/       # Database models
│   ├── schemas/      # Pydantic schemas
│   ├── repositories/ # Data access layer
│   ├── services/     # Business logic
│   └── policies/     # OPA policies
├── tests/            # Test files
└── Makefile          # Development commands
```

## Key Features

- **FastAPI** - Modern, fast web framework
- **SQLAlchemy** - ORM for database operations
- **Pydantic** - Data validation and settings
- **OPA Integration** - Fine-grained authorization
- **JWT Authentication** - Secure token-based auth
- **RBAC** - Role-based access control
- **Docker** - Containerized development

## API Endpoints

### Authentication

- `POST /api/v1/users/token` - Login and get JWT token
- `POST /api/v1/users/register` - Register new user
- `GET /api/v1/users/me` - Get current user info

### Resources

- `GET /api/v1/resources` - List resources (with OPA filtering)
- `GET /api/v1/resources/{id}` - Get resource by ID
- `POST /api/v1/resources` - Create new resource
- `PATCH /api/v1/resources/{id}` - Update resource
- `DELETE /api/v1/resources/{id}` - Delete resource

### Users

- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user by ID
- `PATCH /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

## Authorization Flow

1. **Authentication**: User logs in with email/password, receives JWT token
2. **Request**: User makes request with JWT in Authorization header
3. **Validation**: Backend validates JWT and extracts user context
4. **OPA Query**: Service layer queries OPA with user context and action
5. **Decision**: OPA evaluates policies and returns decision with filters
6. **Database Query**: Repository applies filters and queries database
7. **Response**: Only authorized data is returned

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test

# Run specific test file
pytest tests/test_resources.py -v
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint
```

### Database Migrations

```bash
# Create new migration
make db-revision message="Add new field"

# Apply migrations
make db-migrate

# Rollback migration
make db-downgrade
```

### OPA Policy Testing

```bash
# Test OPA policies
make opa-test

# Run OPA server locally
make opa-run
```

## Configuration

Configuration is managed through environment variables. Copy `.env.example` to `.env` and update:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/co2_calculator

# Security
SECRET_KEY=your-secret-key-here

# OPA
OPA_URL=http://localhost:8181
OPA_ENABLED=true
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

### OPA Issues

```bash
# Check OPA is running
curl http://localhost:8181/health

# Test OPA policy
curl -X POST http://localhost:8181/v1/data/authz/resource/list \
  -d '{"input": {"action": "read", "user": {"id": "test"}}}'
```

### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

## Production Deployment

1. Update `.env` with production values
2. Set `DEBUG=false`
3. Use strong `SECRET_KEY`
4. Configure proper database credentials
5. Set up HTTPS/TLS
6. Disallow CORS_ORIGINS appropriately
7. Use production ASGI server (e.g., Gunicorn + Uvicorn workers)

```bash
# Production run
make run-prod
```

## Resources

- [Architecture Documentation](./ARCHITECTURE.md)
- [API Documentation](http://localhost:8000/docs) (when running)
- [OPA Documentation](https://www.openpolicyagent.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Support

For issues or questions, please refer to the main project documentation.
