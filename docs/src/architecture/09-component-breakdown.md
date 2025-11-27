# Component Breakdown (High-Level View)

## Frontend Layer

### Architecture Pattern

Single Page Application (SPA) with client-side routing

### Main Technologies

- Vue 3 Composition API
- Quasar Framework for UI components
- Pinia for state management
- Axios for HTTP requests

### API Interface Style

RESTful HTTP APIs with JSON payloads, following OpenAPI specification

### How It Connects to Backend

- HTTP GET/POST/PUT/DELETE requests (no PATCH)
- Authentication headers with JWT tokens
- NO CORS
- Error handling with standardized responses

### Behavior as Subsystem

- Client-side routing with Vue Router
- Centralized state management with Pinia
- Responsive UI with Quasar components

For detailed frontend information, see [Frontend Documentation](../frontend/01-overview.md).

## Backend Layer

### Architecture Pattern

RESTful API microservice architecture

### Main Technologies

- FastAPI for API implementation
- Pydantic for data validation
- SQLAlchemy for ORM
- Uvicorn for ASGI server

### API Interface

- RESTful endpoints with JSON request/response formats
- Automatic OpenAPI documentation at `/docs` ( which means /api/docs)
- Standardized error responses

### How It Connects to Other Layers

- Database via SQLAlchemy ORM
- Workers via Redis message queue
- Frontend via HTTP REST APIs
- Storage via direct API calls

### Behavior as Subsystem

- Request handling and validation
- Business logic orchestration
- Data transformation and aggregation

For detailed backend information, see [Backend Documentation](../backend/01-overview.md).

## Workers / Async Processing Layer

### Architecture Pattern

Task queue with event-driven processing

### Main Technologies

- Celery for distributed task queue
- Redis as message broker
- Custom task definitions in Python

### How Tasks Are Triggered and Handled

- Tasks enqueued via Redis broker
- Workers consume tasks asynchronously
- Results stored in Redis or database

### Behavior as Subsystem

- Background job execution
- Retry logic with exponential backoff
- Task monitoring and management

For detailed worker information, see [Backend Overview](../backend/01-overview.md#background-processing).

## Database Layer

### Type and Purpose

PostgreSQL relational database for structured data persistence
PGBouncer if needed

### Connection Method

SQLAlchemy ORM with connection pooling

### Behavior as Subsystem

- Data persistence with ACID guarantees
- Transaction handling with rollback support
- Schema migrations with Alembic

For detailed database information, see [Database Documentation](../database/01-overview.md).

## Storage Layer

### Type and Purpose

S3-compatible object storage for unstructured file uploads (using EPFL s3 layer)

### Integration Method

- TBD ? Maybe Presigned URLs for secure direct uploads ?

### Behavior as Subsystem

- File lifecycle management to be clearly defined during implementation
- Access control through signed URLs TBD ? not sure, or proxy via API (slow)
- Metadata storage in database

For detailed storage information, see [Storage Documentation](../backend/01-overview.md).
