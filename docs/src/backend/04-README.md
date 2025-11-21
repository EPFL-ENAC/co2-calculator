# Backend Quick Start

This is a quick reference for getting the backend up and running. For
detailed architecture information, see [Architecture](02-ARCHITECTURE.md).

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional but recommended)

## Quick Start with Docker

Start all services:

```bash
make docker-up
```

The API runs at:

- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

Stop services:

```bash
make docker-down
```

## Local Development

Install dependencies:

```bash
make install
```

Configure environment:

```bash
cp .env.example .env
# Edit .env with your settings
```

Start PostgreSQL, then run migrations:

```bash
make db-migrate
```

Start development server:

```bash
make run
```

## Project Structure

```
backend/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Infrastructure
│   ├── models/       # Database models
│   ├── schemas/      # Pydantic schemas
│   ├── repositories/ # Data access
│   └── services/     # Business logic
├── tests/            # Test files
└── Makefile          # Dev commands
```

See [File Structure](03-FILE_STRUCTURE.md) for details.

## Key Features

- **FastAPI** - Modern web framework with auto-generated docs
- **SQLAlchemy** - ORM for database operations
- **Pydantic** - Data validation
- **JWT** - Token-based authentication
- **RBAC** - Role-based access control

## API Endpoints

### Authentication

- `POST /api/v1/users/token` - Login and get JWT
- `POST /api/v1/users/register` - Register new user
- `GET /api/v1/users/me` - Get current user

### Resources

- `GET /api/v1/resources` - List resources
- `GET /api/v1/resources/{id}` - Get resource
- `POST /api/v1/resources` - Create resource
- `PATCH /api/v1/resources/{id}` - Update resource
- `DELETE /api/v1/resources/{id}` - Delete resource

### Users

- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user
- `PATCH /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

## Development Workflow

Run tests:

```bash
make test
```

Format code:

```bash
make format
```

Run linters:

```bash
make lint
```

Create database migration:

```bash
make db-revision message="Add new field"
```

Apply migrations:

```bash
make db-migrate
```

## Configuration

Key environment variables in `.env`:

```env
DB_URL=postgresql://user:pass@localhost:5432/co2calculator
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
CORS_ORIGINS=http://localhost:3000
```

## Troubleshooting

### Database Connection

Check PostgreSQL:

```bash
docker-compose ps postgres
docker-compose logs postgres
```

### Debug Logging

Enable in `.env`:

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

## Production Deployment

1. Set `DEBUG=false`
2. Generate secure `SECRET_KEY`
3. Restrict `CORS_ORIGINS`
4. Use Gunicorn:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Documentation

- [Architecture](02-ARCHITECTURE.md) - System design
- [File Structure](03-FILE_STRUCTURE.md) - Code organization
- [Request Flow](05-REQUEST_FLOW.md) - Request lifecycle
- [API Docs](http://localhost:8000/docs) - Interactive API docs

## External Resources

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
