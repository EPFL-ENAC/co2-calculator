# Cross-Cutting Concerns

## Security Model

### Data Classification and Protection Levels

Data is classified into four protection levels:

- Public: Available to all users
- Internal: Authenticated users only
- Confidential: Role-based access
- Restricted: Highly sensitive, limited access

### Transport and Data-at-Rest Encryption

- TLS on every external hop; intra-cluster traffic is unencrypted
- Fernet (AES-128-CBC + HMAC-SHA256) for uploaded files and stored
  connector secrets; database at-rest encryption is the provider's
- Certificates rotated automatically by cert-manager
- Keys held in ENAC-IT's Infisical vault, injected at runtime

See [Encryption and Key Management](encryption.md) for the full picture,
the key inventory, and the known gaps.

### Authentication Enforcement Points

Authentication is enforced at multiple points:

- API gateway level
- Individual service endpoints
- Database access layer
- Storage access controls

This section provides detailed security information. For implementation details, see [Backend Security](../backend/01-overview.md#security-considerations) and [Frontend Auth](../frontend/01-overview.md#authentication--authorization).

## Data Contracts

### API Schema Standards

All APIs follow OpenAPI 3.0 specification with:

- Defined request/response schemas
- Standardized error formats
- Versioned endpoints

### Internal Message/Event Format

Asynchronous messages use JSON format with:

- Standardized metadata fields
- Event type identifiers
- Timestamp and correlation IDs

### Versioning and Compatibility Policies

- Semantic versioning for APIs
- Backward compatibility maintained for N-1 versions
- Deprecation notices for obsolete endpoints

## Observability

### Structured Logging Approach

All components implement structured logging with:

- JSON format for easy parsing
- Consistent field naming
- Log level standardization
- Request correlation IDs

### Metrics Exposure

Metrics are exposed through:

- Prometheus-style endpoints
- Custom business metrics
- Standard system metrics (CPU, memory, etc.)

### Distributed Tracing Support

Tracing is implemented with:

- OpenTelemetry instrumentation
- Request span propagation
- Service dependency mapping

For detailed observability information, see [Infrastructure Monitoring](../infra/01-overview.md#monitoring--observability). For client-side error tracking via self-hosted GlitchTip, see [Frontend Error Monitoring](../frontend/error-monitoring.md).
