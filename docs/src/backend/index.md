# Backend Overview

This section provides an overview of the backend layer architecture, technologies, and integration points.

## Architecture Pattern

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Background Tasks**: Celery with Redis
- **Authentication**: OAuth2 with OIDC integration
- **API Documentation**: OpenAPI (Swagger/UI)

## Main Technologies

- FastAPI for REST API implementation
- PostgreSQL for relational data storage
- SQLAlchemy for ORM and database migrations
- Celery for asynchronous task processing
- Redis for caching and task queues
- Pydantic for data validation and serialization

## API Interface

The backend exposes a RESTful API for frontend consumption:

- Base URL: `/api/v1/`
- Authentication: Bearer token in Authorization header
- Content Type: JSON for requests and responses
- Error Handling: Standard HTTP status codes with JSON error bodies

## Integration Points

- **Database**: PostgreSQL for persistent storage
- **Cache**: Redis for caching and session storage
- **Message Broker**: Redis for Celery task queue
- **Authentication Service**: Microsoft Entra ID (OIDC)
- **File Storage**: S3-compatible storage for file uploads
- **Monitoring**: Prometheus and OpenTelemetry for metrics and tracing

## Subsystems

- [Architecture](./architecture.md) - Detailed backend architecture
- [API Design](./api.md) - API endpoints and contracts
- [Plugins/Extensions](./plugins.md) - Extension mechanisms
- [Testing](./testing.md) - Testing strategies and tools
- [Deployment](./deploy.md) - Deployment processes and considerations

For architectural overview, see [Architecture Overview](../architecture/index.md).
