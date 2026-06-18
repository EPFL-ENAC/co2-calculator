# Infrastructure Overview

The infrastructure runs on **EPFL OpenShift** with a managed PostgreSQL (DBaaS) for persistence and OpenTelemetry-based monitoring (Jaeger for traces, Prometheus/Grafana for metrics). This overview covers deployment, hosting, and operational procedures.

For system architecture and deployment decisions, see:

- [Deployment Topology](../architecture/11-deployment-topology.md) - Infrastructure architecture
- [Environments](../architecture/05-environments.md) - Environment configuration
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) - Automated deployment
- [Tech Stack](../architecture/08-tech-stack.md) - Infrastructure technology choices
- [Disaster Recovery Plan](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md) - Need access (private repo)

---

## Infrastructure Overview

### Platform

- **Platform**: EPFL OpenShift (project `svc1751…-co2-calculator-<env>`)
- **Container Runtime**: CRI-O (OpenShift)
- **Orchestration**: Helm chart + GitOps
- **Ingress**: OpenShift Routes (TLS edge); internal only, EPFL VPN required
- **Database**: managed PostgreSQL (EPFL DBaaS) — not in-cluster
- **Storage**: EPFL S3 for file blobs; `db-dumps` PVC for backups
- **Monitoring**: OpenTelemetry → Jaeger + Prometheus/Grafana, Alertmanager (email)
- **Secrets Management**: Infisical Operator (dev); manual secrets (stage/prod); Azure Key Vault planned (prod)
- **Image Registry**: Quay (quay-its.epfl.ch)
- **Deployment**: ArgoCD (GitOps) + GitHub Actions

### Network Architecture

```
Internet
  ↓
EPFL VPN (required for external access)
  ↓
OpenShift Route (TLS edge)
  ↓
Services (frontend, backend, docs)
  ↓
Managed PostgreSQL (EPFL DBaaS)
```

**Access**: Application is **NOT publicly accessible** outside EPFL network. Users must connect via EPFL VPN or be on EPFL campus network.

---

## Deployment

### Helm Chart Structure

```
helm/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default configuration
├── values-dev.yaml         # Development overrides
├── values-staging.yaml     # Staging overrides
├── values-prod.yaml        # Production overrides
└── templates/
    ├── frontend-deployment.yaml
    ├── backend-deployment.yaml
    ├── docs-deployment.yaml
    ├── {frontend,backend,docs}-service.yaml
    ├── routes.yaml          # OpenShift Routes (TLS edge)
    ├── ingress.yaml         # plain-K8s fallback
    ├── {frontend,backend}-hpa.yaml
    ├── {frontend,backend}-pdb.yaml
    ├── migration-job.yaml   # alembic upgrade head (hook)
    ├── backend-secret.yaml  # only when not using an existing secret
    └── serviceaccount.yaml

# PostgreSQL is external (DBaaS). The OTEL Collector, Jaeger, monitoring
# CRs (ServiceMonitor/PrometheusRule/GrafanaDashboard/AlertmanagerConfig)
# and the db-dump CronJob are deployed from the GitOps repo, not this chart.
```

### Deploying to Environments

**Via ArgoCD** (Recommended):

ArgoCD automatically syncs from Git repository to Kubernetes cluster.

```bash
# View ArgoCD applications
argocd app list

# Sync application manually
argocd app sync co2-calculator-dev

# View deployment status
argocd app get co2-calculator-dev
```

**Via Helm** (Manual):

```bash
# Deploy to development
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-dev \
  --values helm/values-dev.yaml

# Deploy to staging
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-staging \
  --values helm/values-staging.yaml

# Deploy to production
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-prod \
  --values helm/values-prod.yaml
```

### Deployment Checklist

Before deploying to production:

- [ ] All tests pass in CI/CD pipeline
- [ ] Staging deployment tested and validated
- [ ] Database migrations reviewed and tested
- [ ] Environment variables configured correctly
- [ ] Secrets rotated if needed
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Stakeholders notified of deployment window

---

## Kubernetes Resources

### Namespaces

- `co2-calculator-dev`: Development environment
- `co2-calculator-staging`: Staging environment
- `co2-calculator-prod`: Production environment

### Deployments

```yaml
# Frontend (Nginx + Vue SPA)
frontend:
  replicas: 2          # HPA 2–10

# Backend (FastAPI + Uvicorn, in-process jobs)
backend:
  replicas: 2          # HPA 2–10

# Docs (MkDocs static, Nginx)
docs:
  replicas: 1
```

Background jobs run in-process inside the backend pods (no worker fleet, no Redis broker). See [ADR-010](../architecture-decision-records/010-background-job-processing.md).

### Database (external)

PostgreSQL is a **managed database (EPFL DBaaS)** — not deployed
in-cluster, so there is no StatefulSet or database PVC. The application
reaches it over `DB_URL`. The only PVC in the namespace is `db-dumps`,
written by the `db-dump` backup CronJob.

### Services

```yaml
# Service definitions (all ClusterIP)
frontend-service:  { port: 80,   targetPort: 8080 }
backend-service:   { port: 8000, targetPort: 8000 }
docs-service:      { port: 80,   targetPort: 8080 }
```

### Routing (OpenShift Routes)

On OpenShift, traffic is routed by **Routes** with TLS edge termination
(the Helm chart also ships a plain-K8s nginx Ingress as a fallback):

| Path    | Service          | Port |
| ------- | ---------------- | ---- |
| `/`     | frontend-service | 80   |
| `/api`  | backend-service  | 8000 |
| `/docs` | docs-service     | 80   |

Hosts: `co2-calculator-dev.epfl.ch`, `co2-calculator-stage.epfl.ch`,
`co2-calculator.epfl.ch`.

---

## Configuration Management

### ConfigMaps

```yaml
# Application configuration (non-sensitive)
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  ENVIRONMENT: production
  LOG_LEVEL: INFO
  FRONTEND_URL: https://co2-calculator.epfl.ch
# DB_URL and all credentials live in Secrets, not here.
```

### Secrets

On **dev**, the Infisical Operator generates the Kubernetes Secrets. On
**stage/prod**, secrets are currently created manually (OpenShift not yet
wired to Infisical). Either way they are injected into pods as env vars:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
type: Opaque
data:
  DB_URL: <base64-encoded>
  SECRET_KEY: <base64-encoded>
  OAUTH_CLIENT_SECRET: <base64-encoded>
```

**Management**:

```bash
# View secrets (requires cluster admin access)
kubectl get secrets -n co2-calculator-prod

# Describe secret (no values shown)
kubectl describe secret backend-secrets -n co2-calculator-prod

# Rotate secret
# Dev: update in Infisical → Operator re-syncs. Stage/prod: update the OpenShift secret. Then:
kubectl rollout restart deployment co2-calculator-backend -n <namespace>
```

---

## Storage

### Persistent Volumes

The database is external (DBaaS), so the app mounts **no database
volume**. The only PVC is `db-dumps`, used by the backup CronJob. File
uploads go to EPFL S3 (or local disk when S3 is unset).

### Storage Classes

- **rcp-nas**: RCP NAS storage (default, for database)
- **local-path**: Local node storage (for temporary files)

### Backup Storage

- **Database backups**: `db-dump` CronJob → `db-dumps` PVC
- **Application files**: EPFL S3 (or local disk when S3 is unset)

---

## Monitoring & Observability

Client-side JavaScript errors are tracked separately in self-hosted
GlitchTip — see [Frontend Error Monitoring](../frontend/error-monitoring.md).

### Metrics & Traces

The backend is OpenTelemetry-instrumented and exports OTLP to the
in-namespace **OTEL Collector**. From there:

- **Traces** → Jaeger (`otel-collector-jaeger`)
- **Metrics** → scraped from the collector by Prometheus via a
  `ServiceMonitor` (`otel-collector-metrics-monitor`)

There is **no backend `/metrics` endpoint**; Prometheus does not scrape
the app pods directly.

### Grafana Dashboards

**Main Dashboards**:

1. **Application Overview**
   - Request rate, latency, error rate
   - Active users, database connections

2. **Infrastructure Health**
   - CPU, memory, disk usage per pod
   - Network I/O, request throughput
   - Pod restart count, OOMKills

3. **Database Performance**
   - Query duration, slow queries
   - Connection pool usage
   - Table sizes, index usage

**Access**: https://grafana.epfl.ch (requires EPFL credentials)

### Alerting

**Critical Alerts** (email):

- Service down (all replicas unhealthy)
- Database connection failure
- Disk space > 90%
- Error rate > 5% for 5 minutes

**Warning Alerts** (email):

- High memory usage (> 80%)
- Slow response time (> 1s p95)
- Certificate expiry (< 7 days)

**Configuration**: `PrometheusRule` + `AlertmanagerConfig` (email), deployed via GitOps.

### Logging

**Log Aggregation**: structured JSON to stdout (OpenShift logging). Audit records sync to **Elasticsearch** (OPDo); optional Loki push (`LOKI_ENABLED`, off by default).

```bash
# View pod logs
kubectl logs -n co2-calculator-prod deployment/backend --tail=100 -f

# View logs from all backend replicas
kubectl logs -n co2-calculator-prod -l app=backend --tail=50

# Search logs (if Kibana available)
# Access Kibana UI and filter by namespace: co2-calculator-prod
```

**Log Format**: Structured JSON logs

```json
{
  "timestamp": "2025-11-11T10:15:30Z",
  "level": "INFO",
  "logger": "app.services.labs",
  "message": "Laboratory created",
  "lab_id": "abc123",
  "user_id": "user456",
  "trace_id": "xyz789"
}
```

---

## Scaling

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

**Trigger**: Auto-scales when CPU > 70% or memory > 80%

### Manual Scaling

```bash
# Scale backend replicas
# Background jobs run in-process, so this also scales job capacity (no separate worker tier).
kubectl scale deployment backend --replicas=5 -n co2-calculator-prod
```

---

## Operations

### Common kubectl Commands

```bash
# View all resources in namespace
kubectl get all -n co2-calculator-prod

# Check pod status
kubectl get pods -n co2-calculator-prod

# Describe pod (troubleshooting)
kubectl describe pod backend-xxxxx -n co2-calculator-prod

# View pod logs
kubectl logs backend-xxxxx -n co2-calculator-prod

# Execute command in pod
kubectl exec -it backend-xxxxx -n co2-calculator-prod -- /bin/bash

# Port forward for local access
kubectl port-forward svc/backend-service 8000:8000 -n co2-calculator-prod

# Restart deployment
kubectl rollout restart deployment backend -n co2-calculator-prod

# View rollout status
kubectl rollout status deployment backend -n co2-calculator-prod

# Rollback deployment
kubectl rollout undo deployment backend -n co2-calculator-prod
```

### Health Checks

```bash
# Check ingress
kubectl get ingress -n co2-calculator-prod

# Test backend health endpoint
curl https://co2calculator.epfl.ch/api/health

# Test from inside cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n co2-calculator-prod -- \
  curl http://backend-service:8000/health
```

### Database Operations

```bash
# The database is external (DBaaS) — there is no in-cluster postgres pod.
# Connect using DB_URL from the backend secret (e.g. from a tools pod):
psql "$DB_URL" -c "SELECT 1;"

# Scheduled backups come from the db-dump CronJob (→ db-dumps PVC).
# Trigger an ad-hoc backup:
oc create job --from=cronjob/db-dump db-dump-manual -n <namespace>
```

---

## Troubleshooting

### Pod Not Starting

```bash
# Check pod events
kubectl describe pod backend-xxxxx -n co2-calculator-prod

# Common issues:
# - ImagePullBackOff: Check image name/tag, registry credentials
# - CrashLoopBackOff: Check logs, environment variables
# - Pending: Check resource requests, node capacity
```

### Service Not Reachable

```bash
# Check service endpoints
kubectl get endpoints backend-service -n co2-calculator-prod

# Check ingress configuration
kubectl describe ingress co2-calculator-ingress -n co2-calculator-prod

# Test service from inside cluster
kubectl run -it --rm test --image=curlimages/curl --restart=Never -n co2-calculator-prod -- \
  curl http://backend-service:8000/health
```

### Database Connection Issues

```bash
# The database is external (DBaaS) — no postgres pod to inspect.
# Test connectivity from a backend pod using its DB_URL:
kubectl exec -it deploy/co2-calculator-backend -n <namespace> -- \
  python -c "import os, psycopg; psycopg.connect(os.environ['DB_URL']).close(); print('ok')"
```

### High Resource Usage

```bash
# Check resource usage
kubectl top pods -n co2-calculator-prod

# Check resource limits
kubectl describe pod backend-xxxxx -n co2-calculator-prod | grep -A 5 "Limits"

# View historical metrics in Grafana
# Or use kubectl metrics (if metrics-server installed)
```

---

## Security

### Network Policies

```yaml
# Restrict backend to only accept traffic from frontend and ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-network-policy
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
        - podSelector:
            matchLabels:
              app: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
```

### Pod Security

- **Run as non-root**: All containers run as non-root user
- **Read-only filesystem**: Containers have read-only root filesystem where possible
- **Drop capabilities**: Unnecessary Linux capabilities dropped
- **Resource limits**: CPU and memory limits enforced

### TLS/SSL

- **Certificate management**: cert-manager with Let's Encrypt
- **TLS termination**: At ingress controller
- **Internal communication**: Unencrypted (within cluster network)

---

## Additional Resources

### Architecture Documentation

- [Deployment Topology](../architecture/11-deployment-topology.md) - Full deployment architecture
- [Scalability Strategy](../architecture/12-scalability.md) - Scaling patterns
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) - Deployment automation

### EPFL Resources

- EPFL Kubernetes Documentation (internal)
- ENAC-IT Support (for infrastructure issues)
- RCP NAS Documentation (for storage)

### External Documentation

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Prometheus Documentation](https://prometheus.io/docs/)

---

**Last Updated**: November 11, 2025  
**Readable in**: ~10 minutes
