# Environments

The system is deployed across multiple environments with different configurations and purposes.

## Dev / Stage / Prod Topology

| Environment    | Purpose                | Key Characteristics               |
| -------------- | ---------------------- | --------------------------------- |
| Local          | Individual development | Docker Compose, minimal services  |
| Development    | Team collaboration     | Shared services, frequent updates |
| Staging        | staging testing        | Production-like configuration     |
| Pre-production | Pre-production testing | Production-like configuration     |
| Production     | Live user traffic      | High availability, monitoring     |

## Local Setup Instructions

For local development, the system can be run using Docker Compose. See the [Development Guide](../frontend/dev-guide.md) for detailed setup instructions.

Environment-specific configurations/secrets - We'll use infisical and infisical CRD to manage secrets creations on kube - for local development, the user will create .env file based on .env.example for each sub-component

Environment-specific configurations are managed through:

- Environment variables for runtime settings
- Kubernetes secrets for sensitive information in cloud environments
- Local .env files for development

For detailed infrastructure information, see [Infrastructure Documentation](../infra/index.md).
