# Global Conventions

The system follows consistent conventions across all components to ensure maintainability and developer productivity.

## Naming Standards

- Services: lowercase with hyphens (e.g., `user-service`)
- APIs: RESTful with plural nouns (e.g., `/api/v1/users`)
- Variables: snake_case for Python, camelCase for JavaScript
- Database tables: plural snake_case (e.g., `user_profiles`)

## Logging & Monitoring Practices

All components implement structured logging:

- JSON format for machine parsing
- Consistent log levels (DEBUG, INFO, WARNING, ERROR)
- Correlation IDs for request tracing
- Performance metrics exposure

## Secret Management Policy

Secrets are managed through:

- Environment variables for runtime configuration
- Kubernetes secrets for containerized deployments
- Infisical + CRD for Kubernetes secrets
- Never committed to source control

## Error Handling Patterns

Error handling follows consistent patterns:

- Standardized error response format
- Proper HTTP status codes
- Detailed error messages in development
- Generic messages in production

For detailed conventions, see the individual component documentation and our CONTRIBUTING.md
