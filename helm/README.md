# Deploy CO2 Calculator on Kubernetes

Deploy the CO2 Calculator stack (FastAPI backend, Quasar frontend,
PostgreSQL) on Kubernetes with Helm. This guide covers local
development and production deployment.

## Prerequisites

Kubernetes 1.24+, Helm 3.8+, kubectl configured.

## Quick Start

```bash
# Install with default values
helm install co2-calc ./helm

# Access locally
kubectl port-forward svc/co2-calc-frontend 8080:80
```

Visit `http://localhost:8080`.

Override defaults with a custom values file:

```bash
helm install co2-calc ./helm -f values.local.yaml
```

## Development with Skaffold

Start a live-reload development loop:

- `backend.env`: Maps to `APP_NAME`, `API_VERSION`, `LOG_LEVEL` and security values such as `ALGORITHM`.
- `backend.secrets.SECRET_KEY`: Mirrors the required `SECRET_KEY` in the backend `.env`. Override with a secure value.
- `database.external`: Provides the duplicate `DB_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` entries expected by the backend.
- `frontend.env.API_BASE_URL`: Allows the UI to target the API path exposed through the ingress.

```bash
cd helm
make skaffold-dev
```

Skaffold watches for code changes, rebuilds images, and redeploys
pods automatically.

## Production Deployment

### 1. Create Secrets

```bash
kubectl create namespace prod

# Backend secret
kubectl create secret generic backend-secret -n prod \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"

# Database secret
kubectl create secret generic db-secret -n prod \
  --from-literal=DB_URL='postgresql+psycopg://user:pass@host:5432/db'
```

### 2. Configure values.prod.yaml

```yaml
backend:
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
  existingSecret:
    enabled: true
    name: backend-secret

database:
  existingSecret:
    name: db-secret

ingress:
  enabled: true
  className: nginx
  hosts:
    - co2.example.com
  tls:
    - secretName: co2-tls
      hosts: [co2.example.com]
```

### 3. Deploy

```bash
helm install co2-calc ./helm -n prod -f values.prod.yaml
```

Migrations run automatically via an init container. Disable with
`backend.migrations.enabled: false` if running manually.

## Configuration Essentials

### Resource Limits

```yaml
backend:
  resources:
    requests: { cpu: 250m, memory: 256Mi }
    limits: { cpu: 1000m, memory: 1Gi }
```

### Autoscaling

```yaml
backend:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
```

### Environment Variables

```yaml
backend:
  env:
    DEBUG: "false"
    LOG_LEVEL: "INFO"
```

## Updates and Rollbacks

### Upgrade Release

```bash
helm upgrade co2-calc ./helm -n prod -f values.prod.yaml
```

### Rollback

```bash
helm rollback co2-calc -n prod
```

If schema changed, downgrade database:

```bash
kubectl exec deploy/co2-calc-backend -n prod -- \
  alembic downgrade -1
```

## Additional Resources

- Full configuration reference: values.yaml
- Chart version: 0.2.0
- Makefile targets: `make help` from helm directory
