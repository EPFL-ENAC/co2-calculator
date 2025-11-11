# Environments

The system is deployed across multiple environments with different
configurations and purposes.

## Dev / Stage / Prod Topology

| Environment    | Purpose                | Key Characteristics               | Secrets Management      |
| -------------- | ---------------------- | --------------------------------- | ----------------------- |
| Local          | Individual development | Docker Compose, minimal services  | .env files              |
| Development    | Team collaboration     | Shared services, frequent updates | Infisical + K8s secrets |
| Staging        | Pre-release testing    | Production-like configuration     | Infisical + K8s secrets |
| Pre-production | Final validation       | Production-like configuration     | Infisical + K8s secrets |
| Production     | Live user traffic      | High availability, monitoring     | Infisical + Azure Vault |

## Local Setup Instructions

For local development, the system can be run using Docker Compose. See
the [Development Guide](../frontend/01-overview.md) for detailed setup
instructions.

## Secrets Management Approach

Secrets are managed differently per environment to ensure security:

**Local Development:**

- Create `.env` files based on `.env.example` templates
- Files stored locally and never committed to version control
- Separate `.env` files for frontend and backend components
- Example: `backend/.env`, `frontend/.env`

**Cloud Environments (Dev/Stage/Prod):**

- **Infisical** manages secrets centrally
- **Infisical CRD** automatically creates Kubernetes secrets
- Secrets injected as environment variables into pods
- Azure Key Vault integration for additional security in production

## Environment-Specific Configurations

### Database Configuration

| Environment | Database      | Connection Pooling | Replication |
| ----------- | ------------- | ------------------ | ----------- |
| Local       | PostgreSQL 16 | Direct connection  | None        |
| Development | PostgreSQL 16 | PgBouncer          | None        |
| Staging     | PostgreSQL 16 | PgBouncer          | 1 replica   |
| Production  | PostgreSQL 16 | PgBouncer          | 2 replicas  |

### Redis/Celery Configuration

| Environment | Workers | Redis Mode    | Task Retention |
| ----------- | ------- | ------------- | -------------- |
| Local       | 1       | Single node   | 1 day          |
| Development | 2       | Single node   | 3 days         |
| Staging     | 3       | Single node   | 7 days         |
| Production  | 5+      | Redis Cluster | 30 days        |

### Key Environment Variables

| Variable                | Purpose               | Required |
| ----------------------- | --------------------- | -------- |
| `DATABASE_URL`          | PostgreSQL connection | Yes      |
| `REDIS_URL`             | Redis connection      | Yes      |
| `AZURE_STORAGE_ACCOUNT` | Blob storage account  | Yes      |
| `AZURE_CLIENT_ID`       | Entra ID client       | Yes      |
| `AZURE_CLIENT_SECRET`   | Entra ID secret       | Yes      |
| `AZURE_TENANT_ID`       | Entra ID tenant       | Yes      |
| `LOG_LEVEL`             | Logging verbosity     | No       |
| `ENVIRONMENT`           | Environment name      | Yes      |

Complete list available in `.env.example` files.

Environment-specific configurations are managed through:

- Environment variables for runtime settings
- Kubernetes secrets for sensitive information in cloud environments
- Local .env files for development

For detailed infrastructure information, see [Infrastructure Documentation](../infra/01-overview.md).
