# Global Conventions

The system follows consistent conventions across all components to ensure
maintainability and developer productivity.

## Naming Standards

Services follow consistent naming patterns across all layers:

| Component Type   | Convention           | Example           |
| ---------------- | -------------------- | ----------------- |
| Services         | lowercase-kebab-case | `user-service`    |
| API Endpoints    | RESTful plural nouns | `/api/v1/users`   |
| Python Variables | snake_case           | `user_profile`    |
| JS Variables     | camelCase            | `userProfile`     |
| Classes          | PascalCase           | `UserProfile`     |
| Constants        | UPPER_SNAKE_CASE     | `MAX_UPLOAD_SIZE` |
| Database Tables  | plural_snake_case    | `user_profiles`   |
| Files            | kebab-case.ext       | `user-service.ts` |

For comprehensive naming and code style guidelines, see
[Code Standards](code-standards.md).

## Logging & Monitoring Practices

All components implement structured logging with consistent format:

### Log Format

JSON structured logs for machine parsing:

```json
{
  "timestamp": "2025-11-11T10:30:00Z",
  "level": "INFO",
  "service": "backend-api",
  "correlation_id": "abc-123-def",
  "user_id": "user@epfl.ch",
  "message": "Emissions calculated",
  "duration_ms": 45,
  "metadata": {
    "distance": 100,
    "mode": "car"
  }
}
```

### Log Levels

Use consistent log levels across all services:

- **DEBUG**: Detailed diagnostic information for development
- **INFO**: General informational messages about system operation
- **WARNING**: Unexpected situations that don't prevent operation
- **ERROR**: Errors that prevent specific operations from completing
- **CRITICAL**: System-level failures requiring immediate attention

### Correlation IDs

Every request gets a unique correlation ID for tracing:

- Generated at API gateway
- Propagated through all services
- Included in all log entries
- Returned in API responses

### Performance Metrics

All services expose Prometheus metrics:

- Request count and duration
- Error rates
- Queue depths
- Database connection pool status
- Cache hit rates

Access metrics at `/metrics` endpoint on each service.

## Secret Management Policy

Secrets are never stored in code or version control:

### Local Development

- Create `.env` files from `.env.example` templates
- Store locally, never commit
- One `.env` per service

### Cloud Environments

- **Infisical** for central secret management
- **Infisical CRD** creates Kubernetes secrets automatically
- **Azure Key Vault** for production-critical secrets
- Environment variables injected at runtime

### Secret Categories

| Secret Type            | Storage Location        | Rotation Period |
| ---------------------- | ----------------------- | --------------- |
| Database credentials   | Infisical → K8s secrets | 90 days         |
| API keys               | Infisical → K8s secrets | 90 days         |
| Entra ID client secret | Azure Key Vault         | 180 days        |
| Encryption keys        | Azure Key Vault         | 365 days        |

## Error Handling Patterns

All APIs follow standardized error response format:

### Error Response Structure

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Distance must be a positive number",
    "details": {
      "field": "distance",
      "value": -10,
      "constraint": "positive"
    },
    "correlation_id": "abc-123-def",
    "timestamp": "2025-11-11T10:30:00Z"
  }
}
```

### HTTP Status Codes

Use proper HTTP status codes consistently:

| Status | Meaning              | Use Case                         |
| ------ | -------------------- | -------------------------------- |
| 200    | OK                   | Successful GET/PUT               |
| 201    | Created              | Successful POST                  |
| 204    | No Content           | Successful DELETE                |
| 400    | Bad Request          | Invalid input                    |
| 401    | Unauthorized         | Missing/invalid authentication   |
| 403    | Forbidden            | Insufficient permissions         |
| 404    | Not Found            | Resource doesn't exist           |
| 409    | Conflict             | Resource already exists          |
| 422    | Unprocessable Entity | Validation failed                |
| 500    | Internal Error       | Unexpected server error          |
| 503    | Service Unavailable  | Temporary service unavailability |

### Error Codes

Use consistent error code prefixes:

- `AUTH_*` - Authentication/authorization errors
- `VALID_*` - Validation errors
- `DB_*` - Database errors
- `EXT_*` - External service errors
- `SYS_*` - System/infrastructure errors

## API Response Standards

All REST API responses follow consistent structure:

### Success Response

```json
{
  "data": {
    "id": 123,
    "emissions": 20.5,
    "unit": "kg_co2"
  },
  "metadata": {
    "timestamp": "2025-11-11T10:30:00Z",
    "version": "v1"
  }
}
```

### List Response with Pagination

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  },
  "links": {
    "self": "/api/v1/emissions?page=1",
    "next": "/api/v1/emissions?page=2",
    "prev": null
  }
}
```

## API Versioning

API versions in URL path: `/api/v1/resource`

Breaking changes require new version: `/api/v2/resource`

Maintain backward compatibility for minimum 6 months.

## Code Quality Standards

All code must meet minimum quality gates before merge:

### Backend (Python / FastAPI)

- Follow PEP 8, PEP 484 typing standards
- Type hints required for all public functions
- Ruff formatter and Ruff linter must pass
- Async/await preferred for I/O operations
- 60% minimum test coverage with pytest
- FastAPI generates valid OpenAPI documentation

### Frontend (Vue / Quasar)

- Vue 3 Composition API with `<script setup>` syntax
- TypeScript encouraged for new code
- Pinia for global state management
- ESLint and Prettier must pass
- All UI text via i18n (`$t()` function)
- WCAG AA accessibility compliance
- 60% minimum test coverage with Vitest

For complete coding standards, see [Code Standards](code-standards.md).

## Version Control Workflow

Project uses three-tier promotion model:

| Branch  | Environment    | Purpose                |
| ------- | -------------- | ---------------------- |
| `dev`   | Development    | Active development     |
| `stage` | Staging        | Pre-release validation |
| `main`  | Pre-production | Production-ready code  |

**Branch naming:**

- `feature/<issue>` - New features
- `fix/<issue>` - Bug fixes
- `chore/<description>` - Non-functional changes

**Commit format:**

Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`

**Review requirements:**

- 2 reviewers minimum for security-critical code
- CI checks must pass before merge
- Product owner approval required for stage/main

For detailed workflow, see [Workflow Guide](workflow-guide.md).

## Observability Requirements

All services must implement standard observability practices:

### Metrics Endpoint

Expose `/metrics` endpoint with Prometheus format:

- Request count and duration
- Error rates by type
- Resource utilization (CPU, memory)
- Business metrics (calculations performed)

### Distributed Tracing

Use OpenTelemetry for request tracing:

- Trace context propagated across services
- Span created for each major operation
- Critical paths instrumented

### Structured Logging

Include correlation IDs in all log entries for request tracing.

For monitoring setup, see [Infrastructure Monitoring](../infra/01-overview.md).

## Performance Targets

System must meet these baseline performance requirements:

| Metric                  | Target  |
| ----------------------- | ------- |
| API response time (p95) | < 500ms |
| Frontend load time      | < 2s    |
| Database query time     | < 100ms |
| Concurrent users        | 1000+   |
| Lighthouse score        | > 90    |

**Best practices:**

- Stateless design for horizontal scaling
- Redis caching for emission factors
- Database connection pooling
- CDN for static assets
- Lazy loading for frontend routes

For scaling strategy, see [Scalability](12-scalability.md).

## Documentation Standards

Keep documentation concise and actionable:

- Target 500-800 words per document (10-minute read) Okay if < 1200 words
- Use active voice and imperative mood
- Wrap text at 72 characters
- Include examples after concepts
- Add cross-references to related docs
- Avoid duplicating content across files

Update documentation in the same PR as code changes.

For detailed conventions and code examples, see the [Code Standards
documentation](code-standards.md) and individual component guides.
